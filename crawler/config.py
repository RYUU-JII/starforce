"""
크롤러 설정
"""
from pathlib import Path

# API 엔드포인트
BASE_API_URL = "https://orng-api.nexon.com/api/services/maplestory"
PAGE_ID = "562d346f-f2c9-4425-bb08-12680e165251"

# 페이지 URL (브라우저용)
PAGE_URL = f"https://now.nexon.com/service/maplestory?page={PAGE_ID}"

# 메타데이터 API
METADATA_API = f"{BASE_API_URL}/pages/{PAGE_ID}"

# 저장 경로
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# 스케줄 설정 (시간 단위)
CRAWL_INTERVAL_HOURS = 1

# 요청 설정
REQUEST_TIMEOUT = 30000  # 30초
PAGE_LOAD_WAIT = 15000   # 15초 (페이지 로드 대기)
