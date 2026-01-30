import json
import os
import math
import numpy as np
from pathlib import Path

class TemporalService:
    def __init__(self, base_dir: str = "crawler/sessions"):
        self.base_dir = Path(base_dir)
        self._cache = {}

    def get_temporal_gap_data(self, target_stars=None):
        if target_stars is None:
            target_stars = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
            
        raw_data, meta = self._load_all_data()
        if not raw_data:
            return {}

        deltas_map = self._calculate_deltas(raw_data)
        
        result = {}
        for key, deltas in deltas_map.items():
            # Extract star level from key (e.g., no_event_catch_off_17)
            try:
                # Expecting format: {event}_{catch}_{star}
                parts = key.split("_")
                star = int(parts[-1])
            except:
                continue
                
            if star not in target_stars:
                continue

            # Calculate Real Z-scores
            real_z = []
            hourly_data = []
            n_list = []
            for d in deltas:
                n = d["n"]
                p = d["p_s"]
                obs_s = d["s_n"]
                exp_s = n * p
                std = math.sqrt(n * p * (1 - p))
                z = (obs_s - exp_s) / std if std > 0 else 0
                
                real_z.append(z)
                n_list.append(n)
                hourly_data.append({
                    "timestamp": d["timestamp"],
                    "n": n,
                    "success": int(obs_s),
                    "expected": float(exp_s),
                    "z_score": float(z)
                })

            if len(real_z) < 2:
                continue

            # Simulate IID Baseline
            # For each hour, we sample from a Binomial(n, p)
            iid_z = []
            for d in deltas:
                n = d["n"]
                p = d["p_s"]
                # Use numpy for binomial sampling
                sim_s = np.random.binomial(n, p)
                sim_exp = n * p
                sim_std = math.sqrt(n * p * (1 - p))
                sz = (sim_s - sim_exp) / sim_std if sim_std > 0 else 0
                iid_z.append(float(sz))

            result[str(star)] = {
                "real": {
                    "z_scores": [float(z) for z in real_z],
                    "variance": float(np.var(real_z)),
                    "autocorr": float(self._autocorr(real_z)),
                    "skew": float(self._skewness(real_z)),
                    "kurt": float(self._kurtosis(real_z)),
                    "hourly": hourly_data
                },
                "iid": {
                    "z_scores": iid_z,
                    "variance": float(np.var(iid_z)),
                    "autocorr": float(self._autocorr(iid_z)),
                    "skew": float(self._skewness(iid_z)),
                    "kurt": float(self._kurtosis(iid_z))
                },
                "summary": {
                    "n_obs": len(real_z),
                    "n_mean": float(np.mean(n_list)) if n_list else 0.0,
                    "n_median": float(np.median(n_list)) if n_list else 0.0,
                    "z_mean": float(np.mean(real_z)) if real_z else 0.0,
                    "z_std": float(np.std(real_z)) if real_z else 0.0,
                    "z_var": float(np.var(real_z)) if real_z else 0.0,
                    "se_autocorr": float(1.0 / math.sqrt(len(real_z))) if len(real_z) > 0 else 0.0
                }
            }
            
        result["_meta"] = meta
        self._cache["data"] = result
        return result

    def _load_all_data(self):
        all_entries = []
        if not self.base_dir.exists():
            return [], {"source": "none", "sessions_total": 0, "sessions_relabel": 0, "sessions_original": 0}
            
        # Prefer relabeled snapshots if present in a session folder
        seen_snapshots = set()
        sessions_total = 0
        sessions_relabel = 0
        sessions_original = 0
        for root, _, _ in os.walk(self.base_dir):
            relabeled = Path(root) / "hourly_snapshots_relabel.jsonl"
            original = Path(root) / "hourly_snapshots.jsonl"
            path = relabeled if relabeled.exists() else original
            if not path.exists():
                continue
            sessions_total += 1
            if relabeled.exists():
                sessions_relabel += 1
            else:
                sessions_original += 1

            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if entry.get("data_by_key"):
                                total_s = sum(v.get("success_count", 0) for v in entry["data_by_key"].values())
                                sig = f"{entry.get('window_end')}_{total_s}"
                                if sig in seen_snapshots and entry.get('window_end'):
                                    continue
                                seen_snapshots.add(sig)
                                all_entries.append(entry)
                        except:
                            continue
            except Exception as e:
                print(f"Error reading {path}: {e}")
                continue
        
        # Sort by timestamp globally
        all_entries.sort(key=lambda x: x["timestamp"])
        if sessions_relabel and sessions_original:
            source = "mixed"
        elif sessions_relabel:
            source = "relabel"
        else:
            source = "original"
        meta = {
            "source": source,
            "sessions_total": sessions_total,
            "sessions_relabel": sessions_relabel,
            "sessions_original": sessions_original
        }
        return all_entries, meta

    def _calculate_deltas(self, raw_data):
        deltas_map = {}
        prev_data = None
        
        for entry in raw_data:
            curr_data = entry["data_by_key"]
            curr_ts = entry["timestamp"]
            
            if prev_data:
                for key, curr_vals in curr_data.items():
                    if key not in prev_data: continue
                    prev_vals = prev_data[key]
                    
                    # 1. 누적 데이터 역전 체크 (Data Glitch 방지)
                    # 현재 값이 이전 값보다 작으면 '패치 리셋'이 아닐 경우(데이터 오염) 무시
                    if curr_vals["success_count"] < prev_vals["success_count"] or \
                       curr_vals["fail_count"] < prev_vals["fail_count"] or \
                       curr_vals["boom_count"] < prev_vals["boom_count"]:
                        # 넥슨 서버 리셋(50% 이상 폭락)이 아닌 미세한 감소는 글리치로 간주
                        total_prev = prev_vals["success_count"] + prev_vals["fail_count"] + prev_vals["boom_count"]
                        total_curr = curr_vals["success_count"] + curr_vals["fail_count"] + curr_vals["boom_count"]
                        if total_curr < total_prev * 0.5:
                            # 이건 패치 리셋으로 간주하고 현재 값을 Delta로 사용
                            ds, df, db = curr_vals["success_count"], curr_vals["fail_count"], curr_vals["boom_count"]
                        else:
                            # 이건 데이터 오염(Glitch)이므로 건너뜀
                            continue
                    else:
                        ds = curr_vals["success_count"] - prev_vals["success_count"]
                        df = curr_vals["fail_count"] - prev_vals["fail_count"]
                        db = curr_vals["boom_count"] - prev_vals["boom_count"]

                    # 2. 확률 급변 체크 (설정 확률 p_s가 이전과 0.1% 이상 다르면 오염된 데이터로 간주)
                    if abs(curr_vals["success_rate"] - prev_vals["success_rate"]) > 0.001:
                        continue

                    dn = ds + df + db
                    if dn <= 0: continue
                    
                    # Store window_end if available for better temporal alignment
                    window_end = curr_vals.get("window_end", curr_ts)
                    
                    if key not in deltas_map:
                        deltas_map[key] = []
                        
                    deltas_map[key].append({
                        "n": dn,
                        "s_n": ds,
                        "p_s": curr_vals["success_rate"],
                        "timestamp": curr_ts,
                        "window_end": window_end
                    })
            
            # CRITICAL FIX: Only update prev_data if current snapshot is not empty
            if curr_data and len(curr_data) > 0:
                prev_data = curr_data
                
        return deltas_map

    def _autocorr(self, x):
        if len(x) < 5: return 0.0
        a = np.array(x)
        if np.std(a) == 0: return 0.0
        return float(np.corrcoef(a[:-1], a[1:])[0, 1])

    def _skewness(self, x):
        if len(x) < 5: return 0.0
        a = np.array(x)
        m = np.mean(a)
        s = np.std(a)
        if s == 0: return 0.0
        return np.mean(((a - m) / s) ** 3)

    def _kurtosis(self, x):
        if len(x) < 5: return 0.0
        a = np.array(x)
        m = np.mean(a)
        s = np.std(a)
        if s == 0: return 0.0
        return np.mean(((a - m) / s) ** 4) - 3.0
