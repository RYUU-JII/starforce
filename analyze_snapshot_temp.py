import json
import os
from pathlib import Path

# Path to the latest session snapshot
session_path = Path(r"c:\Users\113ji\Desktop\Projects\스타포스시뮬레이터\crawler\sessions\20260131_014105\hourly_snapshots.jsonl")

def analyze_latest_snapshot():
    if not session_path.exists():
        print("데이터 파일을 찾을 수 없습니다.")
        return

    last_line = ""
    with open(session_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                last_line = line

    if not last_line:
        print("데이터가 비어있습니다.")
        return

    data = json.loads(last_line)
    timestamp = data.get("timestamp")
    stats = data.get("data_by_key", {})

    print(f"📊 최신 데이터 스냅샷 분석 ({timestamp})")
    print(f"{'='*80}")
    print(f"{'Star':<5} | {'Event':<10} | {'Catch':<5} | {'Try':<8} | {'Success':<8} | {'Real(%)':<8} | {'Exp(%)':<8} | {'Diff(%)':<8}")
    print(f"{'-'*80}")

    # Sort by star level
    sorted_keys = sorted(stats.keys(), key=lambda k: int(stats[k]['star']))

    for key in sorted_keys:
        item = stats[key]
        star = int(item['star'])
        
        # Only interest in 15+ or high volume
        if star < 15:
            continue

        raw_event = item.get('event', '')
        event = "None"
        if "샤이닝" in raw_event: event = "Shining"
        elif "미적용" in raw_event: event = "None"
        elif "파괴" in raw_event: event = "NoBoom"
        
        # Determine catch from key or item if possible (simplified logic)
        catch = "ON" if "_catch_on_" in key else "OFF"
        
        success = item['success_count']
        fail = item['fail_count']
        boom = item['boom_count']
        total = success + fail + boom
        
        if total == 0:
            continue

        real_prob = (success / total) * 100
        exp_prob = item.get('success_rate', 0) * 100
        diff = real_prob - exp_prob

        # Highlight significant deviations (simple heuristic)
        diff_str = f"{diff:+.2f}"
        
        print(f"{star:<5} | {event:<10} | {catch:<5} | {total:<8} | {success:<8} | {real_prob:<8.2f} | {exp_prob:<8.2f} | {diff_str:<8}")

        # Boom rate check for 15+
        if star >= 15 and boom > 0:
             real_boom = (boom / total) * 100
             exp_boom = item.get('boom_rate', 0) * 100
             if abs(real_boom - exp_boom) > 0.5:
                 print(f"      ↳ 💥 Boom Alert: Real {real_boom:.2f}% vs Exp {exp_boom:.2f}%")

    print(f"{'='*80}")

if __name__ == "__main__":
    analyze_latest_snapshot()
