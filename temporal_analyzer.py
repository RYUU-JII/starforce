import json
import os
import math
import statistics
import numpy as np

def load_all_data(base_dir="crawler/sessions"):
    all_entries = []
    print(f"Searching in: {os.path.abspath(base_dir)}")
    found_files = 0
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file == "hourly_snapshots.jsonl":
                path = os.path.join(root, file)
                found_files += 1
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line: continue
                        try:
                            entry = json.loads(line)
                            if entry.get("data_by_key"):
                                all_entries.append(entry)
                        except: continue
    
    # Sort ALL entries by timestamp globally
    # This treats data across sessions as a single timeline
    all_entries.sort(key=lambda x: x["timestamp"])
    print(f"Aggregated {len(all_entries)} snapshots from {found_files} files.")
    return all_entries

def analyze_temporal_iid(base_dir="crawler/sessions"):
    raw_data = load_all_data(base_dir)
    if not raw_data:
        print("No valid data found.")
        return

    # key -> list of hourly deltas
    deltas_map = {}

    prev_data = None
    for entry in raw_data:
        curr_ts = entry["timestamp"]
        curr_data = entry["data_by_key"]
        
        if not curr_data: continue
            
        if prev_data:
            for key, curr_vals in curr_data.items():
                if key not in prev_data: continue
                    
                prev_vals = prev_data[key]
                
                # Check for MAINTENANCE RESET
                # If current cumulative counts are lower than previous, 
                # it means the API count reset (likely maintenance).
                # In that case, we treat curr_vals as the first hour's increment.
                if curr_vals["success_count"] < prev_vals["success_count"]:
                    # Reset detected! The delta is simply the current value.
                    ds = curr_vals["success_count"]
                    df = curr_vals["fail_count"]
                    db = curr_vals["boom_count"]
                    is_reset = True
                else:
                    # Normal cumulative delta
                    ds = curr_vals["success_count"] - prev_vals["success_count"]
                    df = curr_vals["fail_count"] - prev_vals["fail_count"]
                    db = curr_vals["boom_count"] - prev_vals["boom_count"]
                    is_reset = False
                    
                dn = ds + df + db
                if dn <= 0: continue
                
                p_s = curr_vals["success_rate"]
                
                if key not in deltas_map:
                    deltas_map[key] = []
                
                deltas_map[key].append({
                    "n": dn,
                    "s_n": ds,
                    "p_s": p_s,
                    "timestamp": curr_ts,
                    "is_reset": is_reset
                })
        
        prev_data = curr_data

    # Now Analyze each key
    import re
    
    header = f"{'KEY/SEGMENT':<25} | {'HOURS':<5} | {'TOTAL_N':>10} | {'Z_VAR':>8} | {'AUTOCORR':>10}"
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))

    # Segment tracking: 12-22 stars (High Stakes)
    high_stakes_z = []
    high_stakes_n = 0

    for key in sorted(deltas_map.keys()):
        # Extract star level
        star_match = re.search(r'_(\d+)$', key)
        star = int(star_match.group(1)) if star_match else -1
        
        is_target_range = 12 <= star <= 22
        
        deltas = deltas_map[key]
        if len(deltas) < 2:
            continue
            
        z_scores = []
        total_n = 0
        
        for d in deltas:
            n = d["n"]
            p = d["p_s"]
            obs_s = d["s_n"]
            exp_s = n * p
            
            if n > 0 and 0 < p < 1:
                std = math.sqrt(n * p * (1 - p))
                z = (obs_s - exp_s) / std
                z_scores.append(z)
                total_n += n
                
                if is_target_range:
                    high_stakes_z.append(z)
                    high_stakes_n += n

        if not z_scores:
            continue
            
        # 1. Z-Score Variance
        z_var = statistics.variance(z_scores) if len(z_scores) > 1 else 0.0
        
        # 2. Lag-1 Autocorr
        if len(z_scores) > 5:
            a = np.array(z_scores)
            autocorr = np.corrcoef(a[:-1], a[1:])[0, 1]
        else:
            autocorr = float('nan')

        # Highlight target range
        row_label = f"{key}"
        if is_target_range:
            row_label = f"> {key}"
            
        print(f"{row_label:<25} | {len(z_scores):<5} | {total_n:>10,d} | {z_var:>8.2f} | {autocorr:>10.2f}")

    print("-" * len(header))
    # Aggregate Segment Analysis
    if high_stakes_z:
        var_h = statistics.variance(high_stakes_z) if len(high_stakes_z) > 1 else 0.0
        # For aggregate autocorr, we use the concatenated z-scores (approximate)
        if len(high_stakes_z) > 5:
            a_h = np.array(high_stakes_z)
            autocorr_h = np.corrcoef(a_h[:-1], a_h[1:])[0, 1]
        else:
            autocorr_h = float('nan')
        print(f"{'SEGMENT: 12-22★':<25} | {'-':<5} | {high_stakes_n:>10,d} | {var_h:>8.2f} | {autocorr_h:>10.2f}")

    print("=" * len(header))
    
    # 3. Time-Series Trace for specific stars (Visualization)
    print("\n[Hourly Luck Trace: 17★ & 18★]")
    print(f"{'TIMESTAMP':<20} | {'STAR':<5} | {'N':>8} | {'Z-SCORE':>8} | {'LUCK'}")
    print("-" * 55)
    
    for target in ["no_event_catch_off_17", "no_event_catch_off_18"]:
        if target in deltas_map:
            for d in deltas_map[target]:
                n = d["n"]
                p = d["p_s"]
                obs_s = d["s_n"]
                exp_s = n * p
                z = (obs_s - exp_s) / math.sqrt(n * p * (1 - p)) if n > 0 else 0
                
                luck = "!!!" if z > 2 else "++" if z > 1 else "--" if z < -1 else "!!!" if z < -2 else "ok"
                ts_short = d["timestamp"].split(" ")[1] # Just time
                print(f"{d['timestamp']:<20} | {target[-3:]:>5} | {n:>8,d} | {z:>8.2f} | {luck}")
            print("-" * 55)

    print("\n[Analysis Guide]")
    print("  1. Z_VAR < 1.0: Results are 'too consistent'. Potential Global Deck or Smoothing.")
    print("  2. Z_VAR > 1.0: Results are 'volatile'. Potential outliers or Streakiness.")
    print("  3. AUTOCORR < 0: Negative correlation. A good hour tends to be followed by a bad hour (Rebalancing).")
    print("  4. AUTOCORR > 0: Positive correlation. Luck 'sticks' (Streakiness).")

if __name__ == "__main__":
    import sys
    # For Windows console or redirection
    import io
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    # Check crawler/sessions by default
    base_path = "crawler/sessions"
    if len(sys.argv) > 1:
        base_path = sys.argv[1]
    
    if os.path.isfile(base_path):
        # If a single file is provided, just analyze that
        def load_single_file(path):
            all_entries = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        entry = json.loads(line)
                        if entry.get("data_by_key"):
                            all_entries.append(entry)
                    except: continue
            all_entries.sort(key=lambda x: x["timestamp"])
            return all_entries
        
        # Override analyze_temporal_iid behavior for single file
        data = load_single_file(base_path)
        if not data:
            print("No valid data found in file.")
        else:
            # Re-implement the analysis logic for this data
            # Or just pass the data (requires refactoring analyzer)
            # Simpler: just set base_path to parent dir if it's a file for os.walk
            base_path = os.path.dirname(base_path)
            analyze_temporal_iid(base_path)
    else:
        analyze_temporal_iid(base_path)
