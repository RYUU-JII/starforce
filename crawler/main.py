"""
CLI 진입점: 크롤링 + 데이터 처리 + 분석 통합
"""
import argparse
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 상위 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.config import DATA_DIR
from crawler.nexon_crawler import run_crawler
from crawler.scheduler import run_scheduler
from crawler.data_processor import DeltaCalculator, SessionManager
from crawler.manipulation_detector import ManipulationDetector, run_analysis


# 세션 베이스 디렉토리
SESSIONS_DIR = DATA_DIR.parent / "sessions"


def crawl_and_process(headless: bool = True) -> dict:
    """크롤링 + 데이터 처리 실행 (자동 패치 감지)"""
    # 1. 크롤링
    result = asyncio.run(run_crawler(headless=headless))
    
    # 2. 세션 관리
    session_mgr = SessionManager(SESSIONS_DIR)
    session_dir = session_mgr.get_current_session()
    
    # 3. Delta 계산 (리셋 감지 포함)
    processor = DeltaCalculator(session_dir)
    deltas, reset_detected = processor.process_crawl_result(result)
    
    # 4. 리셋 감지 시 새 세션 시작
    if reset_detected:
        print(f"\n🔄 패치 감지! 새 세션을 자동으로 시작합니다...")
        new_session_name = datetime.now().strftime("patch_%Y%m%d_%H%M")
        session_dir = session_mgr.start_new_session(new_session_name)
        
        # 새 세션에 현재 데이터를 첫 스냅샷으로 저장
        new_processor = DeltaCalculator(session_dir)
        new_processor.process_crawl_result(result)
        
        print(f"✅ 새 세션 생성: {new_session_name}")
    
    print(f"\n{'='*50}")
    print(f"데이터 처리 완료")
    print(f"{'='*50}")
    print(f"세션: {session_dir.name}")
    print(f"새로운 Delta: {len(deltas)}개")
    if reset_detected:
        print(f"⚠️ 패치 리셋 감지로 인해 새 세션이 시작되었습니다.")
    
    return result



def analyze_current_session():
    """현재 세션 분석"""
    session_mgr = SessionManager(SESSIONS_DIR)
    session_dir = session_mgr.get_current_session()
    
    print(f"\n{'='*50}")
    print(f"조작 탐지 분석 시작")
    print(f"세션: {session_dir.name}")
    print(f"{'='*50}")
    
    summary = run_analysis(session_dir)
    
    print(f"\n분석 결과:")
    print(f"  - 분석된 성/이벤트 조합: {summary.total_star_levels_analyzed}")
    print(f"  - 의심 항목 수: {summary.suspicious_count}")
    print(f"  - 전체 의심 점수: {summary.overall_suspicion_score}/100")
    print(f"\n해석: {summary.interpretation}")
    
    return summary


def new_session(name: str = None):
    """새 패치 세션 시작"""
    session_mgr = SessionManager(SESSIONS_DIR)
    
    if name is None:
        name = datetime.now().strftime("patch_%Y%m%d")
    
    session_dir = session_mgr.start_new_session(name)
    print(f"새 세션 시작: {session_dir}")
    return session_dir


def list_sessions():
    """모든 세션 목록"""
    session_mgr = SessionManager(SESSIONS_DIR)
    sessions = session_mgr.list_sessions()
    
    print(f"\n{'='*50}")
    print(f"패치 세션 목록")
    print(f"{'='*50}")
    
    for i, s in enumerate(sessions, 1):
        status = "🟢 활성" if s.get("active") else "⚪ 종료"
        print(f"{i}. {s['name']} {status}")
        print(f"   시작: {s['start_date']}")
        if s.get("end_date"):
            print(f"   종료: {s['end_date']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="넥슨 나우 스타포스 데이터 크롤러 및 분석기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m crawler.main                    # 1회 크롤링 + 처리 (브라우저 표시)
  python -m crawler.main --headless         # 1회 크롤링 + 처리 (백그라운드)
  python -m crawler.main --schedule         # 스케줄러 모드 (1시간마다)
  python -m crawler.main --analyze          # 현재 세션 분석
  python -m crawler.main --new-session      # 새 패치 세션 시작
  python -m crawler.main --list-sessions    # 세션 목록 보기
        """
    )
    
    parser.add_argument(
        "--headless", 
        action="store_true",
        help="브라우저 창 없이 실행"
    )
    
    parser.add_argument(
        "--schedule", 
        action="store_true",
        help="스케줄러 모드 (1시간마다 자동 크롤링)"
    )
    
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="현재 세션 데이터 분석 (조작 탐지)"
    )
    
    parser.add_argument(
        "--new-session",
        nargs="?",
        const="",
        metavar="NAME",
        help="새 패치 세션 시작 (선택적 이름 지정)"
    )
    
    parser.add_argument(
        "--list-sessions",
        action="store_true",
        help="모든 세션 목록 보기"
    )
    
    args = parser.parse_args()
    
    if args.list_sessions:
        list_sessions()
    elif args.new_session is not None:
        name = args.new_session if args.new_session else None
        new_session(name)
    elif args.analyze:
        analyze_current_session()
    elif args.schedule:
        run_scheduler()
    else:
        # 기본: 1회 크롤링 + 처리
        result = crawl_and_process(headless=args.headless)
        
        # 결과 요약 출력
        print(f"\n{'='*50}")
        print(f"크롤링 결과 요약")
        print(f"{'='*50}")
        print(f"수집 시간: {result['crawled_at']}")
        print(f"확률 데이터: {result['summary']['total_prob_responses']}개")


if __name__ == "__main__":
    main()
