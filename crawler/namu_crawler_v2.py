#!/usr/bin/env python3
"""
나무위키 크롤러 V2 — JavaScript 렌더링 지원
사용법: python3 namu_crawler_v2.py
"""

import re
import json
import time
from pathlib import Path
from urllib.parse import quote
from requests_html import HTMLSession
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)

# 크롤링할 문서 목록
PAGES = {
    "palworld": [
        "팰월드",
        "팰월드/팰",
        "팰월드/도감",
        "팰월드/보스",
        "팰월드/기술",
        "팰월드/거점",
        "팰월드/아이템",
        "팰월드/무기",
        "팰월드/방어구",
        "팰월드/건축",
        "팰월드/탈것",
        "팰월드/번식",
        "팰월드/팁",
        "펜킹(팰월드)",
    ],
    "overwatch": [
        "오버워치 2",
        "오버워치/영웅",
        "오버워치/영웅/돌격",
        "오버워치/영웅/피해",
        "오버워치/영웅/지원",
        "오버워치/게임 모드",
        "오버워치/전장",
        "오버워치/아이템",
        "오버워치/경쟁전",
        # 개별 영웅
        "트레이서(오버워치)",
        "겐지(오버워치)",
        "리퍼(오버워치)",
        "솔저: 76",
        "파라(오버워치)",
        "아나(오버워치)",
        "루시우(오버워치)",
        "머시(오버워치)",
        "라인하르트(오버워치)",
        "디바(오버워치)",
        "위도우메이커(오버워치)",
        "한조(오버워치)",
        "정크랫(오버워치)",
        "메이(오버워치)",
        "바스티온(오버워치)",
    ],
    "minecraft": [
        "마인크래프트",
        "마인크래프트/아이템",
        "마인크래프트/블록",
        "마인크래프트/몹",
        "마인크래프트/바이옴",
        "마인크래프트/인챈트",
        "마인크래프트/양조",
        "마인크래프트/레드스톤",
        "마인크래프트/엔더 드래곤",
        "마인크래프트/위더",
        "마인크래프트/네더",
        "마인크래프트/네더라이트",
        "마인크래프트/엔드",
        "마인크래프트/마을",
        "마인크래프트/농사",
        "마인크래프트/조합법",
        "마인크래프트/팁",
        "위더",
        "네더라이트",
    ],
}


def clean_text(text: str) -> str:
    """텍스트 정리"""
    # 나무위키 문법 정리
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)  # [[링크|텍스트]] → 텍스트
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)  # [[링크]] → 링크
    text = re.sub(r'\{\{[^}]*\}\}', '', text)  # {{매크로}} 제거
    # 여러 공백/줄바꿈 정리
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_namu_page(session: HTMLSession, title: str) -> str | None:
    """나무위키 문서 가져오기 (JavaScript 렌더링)"""
    encoded = quote(title, safe='')
    url = f"https://namu.wiki/w/{encoded}"
    
    try:
        print(f"    📡 요청 중...", end=" ", flush=True)
        resp = session.get(url, timeout=30)
        
        if resp.status_code != 200:
            print(f"⚠️ HTTP {resp.status_code}")
            return None
        
        # JavaScript 렌더링 (시간 소요)
        print(f"🎨 렌더링...", end=" ", flush=True)
        resp.html.render(timeout=20, sleep=2)
        
        # BeautifulSoup으로 본문 추출
        soup = BeautifulSoup(resp.html.html, 'lxml')
        
        # 나무위키 본문 영역 찾기
        content_divs = soup.find_all(['div', 'article'], class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['wiki-content', 'wiki-article', 'document', 'content']
        ))
        
        if not content_divs:
            # 클래스 없이 전체 텍스트 추출
            content_divs = [soup.body] if soup.body else []
        
        # 텍스트 추출
        texts = []
        for div in content_divs:
            # 스크립트/스타일 태그 제거
            for tag in div.find_all(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            
            text = div.get_text(separator='\n', strip=True)
            if text and len(text) > 100:
                texts.append(text)
        
        if not texts:
            print("⏭️ 본문 없음")
            return None
        
        # 가장 긴 텍스트 선택
        final_text = max(texts, key=len)
        final_text = clean_text(final_text)
        
        return final_text if len(final_text) > 100 else None
        
    except Exception as e:
        print(f"❌ {e}")
        return None


def crawl_game(game: str, pages: list[str]):
    """게임별 문서 크롤링"""
    game_dir = OUTPUT_DIR / game
    game_dir.mkdir(exist_ok=True)
    
    results = []
    session = HTMLSession()
    
    print(f"\n{'='*60}")
    print(f"🎮 {game.upper()} 크롤링 시작 ({len(pages)}개 문서)")
    print(f"{'='*60}")
    
    for i, title in enumerate(pages, 1):
        print(f"  [{i}/{len(pages)}] {title}")
        
        text = fetch_namu_page(session, title)
        
        if text and len(text) > 100:
            # 개별 파일 저장
            safe_name = re.sub(r'[/\\:*?"<>|]', '_', title)
            filepath = game_dir / f"{safe_name}.txt"
            filepath.write_text(text, encoding='utf-8')
            
            results.append({
                "title": title,
                "file": str(filepath),
                "length": len(text),
            })
            print(f"    ✅ 저장 완료 ({len(text):,}자)\n")
        else:
            print(f"    ⏭️ 스킵 (내용 부족)\n")
        
        time.sleep(3)  # 3초 대기 (rate limit)
    
    session.close()
    
    # 게임별 메타데이터 저장
    meta_path = game_dir / "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    total_chars = sum(r["length"] for r in results)
    print(f"\n📊 {game}: {len(results)}개 문서, 총 {total_chars:,}자 저장")
    
    return results


def main():
    print("🕷️ 나무위키 게임 크롤러 V2 (JavaScript 렌더링 지원)")
    print(f"📁 저장 경로: {OUTPUT_DIR}")
    print("⏱️  렌더링으로 인해 시간이 걸립니다...\n")
    
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
