from pydantic import BaseModel
from typing import List, Optional

class CompareRequest(BaseModel):
    total_tries: int = 100
    block_intensity: int = 40
    independent_deck: bool = True

class AuditQuery(BaseModel):
    events: List[str] = []
    stars: List[int] = []
    catch_ops: List[str] = []
    min_samples: int = 100

class SeasonContrastQuery(AuditQuery):
    split_date: Optional[str] = None
