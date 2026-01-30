from pydantic import BaseModel
from typing import List, Optional

class CompareRequest(BaseModel):
    total_tries: int = 100
    block_intensity: int = 40  # legacy
    independent_deck: bool = True  # legacy
    users: int = 2000
    runs_per_user: int = 1
    share_scope: str = "global-relay"  # session | account | global-relay | global-queue
    deck_size: int = 10000
    corr_length: float = 3.0
    corr_length_s: Optional[float] = None
    corr_length_f: Optional[float] = None
    corr_length_b: Optional[float] = None
    tail_strength: float = 0.0
    tail_strength_s: Optional[float] = None
    tail_strength_f: Optional[float] = None
    tail_strength_b: Optional[float] = None
    cap_length: int = 5000
    cap_length_s: Optional[int] = None
    cap_length_f: Optional[int] = None
    cap_length_b: Optional[int] = None

    # Variance Control
    anti_cluster_mode: bool = False
    sticky_rng: bool = False
    sticky_rho: float = 0.0
    fixed_length_mode: bool = True

    # Markov Mode
    markov_mode: bool = False
    markov_rho: float = 0.0

    # Dual Deck Mode
    dual_mode: bool = False
    dual_bias: float = 0.5  # Ratio of users in Deck A (0.0 to 1.0)
    
    # Deck B params (if dual_mode is True)
    corr_length_s_b: Optional[float] = None
    corr_length_f_b: Optional[float] = None
    corr_length_b_b: Optional[float] = None
    tail_strength_s_b: Optional[float] = None
    tail_strength_f_b: Optional[float] = None
    tail_strength_b_b: Optional[float] = None
    cap_length_s_b: Optional[int] = None
    cap_length_f_b: Optional[int] = None
    cap_length_b_b: Optional[int] = None

    start_mode: str = "carry"  # carry | random
    box_size: int = 0
    mix_rate: float = 0.0
    mix_corr_mult: float = 1.0
    mix_tail_mult: float = 1.0
    mix_cap_mult: float = 1.0
    auto_calibrate: bool = False

class AuditQuery(BaseModel):
    events: List[str] = []
    stars: List[int] = []
    catch_ops: List[str] = []
    min_samples: int = 100

class SeasonContrastQuery(AuditQuery):
    split_date: Optional[str] = None
