import json
import os
from collections import defaultdict, Counter
from typing import Optional

# Base success rates (Starcatch OFF)
BASE_PROBS = {
    0: 0.95, 1: 0.90, 2: 0.85, 3: 0.85, 4: 0.80, 5: 0.75, 6: 0.70, 7: 0.65, 8: 0.60, 9: 0.55,
    10: 0.50, 11: 0.45, 12: 0.40, 13: 0.35, 14: 0.30, 15: 0.30, 16: 0.30, 17: 0.15, 18: 0.15, 19: 0.15,
    20: 0.30, 21: 0.15, 22: 0.15, 23: 0.10, 24: 0.10, 25: 0.10, 26: 0.07, 27: 0.05, 28: 0.03, 29: 0.01,
}

def _parse_star_from_key(key: str) -> Optional[int]:
    parts = key.split("_")
    for part in reversed(parts):
        if part.isdigit(): return int(part)
    return None

def _infer_catch_label_static(star: int, p: float) -> str:
    if star not in BASE_PROBS: return "catch_unknown"
    base_p = BASE_PROBS[star]
    catch_p = base_p * 1.05
    dist_base = abs(p - base_p)
    dist_catch = abs(p - catch_p)
    return "catch_on" if dist_catch < dist_base else "catch_off"

def relabel_sessions(base_dir="crawler/sessions"):
    print("Relabeling sessions with Stability Fix (Majority Vote)...")
    
    for root, _, files in os.walk(base_dir):
        path = os.path.join(root, "hourly_snapshots.jsonl")
        if not os.path.exists(path): continue
        
        out_path = os.path.join(root, "hourly_snapshots_relabel.jsonl")
        all_entries = []
        star_vote_counters = defaultdict(Counter)

        # 1. 파일 내의 모든 데이터를 읽으며 성급별 가장 적절한 라벨 투표
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    entry = json.loads(line)
                    all_entries.append(entry)
                    data = entry.get("data_by_key") or {}
                    for key, val in data.items():
                        star = _parse_star_from_key(key)
                        if star is not None:
                            # 이미 라벨이 붙어있더라도 확률로 다시 확인 (안정성 위해)
                            p = float(val.get("success_rate", 0.0))
                            label = _infer_catch_label_static(star, p)
                            star_vote_counters[star][label] += 1
                except: continue

        if not all_entries: continue

        # 2. 다수결로 해당 세션의 성급별 라벨 확정 (그래프 끊김 방지)
        stable_labels = {}
        for star in sorted(star_vote_counters.keys()):
            counter = star_vote_counters[star]
            label = counter.most_common(1)[0][0]
            stable_labels[star] = label

        # 3. 확정된 라벨로 데이터 일괄 재작성
        with open(out_path, "w", encoding="utf-8") as out:
            for entry in all_entries:
                data = entry.get("data_by_key") or {}
                new_data = {}
                for key, value in data.items():
                    star = _parse_star_from_key(key)
                    if star is not None and star in stable_labels:
                        label = stable_labels[star]
                        new_key = f"no_event_{label}_{star}"
                        new_data[new_key] = value
                    else:
                        new_data[key] = value
                
                entry["data_by_key_raw"] = data
                entry["data_by_key"] = new_data
                out.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        print(f"  [OK] {out_path} (Stable labels applied)")

    print("\nRelabeling complete.")

if __name__ == "__main__":
    relabel_sessions()
