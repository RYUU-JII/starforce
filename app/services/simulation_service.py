
import time
import statistics
import math
import random
import numpy as np
from dataclasses import replace, dataclass, field

from ..models.schemas import CompareRequest
# from ..core.simulator_engine import iid_draw_factory, simulate_detailed, simulate_interleaved, aggregate
from ..core.config import PROB, S, F, B, COST_TABLE
from ..core.utils import unit_size_for_probs, auto_cap, get_b_val, auto_cap_b

import starforce_sim_core as cpp_engine

@dataclass
class RunDeckConfig:
    chunk_size: int = 200000
    chunk_size_by_level: dict = None
    wrap_random: bool = True
    corr_length_s: float = 12.0
    corr_length_f: float = 12.0
    corr_length_b: float = 12.0
    tail_strength_s: float = 0.05
    tail_strength_f: float = 0.05
    tail_strength_b: float = 0.05
    cap_s: int = 0
    cap_f: int = 0
    cap_b: int = 0
    box_size: int = 0
    mix_rate: float = 0.0
    mix_corr_mult: float = 1.0
    mix_tail_mult: float = 1.0
    mix_cap_mult: float = 1.0
    
    # Variance Control
    anti_cluster_mode: bool = False
    fixed_length_mode: bool = True
    
    # Dual Deck Params
    is_deck_b: bool = False

class SimulationService:
    def __init__(self):
        pass

    def run_compare(self, req: CompareRequest):
        start_time = time.time()

        # Resolve simulation counts
        users = max(1, int(req.users or 0))
        runs_per_user = max(1, int(req.runs_per_user or 0))
        if (req.users is None or req.users == 0) and req.total_tries:
            users = int(req.total_tries)
            runs_per_user = 1

        total_sessions = users * runs_per_user
        total_sessions = min(total_sessions, 200000)

        # Config setup
        cfg = self._build_config(req)

        # Fair world (C++)
        if cpp_engine:
            res_tuple = cpp_engine.simulate_fair_cpp(users, runs_per_user, PROB, random.randint(0, 1000000))
            fair_results = res_tuple[0]
        else:
            raise RuntimeError("C++ Engine not available")
        
        fair_time = time.time()
        fair_res = aggregate(fair_results)

        # Calculate deck sizes based on fair results
        cfg = self._adjust_deck_sizes(cfg, fair_res)

        # --- Dual Deck Configuration Setup ---
        cfg_a = cfg
        cfg_b = None
        if req.dual_mode:
            cfg_b = self._build_dual_config(cfg, req)

        # --- Markov Engine Routing ---
        if req.markov_mode and cpp_engine:
            return self._run_markov(req, users, runs_per_user, fair_res, total_sessions, start_time, fair_time)

        # Main Simulation
        rigged_results, rigged_draws, rigged_builds, rigged_wraps = self._run_rigged_simulation(
            req, cfg, cfg_a, cfg_b, users, runs_per_user
        )
        
        rigged_time = time.time()
        rigged_res = aggregate(rigged_results)
        
        # Deck Analysis for Inspector
        deck_analysis = self._generate_deck_analysis(cfg)

        total_time = time.time() - start_time

        return {
            "fair": fair_res,
            "rigged": rigged_res,
            "deck_analysis": deck_analysis,
            "theory": {str(k): v for k, v in PROB.items()},
            "simulation_count": total_sessions,
            "users": users,
            "runs_per_user": runs_per_user,
            "share_scope": req.share_scope or "global-relay",
            "config": self._serialize_config(cfg, req),
            "execution_time": float(total_time),
            "timing": {
                "fair_time": float(fair_time - start_time),
                "rigged_time": float(rigged_time - fair_time)
            },
            "calibration": None,
            "deck_stats": {
                "rigged_draws": rigged_draws,
                "rigged_builds": rigged_builds,
                "rigged_wraps": rigged_wraps
            }
        }

    def _build_config(self, req: CompareRequest):
        corr_s = req.corr_length_s if req.corr_length_s is not None else req.corr_length
        corr_f = req.corr_length_f if req.corr_length_f is not None else req.corr_length
        corr_b = req.corr_length_b if req.corr_length_b is not None else req.corr_length
        
        cap_s = req.cap_length_s if req.cap_length_s is not None and req.cap_length_s > 0 else auto_cap(corr_s, "s")
        cap_f = req.cap_length_f if req.cap_length_f is not None and req.cap_length_f > 0 else auto_cap(corr_f, "f")
        cap_b = req.cap_length_b if req.cap_length_b is not None and req.cap_length_b > 0 else auto_cap(corr_b, "b")

        return RunDeckConfig(
            chunk_size=max(1000, int(req.deck_size)),
            corr_length_s=max(1.0, float(corr_s)),
            corr_length_f=max(1.0, float(corr_f)),
            corr_length_b=max(1.0, float(corr_b)),
            tail_strength_s=max(0.0, float(req.tail_strength_s or 0)),
            tail_strength_f=max(0.0, float(req.tail_strength_f or 0)),
            tail_strength_b=max(0.0, float(req.tail_strength_b or 0)),
            cap_s=max(0, int(cap_s or 0)),
            cap_f=max(0, int(cap_f or 0)),
            cap_b=max(0, int(cap_b or 0)),
            box_size=max(0, int(req.box_size or 0)),
            mix_rate=max(0.0, float(req.mix_rate or 0.0)),
            mix_tail_mult=max(0.0, float(req.mix_tail_mult or 1.0)),
            mix_cap_mult=max(0.1, float(req.mix_cap_mult or 1.0)),
            # Anti-Cluster: Designed for Dual Deck A, but available for Single Deck if requested
            anti_cluster_mode=bool(req.anti_cluster_mode) if req.anti_cluster_mode is not None else False,
            fixed_length_mode=bool(req.fixed_length_mode) if req.fixed_length_mode is not None else True
        )

    def _adjust_deck_sizes(self, cfg, fair_res):
        level_avg = fair_res.get("level_avg_tries", {}) or {}
        values = [level_avg.get(str(l), 0) for l in PROB.keys() if level_avg.get(str(l), 0) > 0]
        mean_tries = statistics.mean(values) if values else 1.0
        if mean_tries <= 0: mean_tries = 1.0

        chunk_by_level = {}
        for level in PROB.keys():
            tries = float(level_avg.get(str(level), mean_tries))
            weight = tries / mean_tries if mean_tries > 0 else 1.0
            raw_size = float(cfg.chunk_size) * weight
            unit = unit_size_for_probs(PROB[level])
            size = int(round(raw_size / unit)) * unit
            if size < unit: size = unit
            chunk_by_level[level] = size
        
        return replace(cfg, chunk_size_by_level=chunk_by_level)

    def _build_dual_config(self, cfg, req):
        corr_s = cfg.corr_length_s
        corr_f = cfg.corr_length_f
        corr_b = cfg.corr_length_b
        
        corr_s_b = get_b_val(req.corr_length_s_b, corr_s)
        corr_f_b = get_b_val(req.corr_length_f_b, corr_f)
        corr_b_b = get_b_val(req.corr_length_b_b, corr_b)

        cap_s_b = req.cap_length_s_b or auto_cap_b(corr_s_b, "s")
        cap_f_b = req.cap_length_f_b or auto_cap_b(corr_f_b, "f")
        cap_b_b = req.cap_length_b_b or auto_cap_b(corr_b_b, "b")

        return replace(
            cfg,
            corr_length_s=corr_s_b,
            corr_length_f=corr_f_b,
            corr_length_b=corr_b_b,
            tail_strength_s=get_b_val(req.tail_strength_s_b, cfg.tail_strength_s),
            tail_strength_f=get_b_val(req.tail_strength_f_b, cfg.tail_strength_f),
            tail_strength_b=get_b_val(req.tail_strength_b_b, cfg.tail_strength_b),
            cap_s=cap_s_b,
            cap_f=cap_f_b,
            cap_b=cap_b_b,
            anti_cluster_mode=False,
            is_deck_b=True
        )

    def _serialize_config(self, cfg, req):
        return {
            "deck_size": cfg.chunk_size,
            "deck_size_by_level": cfg.chunk_size, 
            "auto_calibrate": req.auto_calibrate,
            "sticky_rng": req.sticky_rng,
            "sticky_rho": req.sticky_rho,
            "markov_mode": req.markov_mode,
            "markov_rho": req.markov_rho,
            "fixed_length_mode": getattr(cfg, "fixed_length_mode", True),
            "dual_mode": req.dual_mode
        }

    def _run_markov(self, req, users, runs_per_user, fair_res, total_sessions, start_time, fair_time):
        res_tuple = cpp_engine.simulate_markov_cpp(
            users, runs_per_user, PROB, float(req.markov_rho), random.randint(0, 1000000)
        )
        markov_results_list = res_tuple[0]
        markov_time = time.time()
        markov_res = aggregate(markov_results_list)
        total_time = time.time() - start_time
        
        return {
            "fair": fair_res,
            "rigged": markov_res, 
            "simulation_count": total_sessions,
            "users": users,
            "runs_per_user": runs_per_user,
            "share_scope": "markov",
            "config": {"markov_mode": True},
            "deck_analysis": {},
            "theory": {str(k): v for k, v in PROB.items()},
            "execution_time": float(total_time),
            "timing": {"fair_time": fair_time - start_time, "rigged_time": markov_time - fair_time},
            "calibration": None,
            "deck_stats": {"rigged_draws": 0, "rigged_builds": 0,"rigged_wraps": 0}
        }

    def _resolve_calibration_bias(self, req: CompareRequest) -> float:
        # "Auto Calibrate" logic moved to setup
        if req.auto_calibrate:
             # Placeholder: In the future, this could calculate a dynamic bias based on history
             # For now, we return 0.0 or a fixed offset if requested
             return 0.0 
        return 0.0

    def _run_rigged_simulation(self, req, cfg, cfg_a, cfg_b, users, runs_per_user):
        # 1. Setup Phase: Calibration
        bias = self._resolve_calibration_bias(req)
        
        # 2. Execution Phase: Routing
        if req.dual_mode and cfg_b:
            bias_split = req.dual_bias if req.dual_bias is not None else 0.5
            bias_split = max(0.0, min(1.0, float(bias_split)))
            users_a = int(round(users * bias_split))
            users_b = users - users_a
            
            res_all, d_all, b_all, w_all = [], 0, 0, 0
            
            if users_a > 0:
                # Deck A (supports Anti-Cluster if configured)
                r, d, b, w = self._execute_rigged(req, cfg_a, users_a, runs_per_user, bias)
                res_all.extend(r); d_all += d; b_all += b; w_all += w
            
            if users_b > 0:
                # Deck B (No Anti-Cluster, High Variance typically)
                r, d, b, w = self._execute_rigged(req, cfg_b, users_b, runs_per_user, bias)
                res_all.extend(r); d_all += d; b_all += b; w_all += w
                
            return res_all, d_all, b_all, w_all
        
        # Single Deck Mode
        return self._execute_rigged(req, cfg, users, runs_per_user, bias)

    def _execute_rigged(self, req, cfg, users, runs, bias):
        share_scope = (req.share_scope or "global-relay").lower()
        use_sticky = bool(req.sticky_rng)
        sticky_rho = float(req.sticky_rho or 0.0)
        start_mode = "carry"

        # --- C++ Engine Path ---
        try:
            rigged_results_local = []
            rigged_draws_local = 0
            rigged_builds_local = 0
            rigged_wraps_local = 0
            
            is_sequential = share_scope in ["global-relay", "global"]

            if use_sticky:
                if share_scope == "account":
                    for _ in range(users):
                        res_tuple = cpp_engine.simulate_sticky_cpp(
                            1, runs, PROB, sticky_rho, bias, random.randint(0, 1000000), True
                        )
                        r_res, r_d, r_b, r_w = res_tuple
                        rigged_results_local.extend(r_res)
                        rigged_draws_local += r_d
                        rigged_builds_local += r_b
                        rigged_wraps_local += r_w
                elif share_scope == "session":
                    for _ in range(users * runs):
                        res_tuple = cpp_engine.simulate_sticky_cpp(
                            1, 1, PROB, sticky_rho, bias, random.randint(0, 1000000), True
                        )
                        r_res, r_d, r_b, r_w = res_tuple
                        rigged_results_local.extend(r_res)
                        rigged_draws_local += r_d
                        rigged_builds_local += r_b
                        rigged_wraps_local += r_w
                else:
                    res_tuple = cpp_engine.simulate_sticky_cpp(
                        users, runs, PROB, sticky_rho, bias, random.randint(0, 1000000), is_sequential
                    )
                    r_res, r_d, r_b, r_w = res_tuple
                    rigged_results_local.extend(r_res)
                    rigged_draws_local += r_d
                    rigged_builds_local += r_b
                    rigged_wraps_local += r_w
            else:
                cfg_cpp = self._convert_to_cpp_config(cfg)
                
                if share_scope == "account":
                    for _ in range(users):
                        res_tuple = cpp_engine.simulate_rigged_cpp(
                            1, runs, PROB, cfg_cpp, start_mode, random.randint(0, 1000000), True
                        )
                        r_res, r_d, r_b, r_w = res_tuple
                        rigged_results_local.extend(r_res)
                        rigged_draws_local += r_d
                        rigged_builds_local += r_b
                        rigged_wraps_local += r_w
                elif share_scope == "session":
                    for _ in range(users * runs):
                        res_tuple = cpp_engine.simulate_rigged_cpp(
                            1, 1, PROB, cfg_cpp, start_mode, random.randint(0, 1000000), True
                        )
                        r_res, r_d, r_b, r_w = res_tuple
                        rigged_results_local.extend(r_res)
                        rigged_draws_local += r_d
                        rigged_builds_local += r_b
                        rigged_wraps_local += r_w
                else:
                    res_tuple = cpp_engine.simulate_rigged_cpp(
                        users, runs, PROB, cfg_cpp, start_mode, random.randint(0, 1000000), is_sequential
                    )
                    r_res, r_d, r_b, r_w = res_tuple
                    rigged_results_local.extend(r_res)
                    rigged_draws_local += r_d
                    rigged_builds_local += r_b
                    rigged_wraps_local += r_w

            return rigged_results_local, rigged_draws_local, rigged_builds_local, rigged_wraps_local
        
        except Exception as e:
            # If C++ fails, we propagate the error instead of falling back
            print(f"C++ Engine Critical Error: {e}")
            raise e

    def _convert_to_cpp_config(self, cfg):
        if not cpp_engine: return None
        c = cpp_engine.RunDeckConfig()
        c.chunk_size = int(cfg.chunk_size)
        c.chunk_size_by_level = {int(k): int(v) for k, v in (cfg.chunk_size_by_level or {}).items()}
        c.wrap_random = bool(getattr(cfg, "wrap_random", True))
        c.corr_length_s = float(cfg.corr_length_s)
        c.corr_length_f = float(cfg.corr_length_f)
        c.corr_length_b = float(cfg.corr_length_b)
        c.tail_strength_s = float(cfg.tail_strength_s)
        c.tail_strength_f = float(cfg.tail_strength_f)
        c.tail_strength_b = float(cfg.tail_strength_b)
        c.cap_s = int(cfg.cap_s)
        c.cap_f = int(cfg.cap_f)
        c.cap_b = int(cfg.cap_b)
        c.box_size = int(cfg.box_size)
        c.mix_rate = float(cfg.mix_rate)
        c.mix_corr_mult = float(cfg.mix_corr_mult)
        c.mix_tail_mult = float(cfg.mix_tail_mult)
        c.mix_cap_mult = float(cfg.mix_cap_mult)
        c.anti_cluster_mode = bool(cfg.anti_cluster_mode)
        # Safety check: if C++ extension is old, this attr might fail
        try:
            c.fixed_length_mode = bool(getattr(cfg, "fixed_length_mode", True))
        except AttributeError:
             pass 
        return c

    def _generate_deck_analysis(self, cfg: RunDeckConfig):
        # We sample run lengths for specific stars to show in the inspector
        analysis = {}
        target_stars = [12, 17, 20, 21]
        
        # Use a temporary RNG
        rng = np.random.default_rng(seed=42)
        
        for star in target_stars:
            if star not in PROB: continue
            
            p_s, p_f, p_b = PROB[star]
            
            # Helper to sample run lengths (simplified Python version of Deck Logic)
            def sample_lens(count, mean_len, tail_strength, cap):
                runs = []
                remaining = count
                while remaining > 0:
                    use_mix = cfg.mix_rate > 0 and rng.random() < cfg.mix_rate
                    mean_used = float(mean_len) * (cfg.mix_corr_mult if use_mix else 1.0)
                    mean_used = max(1.0, mean_used)
                    tail_used = float(tail_strength) * (cfg.mix_tail_mult if use_mix else 1.0)
                    tail_used = min(1.0, max(0.0, tail_used))
                    cap_used = cap
                    if cap_used and cap_used > 0 and use_mix:
                        cap_used = int(round(cap_used * cfg.mix_cap_mult))
                    
                    if tail_used <= 0:
                        if cfg.fixed_length_mode:
                            base = max(1, int(math.floor(mean_used)))
                            top = max(1, int(math.ceil(mean_used)))
                            if cap_used > 0:
                                base = min(base, cap_used)
                                top = min(top, cap_used)
                            
                            if base >= top:
                                length = base
                            else:
                                p_top = (mean_used - base) / (top - base)
                                length = top if rng.random() < p_top else base
                        else:
                             p = 1.0 / mean_used
                             length = int(rng.geometric(p))
                    else:
                        p = 1.0 / mean_used
                        if rng.random() < tail_used:
                            tail_min = max(2, int(mean_used * 2))
                            tail_max = max(tail_min, int(mean_used * 4))
                            if cap_used > 0:
                                tail_max = min(tail_max, cap_used)
                            length = int(rng.integers(tail_min, tail_max + 1))
                        else:
                            length = int(rng.geometric(p))
                    
                    if cap_used > 0:
                        length = min(length, cap_used)
                    if length > remaining:
                        length = remaining
                    runs.append(length)
                    remaining -= length
                rng.shuffle(runs)
                return runs

            # Sample 2000 lengths for s and f
            s_runs = sample_lens(2000, cfg.corr_length_s, cfg.tail_strength_s, cfg.cap_s)
            f_runs = sample_lens(2000, cfg.corr_length_f, cfg.tail_strength_f, cfg.cap_f)
            
            def to_dist(runs):
                unique, counts = np.unique(runs, return_counts=True)
                return {int(k): int(v) for k, v in zip(unique, counts)}
                
            analysis[str(star)] = {
                "s": to_dist(s_runs),
                "f": to_dist(f_runs)
            }
        return analysis

# Helper functions removed (migrated to C++)
def aggregate(results):
    if not results:
        return {
            "s_var": 0.0, "f_var": 0.0, "b_var": 0.0,
            "max_f": 0, "max_s": 0, "max_b": 0,
            "level_stats": {},
            "histogram": [], "s_histogram": [], "b_histogram": [], "m_histogram": [],
            "avg_cost": 0,
            "avg_clicks": 0,
            "clicks_p50": 0,
            "clicks_p90": 0,
            "clicks_p95": 0,
            "clicks_p99": 0,
            "level_avg_tries": {}
        }
    
    total_lvl_stats = np.zeros((10, 4), dtype=int)
    costs = []
    clicks = []
    all_streaks = []
    all_b_streaks = []
    for r in results:
        if isinstance(r, dict):
             total_lvl_stats += r['lvl_stats']
             costs.append(r.get('cost', 0))
             clicks.append(r.get('clicks', 0))
             all_streaks.extend(r['streaks'])
             all_b_streaks.extend(r.get('b_streaks', []))
        else:
             # C++ SimResult object
             total_lvl_stats += np.array(r.lvl_stats) # convert to numpy
             costs.append(r.cost)
             clicks.append(r.clicks)
             all_streaks.extend(r.streaks)
             all_b_streaks.extend(r.b_streaks)
    
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

    s_streaks = [s for s in all_streaks if s > 0]
    f_streaks = [abs(s) for s in all_streaks if s < 0]
    b_streaks = [int(s) for s in all_b_streaks if s > 0]
    
    s_var = 0.0
    f_var = 0.0
    b_var = 0.0
    
    if len(s_streaks) > 1:
        s_var = float(np.var(s_streaks, ddof=1))
    if len(f_streaks) > 1:
        f_var = float(np.var(f_streaks, ddof=1))
    if len(b_streaks) > 1:
        b_var = float(np.var(b_streaks, ddof=1))
    
    histogram = []
    if f_streaks:
        unique, counts = np.unique(f_streaks, return_counts=True)
        histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]

    s_histogram = []
    if s_streaks:
        unique, counts = np.unique(s_streaks, return_counts=True)
        s_histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]

    b_histogram = []
    if b_streaks:
        unique, counts = np.unique(b_streaks, return_counts=True)
        b_histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]
        
    m_histogram = []
    if costs:
        cost_billions = [int(c / 1000000000) for c in costs]
        unique, counts = np.unique(cost_billions, return_counts=True)
        m_histogram = [{"x": int(k), "y": int(v)} for k, v in zip(unique, counts)]

    level_avg_tries = {}
    run_count = len(results)
    if run_count > 0:
        for i in range(10):
            level = 12 + i
            tries = int(total_lvl_stats[i][0])
            level_avg_tries[str(level)] = tries / run_count
    
    clicks_p50 = float(np.percentile(clicks, 50)) if clicks else 0.0
    clicks_p90 = float(np.percentile(clicks, 90)) if clicks else 0.0
    clicks_p95 = float(np.percentile(clicks, 95)) if clicks else 0.0
    clicks_p99 = float(np.percentile(clicks, 99)) if clicks else 0.0
    
    return {
        "s_var": s_var,
        "f_var": f_var,
        "b_var": b_var,
        "max_f": int(max(f_streaks)) if f_streaks else 0,
        "max_s": int(max(s_streaks)) if s_streaks else 0,
        "max_b": int(max(b_streaks)) if b_streaks else 0,
        "level_stats": level_table,
        "histogram": histogram,
        "s_histogram": s_histogram,
        "b_histogram": b_histogram,
        "m_histogram": m_histogram,
        "avg_cost": float(statistics.mean(costs)) if costs else 0.0,
        "cost_var": float(statistics.variance(costs)) if len(costs) > 1 else 0.0,
        "avg_clicks": float(statistics.mean(clicks)) if clicks else 0.0,
        "clicks_p50": clicks_p50,
        "clicks_p90": clicks_p90,
        "clicks_p95": clicks_p95,
        "clicks_p99": clicks_p99,
        "level_avg_tries": level_avg_tries
    }
