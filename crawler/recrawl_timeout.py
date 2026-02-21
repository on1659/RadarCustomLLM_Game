#!/usr/bin/env python3
"""타임아웃된 문서 재크롤링"""

import re
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "data"

# 타임아웃된 문서 목록
TIMEOUT_PAGES = {
    "overwatch": [
        "오버워치 2",
        "한조(오버워치)",
        "루시우(오버워치)",
        "아나(오버워치)",
    ],
    "minecraft": [
        "위더",
        "엔더 드래곤",
        "네더라이트",
    ],
}


def clean_text(text: str) -> str:
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_namu_page(page, title: str, timeout: int = 60000) -> str | None:
    """나무위키 문서 가져오기 (타임아웃 연장)"""
    url = f"https://namu.wiki/w/{title}"
    
    try:
        print(f"    📡 로드 (timeout={timeout//1000}s)...", end=" ", flush=True)
        page.goto(url, wait_until='networkidle', timeout=timeout)
        print(f"렌더링...", end=" ", flush=True)
        page.wait_for_timeout(5000)  # 5초 대기 (원래 2초)
        
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'lxml')
        
        # 본문 찾기
        content_divs = soup.find_all(['div', 'article'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['wiki-content', 'wiki-article', 'document', 'content']
        ))
        
        if not content_divs:
            content_divs = [soup.body] if soup.body else []
        
        texts = []
        for div in content_divs:
            for tag in div.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            
            text = div.get_text(separator='\n', strip=True)
            if text and len(text) > 100:
                texts.append(text)
        
        final_text = max(texts, key=len) if texts else ""
        final_text = clean_text(final_text)
        
        if len(final_text) > 100:
            print(f"✅ ({len(final_text):,}자)")
            return final_text
        else:
            print("⏭️ 내용 부족")
            return None
            
    except Exception as e:
        print(f"❌ {e}")
        return None


def main():
    print("🔄 타임아웃된 문서 재크롤링 시작\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        all_results = {}
        
        for game, pages in TIMEOUT_PAGES.items():
            game_dir = OUTPUT_DIR / game
            game_dir.mkdir(exist_ok=True)
            
            results = []
            
            print(f"{'='*60}")
            print(f"🎮 {game.upper()}: {len(pages)}개 문서 재시도")
            print(f"{'='*60}")
            
            for i, title in enumerate(pages, 1):
                print(f"  [{i}/{len(pages)}] {title}")
                
                # 타임아웃 60초로 연장
                text = fetch_namu_page(page, title, timeout=60000)
                
                if text:
                    safe_name = re.sub(r'[/\\:*?"<>|]', '_', title)
                    filepath = game_dir / f"{safe_name}.txt"
                    filepath.write_text(text, encoding='utf-8')
                    
                    results.append({
                        "title": title,
                        "file": str(filepath),
                        "length": len(text),
                    })
                
                time.sleep(3)
            
            all_results[game] = results
            total = sum(r["length"] for r in results)
            print(f"\n📊 {game}: {len(results)}개 성공, 총 {total:,}자\n")
        
        browser.close()
    
    # 요약
    print(f"\n{'='*60}")
    print("📋 재크롤링 완료 요약")
    print(f"{'='*60}")
    
    total_docs = 0
    total_chars = 0
    for game, results in all_results.items():
        docs = len(results)
        chars = sum(r["length"] for r in results)
        total_docs += docs
        total_chars += chars
        print(f"  🎮 {game}: {docs}개 문서, {chars:,}자")
    
    print(f"\n  총합: {total_docs}개 문서, {total_chars:,}자")
    print("\n✅ 완료! 이제 ingest.py로 벡터DB를 재생성하세요.")


if __name__ == "__main__":
    main()
