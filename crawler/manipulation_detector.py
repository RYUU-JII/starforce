"""
확률 조작 탐지를 위한 통계 분석 모듈

분석 방법:
1. 분산 검정 (Variance Test): 실제 분산이 이론값보다 낮으면 조작 의심
2. Mean Reversion 분석: 편차 후 복귀 속도가 비정상적이면 조작 의심
3. 자기상관 분석 (Autocorrelation): 연속 시간대 결과가 상관되면 조작 의심
"""
import json
import math
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
from collections import defaultdict
import statistics


@dataclass
class VarianceTestResult:
    """분산 검정 결과"""
    star_level: int
    event_type: str
    starcatch: bool
    
    sample_count: int               # 분석한 시간대 수
    total_trials: int               # 총 시도 횟수
    
    expected_variance: float        # 이론적 분산 (베르누이)
    actual_variance: float          # 실제 관측 분산
    variance_ratio: float           # actual / expected
    
    # 해석
    is_suspicious: bool             # 조작 의심 여부
    suspicion_reason: str           # 의심 이유
    confidence_level: float         # 신뢰 수준 (0-1)


@dataclass
class MeanReversionResult:
    """Mean Reversion 분석 결과"""
    star_level: int
    event_type: str
    starcatch: bool
    
    sample_count: int
    
    # Reversion 속도 (편차 후 복귀까지 평균 시간)
    avg_reversion_speed: float      # 시간 단위
    expected_reversion: float       # 기대 복귀 시간 (자연적인 경우)
    
    # 편차-복귀 상관계수
    deviation_correction_corr: float  # 큰 편차 후 반대 방향 보정이 강하면 음수
    
    is_suspicious: bool
    suspicion_reason: str


@dataclass 
class AnalysisSummary:
    """전체 분석 요약"""
    session_name: str
    analyzed_at: str
    
    total_star_levels_analyzed: int
    suspicious_count: int
    
    variance_results: list[dict]
    mean_reversion_results: list[dict]
    
    overall_suspicion_score: float   # 0-100, 높을수록 조작 의심
    interpretation: str              # 해석 문구


class ManipulationDetector:
    """확률 조작 탐지기"""
    
    # 최소 샘플 수 (시간대 수)
    MIN_SAMPLES = 10
    # 시간당 최소 시도 횟수
    MIN_TRIALS_PER_HOUR = 50
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.deltas_file = session_dir / "hourly_deltas.jsonl"
    
    def load_deltas(self) -> list[dict]:
        """Delta 데이터 로드"""
        if not self.deltas_file.exists():
            return []
        
        deltas = []
        with open(self.deltas_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    deltas.append(json.loads(line))
        return deltas
    
    def analyze(self) -> AnalysisSummary:
        """전체 분석 실행"""
        deltas = self.load_deltas()
        
        if not deltas:
            return AnalysisSummary(
                session_name=self.session_dir.name,
                analyzed_at="N/A",
                total_star_levels_analyzed=0,
                suspicious_count=0,
                variance_results=[],
                mean_reversion_results=[],
                overall_suspicion_score=0.0,
                interpretation="데이터가 충분하지 않습니다. 최소 10시간 이상 수집 후 분석하세요."
            )
        
        # 그룹화: (star_level, event_type, starcatch) -> list of deltas
        grouped = self._group_deltas(deltas)
        
        variance_results = []
        reversion_results = []
        
        for key, group in grouped.items():
            if len(group) < self.MIN_SAMPLES:
                continue
            
            star, event, catch = key
            
            # 분산 검정
            var_result = self._variance_test(star, event, catch, group)
            if var_result:
                variance_results.append(var_result)
            
            # Mean Reversion 분석
            rev_result = self._mean_reversion_test(star, event, catch, group)
            if rev_result:
                reversion_results.append(rev_result)
        
        # 전체 의심 점수 계산
        suspicious_count = sum(1 for r in variance_results if r.is_suspicious)
        suspicious_count += sum(1 for r in reversion_results if r.is_suspicious)
        
        total_tests = len(variance_results) + len(reversion_results)
        suspicion_score = (suspicious_count / max(total_tests, 1)) * 100
        
        interpretation = self._interpret_score(suspicion_score, variance_results, reversion_results)
        
        from datetime import datetime
        return AnalysisSummary(
            session_name=self.session_dir.name,
            analyzed_at=datetime.now().isoformat(),
            total_star_levels_analyzed=len(grouped),
            suspicious_count=suspicious_count,
            variance_results=[asdict(r) for r in variance_results],
            mean_reversion_results=[asdict(r) for r in reversion_results],
            overall_suspicion_score=round(suspicion_score, 2),
            interpretation=interpretation
        )
    
    def _group_deltas(self, deltas: list) -> dict:
        """Delta를 키별로 그룹화"""
        grouped = defaultdict(list)
        for d in deltas:
            key = (d["star_level"], d["event_type"], d["starcatch"])
            grouped[key].append(d)
        return grouped
    
    def _variance_test(self, star: int, event: str, catch: bool, 
                        deltas: list) -> Optional[VarianceTestResult]:
        """
        분산 검정: Binomial 분포의 이론적 분산과 실제 분산 비교
        
        이론적 분산: p * (1-p) / n (각 시간대별)
        실제 분산: 관측된 성공률의 분산
        
        variance_ratio < 0.5 → 너무 일정함 (조작 의심)
        variance_ratio > 2.0 → 너무 불규칙 (다른 문제)
        """
        # 충분한 시도 횟수가 있는 시간대만 필터
        valid_deltas = [d for d in deltas if d["total_count"] >= self.MIN_TRIALS_PER_HOUR]
        
        if len(valid_deltas) < self.MIN_SAMPLES:
            return None
        
        # 각 시간대별 성공률 계산
        success_rates = [d["actual_success_rate"] for d in valid_deltas]
        expected_rate = valid_deltas[0]["expected_success_rate"]
        
        # 실제 분산
        if len(success_rates) < 2:
            return None
        actual_variance = statistics.variance(success_rates)
        
        # 이론적 분산 (평균 시도 횟수 기준)
        avg_n = statistics.mean([d["total_count"] for d in valid_deltas])
        expected_variance = (expected_rate * (1 - expected_rate)) / avg_n
        
        if expected_variance == 0:
            return None
        
        variance_ratio = actual_variance / expected_variance
        
        # 판정
        is_suspicious = False
        reason = ""
        confidence = 0.0
        
        if variance_ratio < 0.3:
            is_suspicious = True
            reason = f"분산이 이론값의 {variance_ratio:.1%}로 비정상적으로 낮음 (강력한 조작 의심)"
            confidence = 0.9
        elif variance_ratio < 0.5:
            is_suspicious = True
            reason = f"분산이 이론값의 {variance_ratio:.1%}로 낮음 (조작 가능성)"
            confidence = 0.7
        elif variance_ratio < 0.7:
            reason = f"분산이 이론값의 {variance_ratio:.1%}로 다소 낮음 (주의 관찰 필요)"
            confidence = 0.4
        else:
            reason = f"분산이 이론값의 {variance_ratio:.1%}로 정상 범위"
            confidence = 0.1
        
        return VarianceTestResult(
            star_level=star,
            event_type=event,
            starcatch=catch,
            sample_count=len(valid_deltas),
            total_trials=sum(d["total_count"] for d in valid_deltas),
            expected_variance=expected_variance,
            actual_variance=actual_variance,
            variance_ratio=variance_ratio,
            is_suspicious=is_suspicious,
            suspicion_reason=reason,
            confidence_level=confidence
        )
    
    def _mean_reversion_test(self, star: int, event: str, catch: bool,
                              deltas: list) -> Optional[MeanReversionResult]:
        """
        Mean Reversion 분석: 편차 발생 후 복귀 패턴 분석
        
        자연적인 경우: 편차와 다음 시간대 결과는 무상관 (독립)
        조작된 경우: 큰 양의 편차 후 음의 편차가 따라옴 (보정)
        
        deviation[t]와 deviation[t+1]의 상관계수가 강하게 음수면 조작 의심
        """
        valid_deltas = [d for d in deltas if d["total_count"] >= self.MIN_TRIALS_PER_HOUR]
        
        if len(valid_deltas) < self.MIN_SAMPLES:
            return None
        
        expected_rate = valid_deltas[0]["expected_success_rate"]
        
        # 편차 시계열 계산
        deviations = [d["actual_success_rate"] - expected_rate for d in valid_deltas]
        
        if len(deviations) < 3:
            return None
        
        # Lag-1 자기상관 계산 (deviation[t]와 deviation[t+1]의 상관)
        n = len(deviations)
        mean_dev = sum(deviations) / n
        
        numerator = sum((deviations[i] - mean_dev) * (deviations[i+1] - mean_dev) 
                        for i in range(n-1))
        denominator = sum((d - mean_dev) ** 2 for d in deviations)
        
        if denominator == 0:
            return None
        
        autocorr = numerator / denominator
        
        # 복귀 속도 계산 (큰 편차 후 몇 시간만에 정상화되는지)
        # 간이 계산: 편차 절대값이 임계치 넘은 후 다시 내려오기까지
        threshold = 0.05  # 5% 편차
        reversion_times = []
        
        i = 0
        while i < len(deviations) - 1:
            if abs(deviations[i]) > threshold:
                # 편차 발생, 복귀까지 시간 측정
                j = i + 1
                while j < len(deviations) and abs(deviations[j]) > threshold * 0.5:
                    j += 1
                reversion_times.append(j - i)
                i = j
            else:
                i += 1
        
        avg_reversion = sum(reversion_times) / max(len(reversion_times), 1) if reversion_times else 0
        
        # 자연적 복귀 시간 추정 (대수의 법칙 기준)
        # 간이 추정: 분산이 절반으로 줄려면 시행 수가 4배 필요
        avg_n = statistics.mean([d["total_count"] for d in valid_deltas])
        # 대략적으로 3-5시간이 자연적 복귀 시간으로 추정
        expected_reversion = max(3.0, 10.0 * threshold / (expected_rate * (1 - expected_rate) / avg_n) ** 0.5)
        expected_reversion = min(expected_reversion, 10.0)  # 최대 10시간
        
        # 판정
        is_suspicious = False
        reason = ""
        
        if autocorr < -0.5:
            is_suspicious = True
            reason = f"강한 음의 자기상관({autocorr:.3f}): 편차 후 즉시 반대 방향 보정 발생 (강력한 조작 의심)"
        elif autocorr < -0.3:
            is_suspicious = True
            reason = f"음의 자기상관({autocorr:.3f}): 편차와 다음 시간 결과가 반대 경향 (조작 가능성)"
        elif avg_reversion > 0 and avg_reversion < expected_reversion * 0.3:
            is_suspicious = True
            reason = f"비정상적으로 빠른 복귀({avg_reversion:.1f}시간 vs 예상 {expected_reversion:.1f}시간)"
        else:
            reason = f"자기상관({autocorr:.3f})이 정상 범위, 복귀 속도 정상"
        
        return MeanReversionResult(
            star_level=star,
            event_type=event,
            starcatch=catch,
            sample_count=len(valid_deltas),
            avg_reversion_speed=avg_reversion,
            expected_reversion=expected_reversion,
            deviation_correction_corr=autocorr,
            is_suspicious=is_suspicious,
            suspicion_reason=reason
        )
    
    def _interpret_score(self, score: float, 
                          var_results: list, rev_results: list) -> str:
        """전체 점수 해석"""
        if score >= 70:
            return ("🚨 높은 조작 의심: 다수의 성/이벤트 조합에서 비정상적 패턴 발견. "
                    "확률이 인위적으로 제어되고 있을 가능성이 높습니다.")
        elif score >= 40:
            return ("⚠️ 중간 수준 의심: 일부 조합에서 의심스러운 패턴 발견. "
                    "추가 데이터 수집 후 재분석 권장.")
        elif score >= 20:
            return ("🔍 경미한 이상: 몇몇 조합에서 약간의 이상 발견. "
                    "자연적 변동 범위일 수 있으나 모니터링 지속 필요.")
        else:
            return ("✅ 정상 범위: 현재까지 수집된 데이터에서 조작 징후 미발견. "
                    "확률이 자연적으로 작동하는 것으로 보입니다.")
    
    def save_report(self, summary: AnalysisSummary, output_path: Optional[Path] = None):
        """분석 결과 저장"""
        if output_path is None:
            output_path = self.session_dir / "analysis_report.json"
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(summary), f, ensure_ascii=False, indent=2)
        
        print(f"분석 리포트 저장: {output_path}")
        return output_path


def run_analysis(session_dir: Path) -> AnalysisSummary:
    """분석 실행 헬퍼"""
    detector = ManipulationDetector(session_dir)
    summary = detector.analyze()
    detector.save_report(summary)
    return summary
