#!/usr/bin/env python3
"""palworld.gg 크롤러"""
import requests
import re
import json
import time
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "data" / "palworld"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

PAGES = [
    ("pals", "https://palworld.gg/pals"),
    ("items", "https://palworld.gg/items"),
    ("structures", "https://palworld.gg/structures"),
    ("technology-tree", "https://palworld.gg/technology-tree"),
    ("breeding-calculator", "https://palworld.gg/breeding-calculator"),
    ("tier-list", "https://palworld.gg/tier-list"),
    ("capture-rate", "https://palworld.gg/capture-rate"),
]


def clean_html(html: str) -> str:
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_page(name, url):
    print(f"  {name}...", end=" ", flush=True)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            text = clean_html(resp.text)
            if len(text) > 100:
                filepath = OUTPUT_DIR / f"palworld_gg_{name}.txt"
                filepath.write_text(text, encoding='utf-8')
                print(f"✅ ({len(text):,}자)")
                return {"title": name, "length": len(text)}
        print(f"⚠️ HTTP {resp.status_code}")
    except Exception as e:
        print(f"❌ {e}")
    return None


def fetch_individual_pals():
    """개별 팰 페이지 크롤링"""
    print("\n  🐾 개별 팰 페이지 수집 중...")
    # 먼저 팰 목록 가져오기
    try:
        resp = requests.get("https://palworld.gg/pals", headers=HEADERS, timeout=15)
        # HTML에서 팰 링크 추출
        pal_links = re.findall(r'href="/pal/([^"]+)"', resp.text)
        pal_links = list(set(pal_links))[:50]  # 최대 50개
        print(f"  → {len(pal_links)}개 팰 발견")
        
        results = []
        for i, pal in enumerate(pal_links, 1):
            print(f"    [{i}/{len(pal_links)}] {pal}...", end=" ", flush=True)
            try:
                r = requests.get(f"https://palworld.gg/pal/{pal}", headers=HEADERS, timeout=15)
                if r.status_code == 200:
                    text = clean_html(r.text)
                    if len(text) > 200:
                        filepath = OUTPUT_DIR / f"pal_{pal}.txt"
                        filepath.write_text(text, encoding='utf-8')
                        results.append({"title": f"pal_{pal}", "length": len(text)})
                        print(f"✅ ({len(text):,}자)")
                    else:
                        print("⏭️")
                else:
                    print(f"⚠️ {r.status_code}")
            except:
                print("❌")
            time.sleep(1.5)
        
        return results
    except Exception as e:
        print(f"  ❌ 팰 목록 가져오기 실패: {e}")
        return []


def main():
    print("🎮 palworld.gg 크롤러 시작")
    print(f"📁 저장: {OUTPUT_DIR}\n")
    
    results = []
    
    # 메인 페이지들
    print("📄 메인 페이지:")
    for name, url in PAGES:
        r = fetch_page(name, url)
        if r:
            results.append(r)
        time.sleep(2)
    
    # 개별 팰
    pal_results = fetch_individual_pals()
    results.extend(pal_results)
    
    # 메타데이터 업데이트
    meta_path = OUTPUT_DIR / "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    total = sum(r["length"] for r in results)
    print(f"\n📊 완료: {len(results)}개 문서, 총 {total:,}자")


if __name__ == "__main__":
    main()
