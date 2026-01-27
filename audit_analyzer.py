import json
import os
import math
import statistics

def load_all_data(directory="audit_data"):
    all_records = []
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            with open(os.path.join(directory, filename), "r", encoding='utf-8') as f:
                data = json.load(f)
                is_catch = data["meta"]["star_catch"]
                for record in data["records"]:
                    record["_is_catch"] = is_catch
                    record["_filename"] = filename
                    all_records.append(record)
    return all_records

def analyze_by_star_range():
    records = load_all_data()
    
    # key: (star, is_catch)
    stats_map = {}
    
    for r in records:
        key = (r["star"], r["_is_catch"])
        if key not in stats_map:
            stats_map[key] = {
                "total_n": 0,
                "types": {
                    "success": {"obs": 0, "exp": 0.0, "var_sum": 0.0, "z_scores": []},
                    "fail":    {"obs": 0, "exp": 0.0, "var_sum": 0.0, "z_scores": []},
                    "boom":    {"obs": 0, "exp": 0.0, "var_sum": 0.0, "z_scores": []}
                }
            }
        
        s = stats_map[key]
        n_total = r["total_n"]
        s["total_n"] += n_total
        
        for t in ["success", "fail", "boom"]:
            p_target = r[f"{t}_p_target"]
            obs_n = r[f"{t}_n"]
            
            s["types"][t]["obs"] += obs_n
            s["types"][t]["exp"] += n_total * p_target
            # Variance of Binomial(n, p) is n*p*(1-p)
            s["types"][t]["var_sum"] += n_total * p_target * (1.0 - p_target)
            
            if n_total > 100:
                s["types"][t]["z_scores"].append(r[f"{t}_z_score"])

    header = f"{'STAR':<4} | {'CATCH':<5} | {'TOTAL_N':>12} | {'SUCC_Z':>8} | {'SUCC_VAR':>8} | {'FAIL_Z':>8} | {'BOOM_Z':>8}"
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))

    sorted_keys = sorted(stats_map.keys())
    
    for key in sorted_keys:
        star, is_catch = key
        data = stats_map[key]
        if data["total_n"] == 0: continue
        
        output_row = [f"{star:<4}", f"{'ON' if is_catch else 'OFF':<5}", f"{data['total_n']:>12,d}"]
        
        for t in ["success", "fail", "boom"]:
            t_data = data["types"][t]
            
            # Combined Z-score: (Total Obs - Total Exp) / sqrt(Total Var)
            if t_data["var_sum"] > 0:
                total_z = (t_data["obs"] - t_data["exp"]) / (t_data["var_sum"] ** 0.5)
            else:
                total_z = 0.0
            
            if t == "success":
                z_var = statistics.variance(t_data["z_scores"]) if len(t_data["z_scores"]) > 1 else 0.0
                output_row.extend([f"{total_z:>8.2f}", f"{z_var:>8.2f}"])
            else:
                output_row.append(f"{total_z:>8.2f}")
            
        print(" | ".join(output_row))

    print("=" * len(header))
    # ... (Guide remains the same)
    print("💡 분석 가이드:")
    print("  1. Z-SCORE: +/- 2.0을 넘어가면 통계적으로 희박한 확률 (운이 아주 좋거나 나쁨).")
    print("  2. Z-VAR (Z-Score Variance): 이론상 1.0이어야 함.")
    print("     - 0.5 미만: 확률 평탄화(Smoothing) 의심. 결과가 의도적으로 평균에 너무 수렴함.")
    print("     - 1.5 초과: 변동성이 너무 큼. 로직 오류나 숨겨진 보정치 가능성.")

if __name__ == "__main__":
    analyze_by_star_range()
