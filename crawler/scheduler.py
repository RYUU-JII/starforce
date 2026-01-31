"""
스케줄러: 1시간마다 자동 크롤링 + 데이터 처리 실행
"""
import asyncio
import schedule
import time
from datetime import datetime
from pathlib import Path

from .nexon_crawler import run_crawler
from .config import CRAWL_INTERVAL_HOURS, DATA_DIR
from .data_processor import DeltaCalculator, SessionManager


# 세션 베이스 디렉토리
SESSIONS_DIR = DATA_DIR.parent / "sessions"


async def scheduled_crawl():
    """스케줄에 의해 호출되는 크롤링 + 처리 함수 (자동 패치 감지)"""
    print(f"\n{'='*50}")
    print(f"스케줄 크롤링 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")
    
    try:
        # 1. 크롤링 (10분 타임아웃 설정)
        result = await asyncio.wait_for(run_crawler(headless=True), timeout=600.0)
        
        if not result.get("prob_data"):
            raise RuntimeError("크롤링 데이터가 없습니다 (prob_data is empty). 스냅샷 저장을 건너뜁니다.")
        
        # 2. 세션 관리 및 Delta 계산
        session_mgr = SessionManager(SESSIONS_DIR)
        session_dir = session_mgr.get_current_session()
        
        processor = DeltaCalculator(session_dir)
        deltas, reset_detected = processor.process_crawl_result(result)
        
        # 3. 리셋 감지 시 새 세션 시작
        if reset_detected:
            print(f"\n🔄 패치 감지! 새 세션을 자동으로 시작합니다...")
            new_session_name = datetime.now().strftime("patch_%Y%m%d_%H%M")
            session_dir = session_mgr.start_new_session(new_session_name)
            
            # 새 세션에 현재 데이터를 첫 스냅샷으로 저장
            new_processor = DeltaCalculator(session_dir)
            new_processor.process_crawl_result(result)
            
            print(f"✅ 새 세션 생성: {new_session_name}")
        
        print(f"크롤링 완료: {result['summary']['total_prob_responses']}개 테이블")
        print(f"Delta 계산: {len(deltas)}개 (세션: {session_dir.name})")
        
    except Exception as e:
        print(f"크롤링 실패: {e}")
        import traceback
        traceback.print_exc()



def run_scheduler():
    """스케줄러 실행"""
    print(f"넥슨 나우 스타포스 크롤러 시작")
    print(f"크롤링 간격: {CRAWL_INTERVAL_HOURS}시간")
    print(f"-" * 50)
    
    # 시작 시 즉시 1회 실행
    asyncio.run(scheduled_crawl())
    
    # 스케줄 등록 (wrapper 필요)
    def job():
        asyncio.run(scheduled_crawl())
        
    schedule.every(CRAWL_INTERVAL_HOURS).hours.do(job)
    
    print(f"\n다음 크롤링 예정: {CRAWL_INTERVAL_HOURS}시간 후")
    print(f"종료하려면 Ctrl+C를 누르세요.\n")
    
    # 스케줄 루프
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1분마다 체크
    except KeyboardInterrupt:
        print("\n크롤러 종료됨")


if __name__ == "__main__":
    run_scheduler()

