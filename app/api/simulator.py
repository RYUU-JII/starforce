from fastapi import APIRouter
from ..models.schemas import CompareRequest
from ..services.simulation_service import SimulationService

router = APIRouter()
simulation_service = SimulationService()

@router.post("/compare")
def run_compare(req: CompareRequest):
    return simulation_service.run_compare(req)
