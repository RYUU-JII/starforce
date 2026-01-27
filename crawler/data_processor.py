"""
데이터 처리: 스냅샷 → Delta 변환 및 패치 세션 관리
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class HourlyDelta:
    """한 시간 동안의 강화 결과 증분"""
    timestamp: str                    # ISO format
    star_level: int                   # 강화 단계
    event_type: str                   # 이벤트 종류
    starcatch: bool                   # 스타캐치 여부
    
    # 시도 횟수 (이 시간 동안)
    success_count: int
    fail_count: int
    boom_count: int
    total_count: int
    
    # 확률
    expected_success_rate: float      # 설정 확률
    actual_success_rate: float        # 실제 결과
    
    # 파괴 확률 (15성 이상)
    expected_boom_rate: Optional[float] = None
    actual_boom_rate: Optional[float] = None


class DeltaCalculator:
    """연속 스냅샷에서 시간별 증분 계산"""
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_file = session_dir / "hourly_snapshots.jsonl"
        self.deltas_file = session_dir / "hourly_deltas.jsonl"
        
        # 이전 스냅샷 캐시 (star_level -> previous data)
        self._previous: dict[str, dict] = {}
        self._previous_window_end: str = ""  # 마지막 windowEnd 추적
        self._load_last_snapshot()
    
    def _load_last_snapshot(self):
        """마지막 스냅샷 로드하여 delta 계산 준비"""
        if not self.snapshots_file.exists():
            return
        
        # 마지막 줄 읽기
        with open(self.snapshots_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if lines:
                last = json.loads(lines[-1])
                self._previous = last.get("data_by_key", {})
                self._previous_window_end = last.get("window_end", "")
    
    def process_crawl_result(self, crawl_result: dict) -> tuple[list[HourlyDelta], bool]:
        """
        크롤링 결과를 처리하여 delta 계산
        
        Args:
            crawl_result: nexon_crawler의 결과 dict
            
        Returns:
            (계산된 HourlyDelta 리스트, 패치 리셋 감지 여부)
        """
        timestamp = crawl_result.get("crawled_at", datetime.now().isoformat())
        deltas = []
        current_data = {}
        reset_detected = False
        reset_count = 0
        current_window_end = ""
        
        # 첫 번째 prob_entry에서 windowEnd 추출하여 중복 체크
        prob_data = crawl_result.get("prob_data", [])
        if prob_data:
            first_probs = prob_data[0].get("data", {}).get("data", {}).get("probs", [])
            if first_probs:
                current_window_end = first_probs[0].get("windowEnd", "")
        
        # 같은 windowEnd면 중복 데이터 → 저장 건너뜀
        if current_window_end and current_window_end == self._previous_window_end:
            print(f"⏭️ 데이터 변경 없음 (windowEnd: {current_window_end}), 저장 건너뜀")
            return [], False
        
        for prob_entry in crawl_result.get("prob_data", []):
            data = prob_entry.get("data", {}).get("data", {})
            probs = data.get("probs", [])
            
            if not probs:
                continue
            
            # 첫 번째 prob에서 메타데이터 추출
            first = probs[0]
            key = self._make_key(first)
            
            # 현재 데이터 집계
            current = self._aggregate_probs(probs)
            current_data[key] = current
            
            # 이전 데이터와 비교
            if key in self._previous:
                prev = self._previous[key]
                
                # 리셋 감지: 현재 count가 이전보다 작으면 패치로 인한 리셋
                total_prev = prev["success_count"] + prev["fail_count"] + prev["boom_count"]
                total_curr = current["success_count"] + current["fail_count"] + current["boom_count"]
                
                if total_curr < total_prev * 0.5:  # 50% 이상 감소하면 리셋으로 판단
                    reset_count += 1
                else:
                    # 정상적인 delta 계산
                    delta = self._calculate_delta(
                        timestamp=timestamp,
                        key=key,
                        prev=prev,
                        curr=current
                    )
                    if delta and delta.total_count > 0:
                        deltas.append(delta)
        
        # 리셋 감지: 절반 이상의 키에서 리셋이 감지되면 패치로 판단
        if self._previous and reset_count > len(self._previous) * 0.3:
            reset_detected = True
            print(f"🔄 패치 리셋 감지! ({reset_count}개 항목에서 count 감소)")
            # 리셋 시에는 delta를 저장하지 않음 (무의미한 데이터)
            deltas = []
        
        # 스냅샷 저장
        self._save_snapshot(timestamp, current_data, current_window_end)
        
        # Delta 저장 (리셋이 아닐 때만)
        if not reset_detected:
            self._save_deltas(deltas)
        
        # 캐시 업데이트
        self._previous = current_data
        
        return deltas, reset_detected

    
    def _make_key(self, prob: dict) -> str:
        """고유 키 생성: 이벤트_스타캐치_성"""
        trial_name = prob.get("trialid_name", "unknown")
        table_name = prob.get("probtable_name", "unknown")
        
        # 스타캐치 여부 추출
        starcatch = "catch_on" if "스타캐치" in trial_name or "Catch" in trial_name.lower() else "catch_off"
        if "스타캐치 O" in trial_name:
            starcatch = "catch_on"
        elif "스타캐치 X" in trial_name:
            starcatch = "catch_off"
        
        # 성 추출
        star = table_name.replace("성", "").strip()
        
        # 이벤트 타입 추출
        event = "unknown"
        if "이벤트 미적용" in trial_name:
            event = "no_event"
        elif "샤이닝" in trial_name:
            event = "shining"
        elif "파괴 확률" in trial_name:
            event = "boom_reduction"
        elif "비용" in trial_name:
            event = "cost_reduction"
        
        return f"{event}_{starcatch}_{star}"
    
    def _aggregate_probs(self, probs: list) -> dict:
        """prob 배열을 집계된 형태로 변환"""
        result = {
            "star": probs[0].get("probtable_name", "").replace("성", "").strip(),
            "event": probs[0].get("trialid_name", ""),
            "window_end": probs[0].get("windowEnd"),
            "success_count": 0,
            "fail_count": 0,
            "boom_count": 0,
            "success_rate": 0.0,
            "fail_rate": 0.0,
            "boom_rate": 0.0,
        }
        
        for p in probs:
            trial_result = p.get("trialresult_name", "")
            count = p.get("count", 0)
            prob_str = p.get("prob", "0%").replace("%", "")
            prob = float(prob_str) / 100 if prob_str else 0
            
            if "성공" in trial_result:
                result["success_count"] = count
                result["success_rate"] = prob
            elif "유지" in trial_result or "하락" in trial_result:
                result["fail_count"] = count
                result["fail_rate"] = prob
            elif "파괴" in trial_result:
                result["boom_count"] = count
                result["boom_rate"] = prob
        
        return result
    
    def _calculate_delta(self, timestamp: str, key: str, prev: dict, curr: dict) -> Optional[HourlyDelta]:
        """이전 스냅샷과 현재 스냅샷의 차이 계산"""
        success_delta = curr["success_count"] - prev["success_count"]
        fail_delta = curr["fail_count"] - prev["fail_count"]
        boom_delta = curr["boom_count"] - prev["boom_count"]
        total_delta = success_delta + fail_delta + boom_delta
        
        if total_delta <= 0:
            return None
        
        # key 파싱
        parts = key.split("_")
        event_type = parts[0] if len(parts) > 0 else "unknown"
        starcatch = parts[1] == "catch_on" if len(parts) > 1 else False
        star_level = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        
        actual_success = success_delta / total_delta if total_delta > 0 else 0
        actual_boom = boom_delta / total_delta if total_delta > 0 else 0
        
        return HourlyDelta(
            timestamp=timestamp,
            star_level=star_level,
            event_type=event_type,
            starcatch=starcatch,
            success_count=success_delta,
            fail_count=fail_delta,
            boom_count=boom_delta,
            total_count=total_delta,
            expected_success_rate=curr["success_rate"],
            actual_success_rate=actual_success,
            expected_boom_rate=curr["boom_rate"] if curr["boom_rate"] > 0 else None,
            actual_boom_rate=actual_boom if boom_delta > 0 else None
        )
    
    def _save_snapshot(self, timestamp: str, data: dict, window_end: str = ""):
        """스냅샷 저장"""
        entry = {
            "timestamp": timestamp,
            "window_end": window_end,
            "data_by_key": data
        }
        with open(self.snapshots_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        # 캐시 업데이트
        self._previous_window_end = window_end
    
    def _save_deltas(self, deltas: list[HourlyDelta]):
        """Delta 저장"""
        with open(self.deltas_file, "a", encoding="utf-8") as f:
            for d in deltas:
                f.write(json.dumps(asdict(d), ensure_ascii=False) + "\n")


class SessionManager:
    """패치 세션 관리"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_file = base_dir / "sessions.json"
        self.sessions = self._load_sessions()
    
    def _load_sessions(self) -> list[dict]:
        if self.sessions_file.exists():
            with open(self.sessions_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _save_sessions(self):
        with open(self.sessions_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, ensure_ascii=False, indent=2)
    
    def get_current_session(self) -> Path:
        """현재 활성 세션 디렉토리 반환"""
        if not self.sessions or not self.sessions[-1].get("active"):
            return self.start_new_session()
        
        current = self.sessions[-1]
        return self.base_dir / current["name"]
    
    def start_new_session(self, name: Optional[str] = None) -> Path:
        """새 패치 세션 시작"""
        # 이전 세션 비활성화
        if self.sessions:
            self.sessions[-1]["active"] = False
            self.sessions[-1]["end_date"] = datetime.now().isoformat()
        
        # 새 세션 생성
        if name is None:
            name = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        session = {
            "name": name,
            "start_date": datetime.now().isoformat(),
            "end_date": None,
            "active": True
        }
        self.sessions.append(session)
        self._save_sessions()
        
        session_dir = self.base_dir / name
        session_dir.mkdir(exist_ok=True)
        return session_dir
    
    def end_current_session(self):
        """현재 세션 종료 (패치 시 호출)"""
        if self.sessions and self.sessions[-1].get("active"):
            self.sessions[-1]["active"] = False
            self.sessions[-1]["end_date"] = datetime.now().isoformat()
            self._save_sessions()
    
    def list_sessions(self) -> list[dict]:
        """모든 세션 목록"""
        return self.sessions
