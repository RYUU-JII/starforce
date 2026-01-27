import os
import json
import statistics
import math
from scipy import stats as scipy_stats

AUDIT_DB = []

# Approximate cost per attempt (in million Mesos) for level 200 items (representative)
STARFORCE_COST_MAP = {
    15: 18.0, 16: 22.0, 17: 43.0, 18: 51.0, 19: 58.0,
    20: 105.0, 21: 120.0, 22: 150.0, 23: 250.0, 24: 400.0
}

def load_audit_data(directory="audit_data"):
    all_records = []
    if not os.path.exists(directory):
        return []
        
    for filename in os.listdir(directory):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(directory, filename), "r", encoding='utf-8') as f:
                    data = json.load(f)
                    
                    meta = data.get("meta", {})
                    event_name = meta.get("event", "스타포스 이벤트 미적용").strip()
                    if not event_name or event_name == "" or event_name == "No Event":
                        event_name = "스타포스 이벤트 미적용"
                    
                    date_str = filename.split("_")[0]
                    is_catch = meta.get("star_catch", False)
                    
                    for r in data.get("records", []):
                        # Drop empty/placeholder rows (these dilute aggregates like heatmap/drift/monthly).
                        if r.get("total_n", 0) <= 0:
                            continue
                        flat_record = r.copy()
                        flat_record["_event"] = event_name
                        flat_record["_date"] = date_str
                        flat_record["_is_catch"] = is_catch
                        flat_record["_filename"] = filename
                        all_records.append(flat_record)
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                continue
    return all_records

def get_audit_db():
    global AUDIT_DB
    if not AUDIT_DB:
        AUDIT_DB = load_audit_data()
    return AUDIT_DB

def filter_audit_data(events=None, stars=None, catch_ops=None, min_samples=100):
    db = get_audit_db()
    filtered = []
    
    target_events = set(events) if events else None
    target_stars = set(stars) if stars else None
    
    target_catch = None
    if catch_ops:
        target_catch = set()
        if "ON" in catch_ops: target_catch.add(True)
        if "OFF" in catch_ops: target_catch.add(False)

    total_skipped = 0
    total_included = 0

    for r in db:
        if target_events and r["_event"] not in target_events: 
            total_skipped += 1
            continue
        if target_stars and r["star"] not in target_stars:
            total_skipped += 1
            continue
        if target_catch is not None and r["_is_catch"] not in target_catch: 
            total_skipped += 1
            continue
        if r["total_n"] < min_samples: 
            total_skipped += 1
            continue
        
        filtered.append(r)
        total_included += 1
        
    return filtered, total_included, total_skipped, len(db)

def calculate_stats(filtered_data):
    stats_map = {}
    
    for r in filtered_data:
        key = (r["star"], r["_is_catch"])
        if key not in stats_map:
            stats_map[key] = {
                "star": r["star"],
                "catch": "ON" if r["_is_catch"] else "OFF",
                "total_n": 0,
                "succ": {"obs": 0, "exp": 0.0, "var_exp": 0.0, "z_list": []},
                "fail": {"obs": 0, "exp": 0.0, "var_exp": 0.0, "z_list": []},
                "boom": {"obs": 0, "exp": 0.0, "var_exp": 0.0, "z_list": []},
            }
        
        entry = stats_map[key]
        n = r["total_n"]
        entry["total_n"] += n
        
        for t, prefix in [("succ", "success"), ("fail", "fail"), ("boom", "boom")]:
            target_p = r.get(f"{prefix}_p_target", 0.0)
            obs = r.get(f"{prefix}_n", 0)
            
            entry[t]["obs"] += obs
            entry[t]["exp"] += n * target_p
            # Theoretical variance N*p*(1-p)
            entry[t]["var_exp"] += n * target_p * (1.0 - target_p)
            
            if n > 100: 
                z = r.get(f"{prefix}_z_score", 0.0)
                entry[t]["z_list"].append(z)

    results = []
    for key, d in stats_map.items():
        total_n = int(d["total_n"])
        safe_total_n = total_n if total_n > 0 else 1
        row = {
            "star": d["star"],
            "catch": d["catch"],
            "total_n": total_n,
        }
        
        for t in ["succ", "fail", "boom"]:
            obs = int(d[t]["obs"])
            exp = float(d[t]["exp"])
            diff = float(obs - exp)
            t_var_exp = d[t]["var_exp"]
            if t_var_exp > 0:
                z_score = diff / (t_var_exp ** 0.5)
            else:
                z_score = 0.0
            
            # VAR Ratio: Observed Z Variance / Expected (1.0)
            z_list = d[t]["z_list"]
            var_n = len(z_list)
            if var_n > 1:
                z_observed_var = statistics.variance(z_list)
                var_ratio = float(z_observed_var)  # Expected Var(Z) ~= 1.0 under iid binomial model
                df = var_n - 1
                chi_stat = df * var_ratio
                var_p_under = float(scipy_stats.chi2.cdf(chi_stat, df))
                var_p_over = float(scipy_stats.chi2.sf(chi_stat, df))
                var_p_two = float(min(1.0, 2.0 * min(var_p_under, var_p_over)))
            else:
                var_ratio = 1.0
                var_p_under = 1.0
                var_p_over = 1.0
                var_p_two = 1.0
                
            # p-value for rare event detection
            p_val = float(scipy_stats.norm.sf(abs(z_score)) * 2)

            # Effect size (weighted by total_n across merged records)
            p_target = float(exp / safe_total_n)
            p_actual = float(obs / safe_total_n)
            delta_p = float(p_actual - p_target)
            delta_p_ci95 = float((1.96 * (t_var_exp ** 0.5) / safe_total_n) if t_var_exp > 0 else 0.0)
                
            row[f"{t}_z"] = round(z_score, 4)
            row[f"{t}_var_ratio"] = round(var_ratio, 4)
            row[f"{t}_p_val"] = p_val
            row[f"{t}_obs"] = obs
            row[f"{t}_exp"] = round(exp, 2)
            row[f"{t}_diff"] = round(diff, 2)
            row[f"{t}_p_target"] = round(p_target, 8)
            row[f"{t}_p_actual"] = round(p_actual, 8)
            row[f"{t}_delta_p"] = round(delta_p, 8)
            row[f"{t}_delta_p_ci95"] = round(delta_p_ci95, 8)
            row[f"{t}_var_n"] = var_n
            row[f"{t}_var_p_under"] = var_p_under
            row[f"{t}_var_p_over"] = var_p_over
            row[f"{t}_var_p_two"] = var_p_two
            
        results.append(row)
    
    results.sort(key=lambda x: (x["star"], x["catch"]))
    return results

def get_heatmap_stats(filtered_db=None):
    """Returns combined Z-score per (star, date)."""
    db = filtered_db if filtered_db is not None else get_audit_db()
    heatmap_data = {}
    
    for r in db:
        key = (r["star"], r["_date"])
        if key not in heatmap_data:
            heatmap_data[key] = {
                "star": r["star"],
                "date": r["_date"],
                "total_n": 0,
                "succ_obs": 0,
                "succ_exp": 0.0,
                "succ_var": 0.0,
                "boom_obs": 0,
                "boom_exp": 0.0,
                "boom_var": 0.0
            }
        
        entry = heatmap_data[key]
        n = int(r.get("total_n", 0))
        if n <= 0:
            continue

        # Success
        p_s = float(r.get("success_p_target", 0.0))
        entry["succ_obs"] += int(r.get("success_n", 0))
        entry["succ_exp"] += n * p_s
        entry["succ_var"] += n * p_s * (1.0 - p_s)

        # Boom
        p_b = float(r.get("boom_p_target", 0.0))
        entry["boom_obs"] += int(r.get("boom_n", 0))
        entry["boom_exp"] += n * p_b
        entry["boom_var"] += n * p_b * (1.0 - p_b)

        entry["total_n"] += n
    
    results = []
    for entry in heatmap_data.values():
        succ_z = (entry["succ_obs"] - entry["succ_exp"]) / (entry["succ_var"] ** 0.5) if entry["succ_var"] > 0 else 0.0
        boom_z = (entry["boom_obs"] - entry["boom_exp"]) / (entry["boom_var"] ** 0.5) if entry["boom_var"] > 0 else 0.0
        
        results.append({
            "star": entry["star"],
            "date": entry["date"],
            "succ_z": round(float(succ_z), 2),
            "boom_z": round(float(boom_z), 2),
            "total_n": int(entry["total_n"])
        })
            
    return results

def get_drift_stats(filtered_db=None):
    db = filtered_db if filtered_db is not None else get_audit_db()
    date_stats = {}
    
    for r in db:
        date = r["_date"]
        if date not in date_stats:
            date_stats[date] = {
                "succ_diff": 0.0,
                "succ_var": 0.0,
                "succ_error": 0.0,
                "meso_loss": 0.0
            }

        n = int(r.get("total_n", 0))
        if n <= 0:
            continue

        act = int(r.get("success_n", 0))
        p = float(r.get("success_p_target", 0.0))
        exp = n * p
        var = n * p * (1.0 - p)
        err = act - exp

        date_stats[date]["succ_diff"] += err
        date_stats[date]["succ_var"] += var
        date_stats[date]["succ_error"] += err

        star = r.get("star", 0)
        cost_per = STARFORCE_COST_MAP.get(star, 10.0) # Default 10M if unknown
        date_stats[date]["meso_loss"] += err * cost_per
    
    results = []
    cumulative_z = 0.0
    cumulative_error = 0.0
    cumulative_meso = 0.0
    
    for date in sorted(date_stats.keys()):
        stats = date_stats[date]
        day_z = (stats["succ_diff"] / (stats["succ_var"] ** 0.5)) if stats["succ_var"] > 0 else 0.0
        cumulative_z += day_z
        cumulative_error += stats["succ_error"]
        cumulative_meso += stats["meso_loss"]
        
        results.append({
            "date": date,
            "avg_succ_z": round(float(day_z), 2),
            "cumulative_succ_z": round(cumulative_z, 2),
            "cumulative_error": round(cumulative_error, 1),
            "cumulative_meso": round(cumulative_meso, 1)
        })
    return results

def get_monthly_stats(filtered_db=None):
    db = filtered_db if filtered_db is not None else get_audit_db()
    monthly_stats = {}
    
    for r in db:
        date_str = r["_date"]
        if len(date_str) >= 6:
            yyyymm = date_str[:6]
            formatted_month = f"{yyyymm[:4]}-{yyyymm[4:]}"
        else:
            continue
            
        if formatted_month not in monthly_stats:
            monthly_stats[formatted_month] = {
                "succ_obs": 0, "succ_exp": 0.0, "succ_var": 0.0,
                "boom_obs": 0, "boom_exp": 0.0, "boom_var": 0.0,
            }

        n = int(r.get("total_n", 0))
        if n <= 0:
            continue

        p_s = float(r.get("success_p_target", 0.0))
        monthly_stats[formatted_month]["succ_obs"] += int(r.get("success_n", 0))
        monthly_stats[formatted_month]["succ_exp"] += n * p_s
        monthly_stats[formatted_month]["succ_var"] += n * p_s * (1.0 - p_s)

        p_b = float(r.get("boom_p_target", 0.0))
        monthly_stats[formatted_month]["boom_obs"] += int(r.get("boom_n", 0))
        monthly_stats[formatted_month]["boom_exp"] += n * p_b
        monthly_stats[formatted_month]["boom_var"] += n * p_b * (1.0 - p_b)
    
    results = []
    for month in sorted(monthly_stats.keys()):
        stats = monthly_stats[month]
        succ_z = (stats["succ_obs"] - stats["succ_exp"]) / (stats["succ_var"] ** 0.5) if stats["succ_var"] > 0 else 0.0
        boom_z = (stats["boom_obs"] - stats["boom_exp"]) / (stats["boom_var"] ** 0.5) if stats["boom_var"] > 0 else 0.0
        results.append({
            "month": month,
            "total_succ_z": round(float(succ_z), 2),
            "total_boom_z": round(float(boom_z), 2)
        })
    return results

def get_event_comparison_stats():
    db = get_audit_db()
    
    event_stats = {"succ_z_sum": 0.0, "boom_z_sum": 0.0, "total_n": 0, "count": 0}
    no_event_stats = {"succ_z_sum": 0.0, "boom_z_sum": 0.0, "total_n": 0, "count": 0}
    
    for r in db:
        is_event = "이벤트 미적용" not in r["_event"] and "no_event" not in r["_event"] and "No Event" not in r["_event"]
        target = event_stats if is_event else no_event_stats
        
        target["succ_z_sum"] += r.get("success_z_score", 0.0)
        target["boom_z_sum"] += r.get("boom_z_score", 0.0)
        target["total_n"] += r.get("total_n", 0)
        target["count"] += 1
    
    return {
        "event": {
            "avg_succ_z": round(event_stats["succ_z_sum"] / event_stats["count"], 3) if event_stats["count"] else 0,
            "avg_boom_z": round(event_stats["boom_z_sum"] / event_stats["count"], 3) if event_stats["count"] else 0,
            "total_n": event_stats["total_n"],
            "record_count": event_stats["count"]
        },
        "no_event": {
            "avg_succ_z": round(no_event_stats["succ_z_sum"] / no_event_stats["count"], 3) if no_event_stats["count"] else 0,
            "avg_boom_z": round(no_event_stats["boom_z_sum"] / no_event_stats["count"], 3) if no_event_stats["count"] else 0,
            "total_n": no_event_stats["total_n"],
            "record_count": no_event_stats["count"]
        }
    }

def get_event_deception_index(filtered_db=None):
    db = filtered_db if filtered_db is not None else get_audit_db()
    full_db = get_audit_db()
    
    MIN_SAMPLES_FOR_VALID_METRIC = 1000  # Minimum total_n across records to consider valid
    MIN_RECORDS_FOR_GROUP = 3  # Minimum number of records to form a valid group
    
    # Baseline: No-Event data
    no_evt_map = {}
    no_evt_keys = list(set([r["_event"] for r in full_db if any(x in r["_event"] for x in ["미적용", "no_event", "No Event"])]))
    
    for r in full_db:
        if r["_event"] not in no_evt_keys: continue
        star = r["star"]
        if star < 12: continue
        if r.get("total_n", 0) < 100: continue  # Skip low-N records
        if star not in no_evt_map: no_evt_map[star] = {"actual":[], "target":[], "z_list":[], "n_sum": 0}
        no_evt_map[star]["actual"].append(r.get("success_p_actual", 0))
        no_evt_map[star]["target"].append(r.get("success_p_target", 0))
        no_evt_map[star]["z_list"].append(r.get("success_z_score", 0))
        no_evt_map[star]["n_sum"] += r.get("total_n", 0)

    def calc_metrics(data_map):
        all_actuals = []
        all_targets = []
        all_z_vars = []
        total_n = 0
        record_count = 0
        
        for star, vals in data_map.items():
            all_actuals.extend(vals["actual"])
            all_targets.extend(vals["target"])
            total_n += vals.get("n_sum", 0)
            record_count += len(vals["actual"])
            if len(vals["z_list"]) > 1:
                all_z_vars.append(statistics.variance(vals["z_list"]))
        
        # Safeguard: Not enough data
        if total_n < MIN_SAMPLES_FOR_VALID_METRIC or record_count < MIN_RECORDS_FOR_GROUP:
            return None, None, total_n, record_count
        
        avg_dev = 0.0
        if all_targets:
            devs = [(a - t) / t for a, t in zip(all_actuals, all_targets) if t > 0]
            avg_dev = sum(devs) / len(devs) if devs else 0.0
            
        avg_var = sum(all_z_vars) / len(all_z_vars) if all_z_vars else 1.0
        return avg_dev, avg_var, total_n, record_count

    base_dev, base_var, base_n, base_count = calc_metrics(no_evt_map)
    if base_dev is None:
        base_dev, base_var = 0.0, 1.0  # Fallback for baseline

    # Filtered Data analysis
    target_grouped = {}
    for r in db:
        evt = r["_event"]
        star = r["star"]
        if star < 12: continue
        if evt in no_evt_keys: continue
        if r.get("total_n", 0) < 100: continue  # Skip low-N records
        
        if evt not in target_grouped: target_grouped[evt] = {}
        if star not in target_grouped[evt]:
            target_grouped[evt][star] = {"actual": [], "target": [], "z_list": [], "n_sum": 0}
            
        entry = target_grouped[evt][star]
        entry["actual"].append(r.get("success_p_actual", 0))
        entry["target"].append(r.get("success_p_target", 0))
        entry["z_list"].append(r.get("success_z_score", 0))
        entry["n_sum"] += r.get("total_n", 0)

    # Star Groups
    groups = {
        "Low (12-16성)": [12, 13, 14, 15, 16],
        "Mid (17-21성)": [17, 18, 19, 20, 21],
        "High (22-25성)": [22, 23, 24, 25]
    }
    
    star_group_results = {}
    for g_name, star_list in groups.items():
        g_evt_map = {}
        for evt, stars in target_grouped.items():
            for s in star_list:
                if s in stars:
                    if s not in g_evt_map: g_evt_map[s] = {"actual":[], "target":[], "z_list":[], "n_sum": 0}
                    g_evt_map[s]["actual"].extend(stars[s]["actual"])
                    g_evt_map[s]["target"].extend(stars[s]["target"])
                    g_evt_map[s]["z_list"].extend(stars[s]["z_list"])
                    g_evt_map[s]["n_sum"] += stars[s]["n_sum"]
        
        g_base_map = {s: no_evt_map[s] for s in star_list if s in no_evt_map}
        
        evt_dev, evt_var, evt_n, evt_cnt = calc_metrics(g_evt_map)
        b_dev, b_var, _, _ = calc_metrics(g_base_map)
        
        if evt_dev is None or b_dev is None:
            star_group_results[g_name] = {"deception": 0.0, "var_suppression": 1.0, "insufficient_data": True}
        else:
            star_group_results[g_name] = {
                "deception": round((b_dev - evt_dev) * 100, 2),
                "var_suppression": round(b_var / evt_var if evt_var > 0 else 1.0, 2),
                "insufficient_data": False
            }

    # Individual Events
    event_results = []
    for evt, stars in target_grouped.items():
        e_dev, e_var, e_n, e_cnt = calc_metrics(stars)
        if e_dev is None:
            continue  # Skip events with insufficient data

        # Calculate a localized baseline for the same set of stars
        e_stars_list = list(stars.keys())
        e_base_map = {s: no_evt_map[s] for s in e_stars_list if s in no_evt_map}
        b_dev_local, b_var_local, _, _ = calc_metrics(e_base_map)
        
        # Fallback to global baseline values if local one is insufficient
        final_b_dev = b_dev_local if b_dev_local is not None else base_dev
        final_b_var = b_var_local if b_var_local is not None else base_var

        event_results.append({
            "name": evt,
            "deception": round((final_b_dev - e_dev) * 100, 2),
            "var_suppression": round(final_b_var / e_var if e_var > 0 else 1.0, 2)
        })

    # Global Deception
    global_evt_map = {}
    for evt, stars in target_grouped.items():
        for s, vals in stars.items():
            if s not in global_evt_map: global_evt_map[s] = {"actual":[], "target":[], "z_list":[], "n_sum": 0}
            global_evt_map[s]["actual"].extend(vals["actual"])
            global_evt_map[s]["target"].extend(vals["target"])
            global_evt_map[s]["z_list"].extend(vals["z_list"])
            global_evt_map[s]["n_sum"] += vals["n_sum"]
            
    global_evt_dev, global_evt_var, global_n, global_cnt = calc_metrics(global_evt_map)
    
    if global_evt_dev is None:
        return {
            "deception_index": 0.0,
            "event_avg_deviation": 0.0,
            "no_event_avg_deviation": round(base_dev * 100, 2),
            "star_groups": star_group_results,
            "events": [],
            "interpretation": "Insufficient Data for Analysis",
            "insufficient_data": True
        }
    
    global_deception = (base_dev - global_evt_dev) * 100

    return {
        "deception_index": round(global_deception, 2),
        "event_avg_deviation": round(global_evt_dev * 100, 2),
        "no_event_avg_deviation": round(base_dev * 100, 2),
        "star_groups": star_group_results,
        "events": sorted(event_results, key=lambda x: x["deception"], reverse=True),
        "interpretation": "Strong Evidence of Bias" if global_deception > 0.5 else "Low Global Bias",
        "insufficient_data": False
    }


def get_event_dates(filtered_db=None):
    db = filtered_db if filtered_db is not None else get_audit_db()
    date_events = {}
    
    for r in db:
        date = r["_date"]
        event = r["_event"]
        
        if date not in date_events:
            date_events[date] = set()
        date_events[date].add(event)
    
    results = []
    for date in sorted(date_events.keys()):
        events = list(date_events[date])
        is_event = False
        real_events = []
        for e in events:
            if "이벤트 미적용" not in e and "no_event" not in e and "No Event" not in e:
                is_event = True
                real_events.append(e)
        
        results.append({
            "date": date,
            "events": real_events if real_events else ["이벤트 없음"],
            "is_event_period": is_event
        })
    
    return results

def get_season_contrast_stats(split_date=None, filtered_db=None):
    db = filtered_db if filtered_db is not None else get_audit_db()
    
    before_data = {"succ_diff": 0.0, "succ_var": 0.0, "total_n": 0, "actual_succ": 0, "exp_succ": 0.0}
    after_data = {"succ_diff": 0.0, "succ_var": 0.0, "total_n": 0, "actual_succ": 0, "exp_succ": 0.0}
    
    # Estimate cost factor from starforce map (approx average)
    avg_cost = 10.0 # Default fallback
    if STARFORCE_COST_MAP:
        avg_cost = sum(STARFORCE_COST_MAP.values()) / len(STARFORCE_COST_MAP)

    for r in db:
        date_str = r["_date"]
        
        target = None
        if split_date:
            if date_str < split_date:
                target = before_data
            else:
                target = after_data
        else:
            # Fallback to original logic if no split_date (though UI should always provide one now)
            # Keeping legacy logic as default for safety
            month = int(date_str[4:6])
            if 5 <= month <= 9:
                target = before_data
            elif month >= 10 or month <= 1:
                target = after_data
        
        if target:
            n = int(r.get("total_n", 0))
            if n <= 0:
                continue
            act = int(r.get("success_n", 0))
            p = float(r.get("success_p_target", 0.0))
            exp = n * p
            var = n * p * (1.0 - p)

            target["succ_diff"] += act - exp
            target["succ_var"] += var
            target["total_n"] += n
            target["actual_succ"] += act
            target["exp_succ"] += exp
        
    def summarize(tag, d):
        if d["total_n"] <= 0:
            return {"period": tag, "avg_z": 0, "total_n": 0, "error_count": 0, "deception_index": 0}
        avg_z = (d["succ_diff"] / (d["succ_var"] ** 0.5)) if d["succ_var"] > 0 else 0.0
        err = d["actual_succ"] - d["exp_succ"]
        return {
            "period": tag,
            "avg_z": round(float(avg_z), 3),
            "total_n": d["total_n"],
            "error_count": round(err, 1),
            "deception_index": round(-err / d["exp_succ"] * 100, 3) if d["exp_succ"] > 0 else 0
        }
        
    if split_date:
        tag_before = f"{split_date} 이전 (Period A)"
        tag_after = f"{split_date} 이후 (Period B)"
    else:
        tag_before = "5월~9월 (성수기)"
        tag_after = "10월~1월 (비성수기)"

    return {
        "before": summarize(tag_before, before_data),
        "after": summarize(tag_after, after_data),
        "cost_factor": 0.4 # Keeping the 0.4 multiplier for Meso calculation as per original logic, or make it dynamic if needed
    }
