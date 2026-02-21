#!/usr/bin/env python3
"""
나무위키 크롤러 (Playwright 기반)
사용법: python3 namu_crawler_final.py
"""

import re
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 크롤링할 문서 목록
PAGES = {
    "overwatch": [
        "오버워치 2",
        "오버워치/영웅",
        "오버워치/게임 모드",
        "오버워치/전장",
        "오버워치/경쟁전",
        # 개별 영웅
        "트레이서(오버워치)",
        "겐지(오버워치)",
        "리퍼(오버워치)",
        "솔저: 76",
        "아나(오버워치)",
        "루시우(오버워치)",
        "머시(오버워치)",
        "라인하르트(오버워치)",
        "디바(오버워치)",
        "한조(오버워치)",
        "정크랫(오버워치)",
        "메이(오버워치)",
    ],
    "minecraft": [
        "마인크래프트",
        "마인크래프트/아이템",
        "마인크래프트/블록",
        "마인크래프트/몹",
        "마인크래프트/바이옴",
        "마인크래프트/마법 부여",
        "마인크래프트/양조",
        "마인크래프트/레드스톤",
        "위더",
        "엔더 드래곤",
        "네더라이트",
        "마인크래프트/마을",
        "마인크래프트/농사",
    ],
}


def clean_text(text: str) -> str:
    """텍스트 정리"""
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)
    text = re.sub(r'\{\{[^}]*\}\}', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_namu_page(page, title: str) -> str | None:
    """나무위키 문서 가져오기"""
    url = f"https://namu.wiki/w/{title}"
    
    try:
        print(f"    📡 로드...", end=" ", flush=True)
        page.goto(url, wait_until='networkidle', timeout=30000)
        print(f"렌더링...", end=" ", flush=True)
        page.wait_for_timeout(2000)  # 2초 대기
        
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


def crawl_game(game: str, pages: list[str]):
    """게임별 문서 크롤링"""
    game_dir = OUTPUT_DIR / game
    game_dir.mkdir(exist_ok=True)
    
    results = []
    
    print(f"\n{'='*60}")
    print(f"🎮 {game.upper()} 크롤링 시작 ({len(pages)}개 문서)")
    print(f"{'='*60}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for i, title in enumerate(pages, 1):
            print(f"  [{i}/{len(pages)}] {title}")
            
            text = fetch_namu_page(page, title)
            
            if text:
                # 개별 파일 저장
                safe_name = re.sub(r'[/\\:*?"<>|]', '_', title)
                filepath = game_dir / f"{safe_name}.txt"
                filepath.write_text(text, encoding='utf-8')
                
                results.append({
                    "title": title,
                    "file": str(filepath),
                    "length": len(text),
                })
            
            time.sleep(2)  # Rate limit
        
        browser.close()
    
    # 메타데이터 저장
    meta_path = game_dir / "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    total_chars = sum(r["length"] for r in results)
    print(f"\n📊 {game}: {len(results)}개 문서, 총 {total_chars:,}자 저장")
    
    return results


def main():
    print("🕷️ 나무위키 크롤러 (Playwright)")
    print(f"📁 저장 경로: {OUTPUT_DIR}\n")
    
    all_results = {}
    for game, pages in PAGES.items():
        all_results[game] = crawl_game(game, pages)
    
    # 전체 요약
    print(f"\n{'='*60}")
    print("📋 크롤링 완료 요약")
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
    print(f"  저장 위치: {OUTPUT_DIR}")
    print("\n✅ 완료! 이제 ingest.py로 벡터DB를 생성하세요.")


if __name__ == "__main__":
    main()
