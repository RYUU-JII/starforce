from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from collections import deque
import statistics
import time
import os
import json

app = FastAPI()

app.mount("/audit", StaticFiles(directory="audit", html=True), name="audit")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROB = {
    12: (0.40, 0.60, 0.00), 13: (0.35, 0.65, 0.00), 14: (0.30, 0.70, 0.00),
    15: (0.30, 0.679, 0.021), 16: (0.30, 0.679, 0.021), 17: (0.15, 0.782, 0.068),
    18: (0.15, 0.782, 0.068), 19: (0.15, 0.765, 0.085), 20: (0.30, 0.595, 0.105),
    21: (0.15, 0.7225, 0.1275),
}

S, F, B = 0, 1, 2

COST_TABLE = {
    12: 34300000,
    13: 55000000,
    14: 95000000,
    15: 72400000, 
    16: 100000000, 
    17: 130400000,
    18: 324700000,
    19: 584300000, 
    20: 148000000, 
    21: 272200000  
}

class DeckManager:

    def __init__(self, prob_table, chunk_size=5000000, mode='random', block_intensity=40):
        self.decks = {}
        self.prob = prob_table
        self.chunk_size = chunk_size
        self.mode = mode
        self.block_intensity = max(1, min(block_intensity, 100))
        self.shared_cursors = {level: 0 for level in prob_table} 
        
        print(f"Initializing DeckManager ({mode}) with size {chunk_size}...")
        for level in prob_table:
            self.decks[level] = self._create_new_deck(level)
        print("Deck initialization complete.")
            
    def _create_new_deck(self, level):
        s_prob, f_prob, b_prob = self.prob[level]
        s_cnt = int(round(self.chunk_size * s_prob))
        b_cnt = int(round(self.chunk_size * b_prob))
        f_cnt = self.chunk_size - s_cnt - b_cnt
        total = s_cnt + b_cnt + f_cnt
        if total != self.chunk_size:
            f_cnt += (self.chunk_size - total)
            
        base = np.concatenate([np.full(s_cnt, S), np.full(f_cnt, F), np.full(b_cnt, B)])
        
        if self.mode == 'random':
            np.random.shuffle(base)
            return base 
            
        elif self.mode == 'rigged':
            bad_tokens = np.concatenate([np.full(f_cnt, F), np.full(b_cnt, B)])
            np.random.shuffle(bad_tokens)
            
            avg_block = self.block_intensity
            s_blocks = []
            remaining = s_cnt
            
            while remaining > 0:
                block_size = int(np.abs(np.random.normal(avg_block, avg_block/3)))
                block_size = max(1, min(block_size, remaining))
                s_blocks.append(np.full(block_size, S))
                remaining -= block_size
            
            bad_blocks = []
            remaining = len(bad_tokens)
            start_idx = 0
            
            while remaining > 0:
                block_size = int(np.abs(np.random.normal(avg_block * 1.5, avg_block/2)))
                block_size = max(1, min(block_size, remaining))
                bad_blocks.append(bad_tokens[start_idx:start_idx + block_size])
                start_idx += block_size
                remaining -= block_size
            
            all_blocks = s_blocks + bad_blocks
            import random
            random.shuffle(all_blocks)
            
            if all_blocks:
                result = np.concatenate(all_blocks)
                return result
            else:
                return base

    def get_draw_fn(self, independent=False):
        decks = self.decks
        size = self.chunk_size
        
        if independent:
            cursors = {lvl: np.random.randint(0, size) for lvl in decks}
            
            def draw(level):
                if level not in decks: return S
                idx = cursors[level]
                val = decks[level][idx]
                cursors[level] = (idx + 1) % size
                return val
            return draw
            
        else:
            cursors = self.shared_cursors
            
            def draw(level):
                if level not in decks: return S
                idx = cursors[level]
                val = decks[level][idx]
                cursors[level] = (idx + 1) % size
                return val
            return draw

def get_cost_200(level):
    return COST_TABLE.get(level, 0)

def simulate_detailed(draw_fn):
    curr = 12
    clicks = 0
    total_cost = 0
    lvl_stats = np.zeros((10, 4), dtype=int)
    streaks = []
    curr_type = -1
    curr_len = 0
    
    while curr < 22 and clicks < 5000:
        clicks += 1
        idx = curr - 12
        
        total_cost += get_cost_200(curr)
        
        if 0 <= idx < 10:
            r = draw_fn(curr)
            lvl_stats[idx][0] += 1
            if r == S:
                lvl_stats[idx][1] += 1
                curr += 1
            elif r == F: 
                lvl_stats[idx][2] += 1
            elif r == B: 
                lvl_stats[idx][3] += 1
                curr = 12
        else:
            r = draw_fn(curr)
            if r == S:
                curr += 1
        
        type_code = 0 if (r == S) else 1
        if type_code == curr_type:
            curr_len += 1
        else:
            if curr_len > 0:
                streaks.append(curr_len if curr_type == 0 else -curr_len)
            curr_type, curr_len = type_code, 1
    
    if curr_len > 0:
        streaks.append(curr_len if curr_type == 0 else -curr_len)
    
    return {"streaks": streaks, "lvl_stats": lvl_stats, "cost": total_cost}

class CompareRequest(BaseModel):
    total_tries: int = 100
    block_intensity: int = 40
    independent_deck: bool = True

def aggregate(results):
    if not results:
        return {
            "s_var": 0.0, "f_var": 0.0,
            "max_f": 0, "max_s": 0,
            "level_stats": {},
            "histogram": [], "s_histogram": [], "m_histogram": [],
            "avg_cost": 0
        }
    
    total_lvl_stats = np.zeros((10, 4), dtype=int)
    costs = []
    for r in results:
        total_lvl_stats += r['lvl_stats']
        costs.append(r.get('cost', 0))
    
    level_table = {}
    for i in range(10):
        level = 12 + i
        row = total_lvl_stats[i]
        tries = int(row[0])
        safe_tries = tries if tries > 0 else 1
        
        level_table[str(level)] = {
            "try": tries,
            "s": int(row[1]), "f": int(row[2]), "b": int(row[3]),
            "success_rate": float(row[1]) / safe_tries * 100 if safe_tries > 0 else 0,
            "fail_rate": float(row[2]) / safe_tries * 100 if safe_tries > 0 else 0,
            "boom_rate": float(row[3]) / safe_tries * 100 if safe_tries > 0 else 0
        }

    all_streaks = []
    for r in results:
        all_streaks.extend(r['streaks'])
    
    s_streaks = [s for s in all_streaks if s > 0]
    f_streaks = [abs(s) for s in all_streaks if s < 0]
    
    s_var = 0.0
    f_var = 0.0
    
    if len(s_streaks) > 1:
        s_var = float(np.var(s_streaks, ddof=1))
    if len(f_streaks) > 1:
        f_var = float(np.var(f_streaks, ddof=1))
    
    histogram = []
    if f_streaks:
        unique, counts = np.unique(f_streaks, return_counts=True)
        histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]

    s_histogram = []
    if s_streaks:
        unique, counts = np.unique(s_streaks, return_counts=True)
        s_histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]
        
    m_histogram = []
    if costs:
        cost_billions = [int(c / 1000000000) for c in costs]
        unique, counts = np.unique(cost_billions, return_counts=True)
        m_histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]
    
    return {
        "s_var": s_var,
        "f_var": f_var,
        "max_f": int(max(f_streaks)) if f_streaks else 0,
        "max_s": int(max(s_streaks)) if s_streaks else 0,
        "level_stats": level_table,
        "histogram": histogram,
        "s_histogram": s_histogram,
        "m_histogram": m_histogram,
        "avg_cost": float(statistics.mean(costs)) if costs else 0.0,
        "cost_var": float(statistics.variance(costs)) if len(costs) > 1 else 0.0
    }

@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("index.html", "r", encoding='utf-8') as f:
        return f.read()

@app.post("/compare")
def run_compare(req: CompareRequest):
    start_time = time.time()
    
    total_tries = min(req.total_tries, 100000)
    
    fair_manager = DeckManager(PROB, chunk_size=1000000, mode='random')
    fair_draw_fn = fair_manager.get_draw_fn(independent=False)
    
    fair_results = []
    for i in range(total_tries):
        fair_results.append(simulate_detailed(fair_draw_fn))
    
    fair_time = time.time()
    print(f"Fair simulation time: {fair_time - start_time:.2f}s")
    
    rigged_manager = DeckManager(PROB, chunk_size=1000000, mode='rigged', block_intensity=req.block_intensity)
    rigged_results = []
    
    if req.independent_deck:
        for i in range(total_tries):
            draw_fn = rigged_manager.get_draw_fn(independent=True)
            rigged_results.append(simulate_detailed(draw_fn))
    else:
        shared_draw_fn = rigged_manager.get_draw_fn(independent=False)
        for i in range(total_tries):
             rigged_results.append(simulate_detailed(shared_draw_fn))
    
    rigged_time = time.time()
    print(f"Rigged simulation time: {rigged_time - fair_time:.2f}s")
    
    fair_res = aggregate(fair_results)
    rigged_res = aggregate(rigged_results)
    
    total_time = time.time() - start_time
    print(f"Total time: {total_time:.2f}s")
    
    return {
        "fair": fair_res,
        "rigged": rigged_res,
        "theory": {str(k): v for k, v in PROB.items()},
        "simulation_count": total_tries,
        "execution_time": float(total_time)
    }

# --- Audit Backend Logic ---

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
                    event_name = meta.get("event", "No Event").strip()
                    if not event_name or event_name == "":
                        event_name = "No Event"
                    
                    date_str = filename.split("_")[0]
                    is_catch = meta.get("star_catch", False)
                    
                    for r in data.get("records", []):
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

AUDIT_DB = load_audit_data()

class AuditQuery(BaseModel):
    events: list[str] = []
    stars: list[int] = []
    catch_ops: list[str] = []
    min_samples: int = 100

@app.get("/api/audit/meta")
def get_audit_metadata():
    global AUDIT_DB
    if not AUDIT_DB:
        AUDIT_DB = load_audit_data()
        
    events = sorted(list(set(r["_event"] for r in AUDIT_DB)))
    stars = sorted(list(set(r["star"] for r in AUDIT_DB)))
    dates = sorted(list(set(r["_date"] for r in AUDIT_DB)))
    
    return {
        "events": events,
        "stars": stars,
        "dates": dates,
        "total_records": len(AUDIT_DB)
    }

@app.post("/api/audit/query")
def query_audit_data(q: AuditQuery):
    filtered = []
    
    target_events = set(q.events) if q.events else None
    target_stars = set(q.stars) if q.stars else None
    
    target_catch = None
    if q.catch_ops:
        target_catch = set()
        if "ON" in q.catch_ops: target_catch.add(True)
        if "OFF" in q.catch_ops: target_catch.add(False)

    total_skipped = 0
    total_included = 0

    for r in AUDIT_DB:
        if target_events and r["_event"] not in target_events: 
            total_skipped += 1
            continue
        if target_stars and r["star"] not in target_stars:
            total_skipped += 1
            continue
        if target_catch is not None and r["_is_catch"] not in target_catch: 
            total_skipped += 1
            continue
        if r["total_n"] < q.min_samples: 
            total_skipped += 1
            continue
        
        filtered.append(r)
        total_included += 1

    stats_map = {}
    
    for r in filtered:
        key = (r["star"], r["_is_catch"])
        if key not in stats_map:
            stats_map[key] = {
                "star": r["star"],
                "catch": "ON" if r["_is_catch"] else "OFF",
                "total_n": 0,
                "succ": {"obs": 0, "exp": 0.0, "var": 0.0, "z_list": []},
                "fail": {"obs": 0, "exp": 0.0, "var": 0.0, "z_list": []},
                "boom": {"obs": 0, "exp": 0.0, "var": 0.0, "z_list": []},
            }
        
        entry = stats_map[key]
        n = r["total_n"]
        entry["total_n"] += n
        
        for t, prefix in [("succ", "success"), ("fail", "fail"), ("boom", "boom")]:
            target_p = r.get(f"{prefix}_p_target", 0.0)
            obs = r.get(f"{prefix}_n", 0)
            
            entry[t]["obs"] += obs
            entry[t]["exp"] += n * target_p
            entry[t]["var"] += n * target_p * (1.0 - target_p)
            
            if n > 100: 
                z = r.get(f"{prefix}_z_score", 0.0)
                entry[t]["z_list"].append(z)

    results = []
    for key, d in stats_map.items():
        row = {
            "star": d["star"],
            "catch": d["catch"],
            "total_n": d["total_n"],
        }
        
        for t in ["succ", "fail", "boom"]:
            total_var = d[t]["var"]
            if total_var > 0:
                z_score = (d[t]["obs"] - d[t]["exp"]) / (total_var ** 0.5)
            else:
                z_score = 0.0
            
            z_list = d[t]["z_list"]
            if len(z_list) > 1:
                z_score_var = statistics.variance(z_list)
            else:
                z_score_var = 0.0
                
            row[f"{t}_z"] = round(z_score, 2)
            row[f"{t}_var"] = round(z_score_var, 2)
            
        results.append(row)
    
    results.sort(key=lambda x: (x["star"], x["catch"]))
    
    return {
        "results": results,
        "count": len(results),
        "debug_info": {
            "db_size": len(AUDIT_DB),
            "included": total_included,
            "skipped": total_skipped
        }
    }

@app.get("/api/audit/heatmap")
def get_heatmap_data():
    """Returns Z-score data grouped by (star, date) for heatmap visualization."""
    # Group by (star, date, is_catch)
    heatmap_data = {}  # key: (star, date) -> {succ_z, boom_z, total_n}
    
    for r in AUDIT_DB:
        key = (r["star"], r["_date"])
        if key not in heatmap_data:
            heatmap_data[key] = {
                "star": r["star"],
                "date": r["_date"],
                "succ_z_sum": 0.0,
                "boom_z_sum": 0.0,
                "count": 0,
                "total_n": 0
            }
        
        entry = heatmap_data[key]
        entry["succ_z_sum"] += r.get("success_z_score", 0.0)
        entry["boom_z_sum"] += r.get("boom_z_score", 0.0)
        entry["count"] += 1
        entry["total_n"] += r.get("total_n", 0)
    
    # Calculate averages
    results = []
    for key, entry in heatmap_data.items():
        if entry["count"] > 0:
            results.append({
                "star": entry["star"],
                "date": entry["date"],
                "succ_z": round(entry["succ_z_sum"] / entry["count"], 2),
                "boom_z": round(entry["boom_z_sum"] / entry["count"], 2),
                "total_n": entry["total_n"]
            })
    
    # Get unique sorted dates and stars for axes
    dates = sorted(list(set(r["date"] for r in results)))
    stars = sorted(list(set(r["star"] for r in results)))
    
    return {
        "data": results,
        "dates": dates,
        "stars": stars
    }

@app.get("/api/audit/drift")
def get_drift_data():
    """Returns Z-score drift over time for Zero-sum Audit analysis."""
    # Group by date, calculate cumulative Z deviation
    date_stats = {}  # date -> {succ_z_sum, count}
    
    for r in AUDIT_DB:
        date = r["_date"]
        if date not in date_stats:
            date_stats[date] = {"succ_z_sum": 0.0, "boom_z_sum": 0.0, "count": 0}
        
        date_stats[date]["succ_z_sum"] += r.get("success_z_score", 0.0)
        date_stats[date]["boom_z_sum"] += r.get("boom_z_score", 0.0)
        date_stats[date]["count"] += 1
    
    # Calculate average Z per date and cumulative drift
    results = []
    cumulative_succ = 0.0
    cumulative_boom = 0.0
    
    for date in sorted(date_stats.keys()):
        stats = date_stats[date]
        avg_succ_z = stats["succ_z_sum"] / stats["count"] if stats["count"] > 0 else 0
        avg_boom_z = stats["boom_z_sum"] / stats["count"] if stats["count"] > 0 else 0
        
        cumulative_succ += avg_succ_z
        cumulative_boom += avg_boom_z
        
        results.append({
            "date": date,
            "avg_succ_z": round(avg_succ_z, 2),
            "avg_boom_z": round(avg_boom_z, 2),
            "cumulative_succ_z": round(cumulative_succ, 2),
            "cumulative_boom_z": round(cumulative_boom, 2)
        })
    
    return {"drift": results}