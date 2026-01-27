import numpy as np
import statistics
import time
from ..core.config import S, F, B, PROB, COST_TABLE

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
