
import math

def unit_size_for_probs(prob_tuple):
    """
    Calculates the minimum integer unit size that can represent the given probabilities.
    e.g. (0.3, 0.65, 0.05) -> GCD logic -> returns smallest common denominator equivalent count.
    """
    p_s, p_f, p_b = prob_tuple
    denom = 10000
    s_cnt = int(round(p_s * denom))
    b_cnt = int(round(p_b * denom))
    f_cnt = denom - s_cnt - b_cnt
    
    # Calculate GCD of counts
    g = math.gcd(s_cnt, math.gcd(f_cnt, b_cnt))
    if g <= 0:
        return denom
    return int(denom // g)

def auto_cap(mean_len, kind):
    """
    Heuristic to set 'cap' (max streak length) based on mean run length.
    """
    m = max(1, float(mean_len))
    if kind == 's': 
        return min(25, max(6, int(round(m * 6))))
    if kind == 'f': 
        return min(500, max(50, int(round(m * 80))))
    return min(50, max(5, int(round(m * 20))))

def get_b_val(val_b, val_a):
    """Helper to fallback to A value if B is not set"""
    return val_b if val_b is not None else val_a

def auto_cap_b(mean_len, kind):
    """Duplicate of auto_cap for Deck B contexts?"""
    return auto_cap(mean_len, kind)
