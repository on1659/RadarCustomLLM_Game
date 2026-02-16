#!/usr/bin/env python3
"""
나무위키 크롤러 — 게임 문서를 텍스트로 저장
사용법: python3 namu_crawler.py
"""

import requests
import re
import json
import os
import time
from pathlib import Path
from urllib.parse import quote

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
        "마인크래프트/엔드",
        "마인크래프트/마을",
        "마인크래프트/농사",
        "마인크래프트/조합법",
        "마인크래프트/팁",
    ],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def clean_namu_text(raw_html: str) -> str:
    """나무위키 HTML에서 본문 텍스트 추출"""
    # HTML 태그 제거
    text = re.sub(r'<script[^>]*>.*?</script>', '', raw_html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', raw_html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    # 나무위키 문법 정리
    text = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', text)  # [[링크|텍스트]] → 텍스트
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)  # [[링크]] → 링크
    text = re.sub(r'\{\{[^}]*\}\}', '', text)  # {{매크로}} 제거
    text = re.sub(r'&#\d+;', ' ', text)  # HTML 엔티티
    text = re.sub(r'&[a-z]+;', ' ', text)
    # 여러 공백/줄바꿈 정리
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_namu_page(title: str) -> str | None:
    """나무위키 문서 가져오기 (API 사용)"""
    encoded = quote(title, safe='')
    
    # 나무위키 raw 문서 시도
    url = f"https://namu.wiki/w/{encoded}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return clean_namu_text(resp.text)
        else:
            print(f"  ⚠️ HTTP {resp.status_code}: {title}")
            return None
    except Exception as e:
        print(f"  ❌ 에러: {title} — {e}")
        return None


def crawl_game(game: str, pages: list[str]):
    """게임별 문서 크롤링"""
    game_dir = OUTPUT_DIR / game
    game_dir.mkdir(exist_ok=True)
    
    results = []
    
    print(f"\n{'='*50}")
    print(f"🎮 {game.upper()} 크롤링 시작 ({len(pages)}개 문서)")
    print(f"{'='*50}")
    
    for i, title in enumerate(pages, 1):
        print(f"  [{i}/{len(pages)}] {title}...", end=" ", flush=True)
        
        text = fetch_namu_page(title)
        if text and len(text) > 100:  # 너무 짧으면 스킵
            # 개별 파일 저장
            safe_name = re.sub(r'[/\\:*?"<>|]', '_', title)
            filepath = game_dir / f"{safe_name}.txt"
            filepath.write_text(text, encoding='utf-8')
            
            results.append({
                "title": title,
                "file": str(filepath),
                "length": len(text),
            })
            print(f"✅ ({len(text):,}자)")
        else:
            print(f"⏭️ 스킵 (내용 없음)")
        
        time.sleep(2)  # 2초 대기 (rate limit)
    
    # 게임별 메타데이터 저장
    meta_path = game_dir / "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    total_chars = sum(r["length"] for r in results)
    print(f"\n📊 {game}: {len(results)}개 문서, 총 {total_chars:,}자 저장")
    
    return results


def main():
    print("🕷️ 나무위키 게임 크롤러 시작")
    print(f"📁 저장 경로: {OUTPUT_DIR}")
    
    all_results = {}
    for game, pages in PAGES.items():
        all_results[game] = crawl_game(game, pages)
    
    # 전체 요약
    print(f"\n{'='*50}")
    print("📋 크롤링 완료 요약")
    print(f"{'='*50}")
    
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
    print("\n✅ 완료! RAG에 이 데이터를 넣으면 됩니다.")


if __name__ == "__main__":
    main()
