"""
Nexon Now 스타포스 데이터 크롤러
Playwright 기반으로 API 응답을 캡처하여 JSON으로 저장
"""
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright, Response

from .config import (
    PAGE_URL, 
    METADATA_API, 
    BASE_API_URL,
    DATA_DIR, 
    PAGE_LOAD_WAIT,
    REQUEST_TIMEOUT
)


class StarforceCrawler:
    """넥슨 나우 스타포스 통계 크롤러"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.metadata: Optional[dict] = None
        self.prob_data: list[dict] = []
        
    async def crawl(self) -> dict:
        """
        메인 크롤링 함수
        1. 페이지 로드하며 메타데이터 캡처
        2. 모든 /probs API 응답 캡처
        3. 결과 반환 및 저장
        """
        print(f"[{self._timestamp()}] 크롤링 시작...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            # API 응답 캡처 핸들러 등록
            page.on("response", self._handle_response)
            
            try:
                # 페이지 로드
                print(f"[{self._timestamp()}] 페이지 로드 중...")
                await page.goto(PAGE_URL, timeout=REQUEST_TIMEOUT)
                
                # 동적 콘텐츠 로드 대기
                await page.wait_for_timeout(PAGE_LOAD_WAIT)
                
                # 스크롤하여 추가 데이터 로드 (lazy loading 대응)
                await self._scroll_page(page)
                
                print(f"[{self._timestamp()}] 데이터 캡처 완료!")
                print(f"  - 메타데이터: {'✓' if self.metadata else '✗'}")
                print(f"  - 확률 데이터: {len(self.prob_data)}개 테이블")
                
            except Exception as e:
                print(f"[{self._timestamp()}] 에러 발생: {e}")
            finally:
                await browser.close()
        
        # 결과 구성
        result = self._build_result()
        
        # 저장
        self._save_result(result)
        
        return result
    
    async def _handle_response(self, response: Response):
        """API 응답 캡처 핸들러"""
        url = response.url
        
        try:
            # 메타데이터 API
            if METADATA_API in url and "/sub-pages/" not in url:
                self.metadata = await response.json()
                print(f"  [메타데이터] 캡처됨")
            
            # 확률 데이터 API (/probs)
            elif f"{BASE_API_URL}" in url and "/probs" in url:
                data = await response.json()
                # URL에서 테이블 정보 추출
                self.prob_data.append({
                    "url": url,
                    "data": data,
                    "captured_at": self._timestamp()
                })
                print(f"  [확률 데이터] 캡처됨 ({len(self.prob_data)}번째)")
                
        except Exception as e:
            # JSON 파싱 실패 등은 무시
            pass
    
    async def _scroll_page(self, page):
        """페이지 스크롤하여 lazy loading 콘텐츠 로드"""
        print(f"[{self._timestamp()}] 페이지 스크롤 중...")
        
        for i in range(5):
            await page.evaluate("window.scrollBy(0, 800)")
            await page.wait_for_timeout(1000)
    
    def _build_result(self) -> dict:
        """크롤링 결과 구성"""
        # 메타데이터에서 테이블 정보 추출
        tables = []
        if self.metadata:
            paragraphs = self._extract_paragraphs(self.metadata)
            for p in paragraphs:
                if p.get("type") == "AUTO_TABLE":
                    tables.append({
                        "name": p.get("tableName", "Unknown"),
                        "columns": p.get("columns", []),
                        "dataSources": p.get("dataSources", [])
                    })
        
        return {
            "crawled_at": self._timestamp(),
            "page_url": PAGE_URL,
            "tables_metadata": tables,
            "prob_data": self.prob_data,
            "summary": {
                "total_tables": len(tables),
                "total_prob_responses": len(self.prob_data)
            }
        }
    
    def _extract_paragraphs(self, data: dict) -> list:
        """메타데이터에서 모든 paragraphs 추출 (중첩 구조 처리)"""
        paragraphs = []
        
        # selectedSubPage에서 추출
        if "selectedSubPage" in data:
            paragraphs.extend(data["selectedSubPage"].get("paragraphs", []))
        
        # subPages 배열에서 추출
        if "subPages" in data:
            for sp in data["subPages"]:
                paragraphs.extend(sp.get("paragraphs", []))
        
        return paragraphs
    
    def _save_result(self, result: dict):
        """결과를 JSON 파일로 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = DATA_DIR / f"starforce_{timestamp}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"[{self._timestamp()}] 저장 완료: {filename}")
        
        # 최신 데이터 심볼릭 링크/복사
        latest_file = DATA_DIR / "latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def run_crawler(headless: bool = True) -> dict:
    """크롤러 실행 헬퍼 함수"""
    crawler = StarforceCrawler(headless=headless)
    return await crawler.crawl()


if __name__ == "__main__":
    # 직접 실행 시
    result = asyncio.run(run_crawler(headless=False))
    print(f"\n총 {result['summary']['total_prob_responses']}개 확률 테이블 수집됨")
