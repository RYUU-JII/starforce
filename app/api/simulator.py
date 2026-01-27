from fastapi import APIRouter
from ..models.schemas import CompareRequest
from ..core.simulator_engine import DeckManager, simulate_detailed, aggregate
from ..core.config import PROB
import time

router = APIRouter()

@router.post("/compare")
def run_compare(req: CompareRequest):
    start_time = time.time()
    
    total_tries = min(req.total_tries, 100000)
    
    fair_manager = DeckManager(PROB, chunk_size=1000000, mode='random')
    fair_draw_fn = fair_manager.get_draw_fn(independent=False)
    
    fair_results = []
    for i in range(total_tries):
        fair_results.append(simulate_detailed(fair_draw_fn))
    
    fair_time = time.time()
    
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
    
    fair_res = aggregate(fair_results)
    rigged_res = aggregate(rigged_results)
    
    total_time = time.time() - start_time
    
    return {
        "fair": fair_res,
        "rigged": rigged_res,
        "theory": {str(k): v for k, v in PROB.items()},
        "simulation_count": total_tries,
        "execution_time": float(total_time)
    }
