#!/usr/bin/env python3
"""palworld.gg 크롤러 V2 — JavaScript 렌더링 지원"""
import re
import json
import time
from pathlib import Path
from requests_html import HTMLSession
from bs4 import BeautifulSoup

OUTPUT_DIR = Path(__file__).parent / "data" / "palworld"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("pals", "https://palworld.gg/pals"),
    ("items", "https://palworld.gg/items"),
    ("structures", "https://palworld.gg/structures"),
    ("technology-tree", "https://palworld.gg/technology-tree"),
    ("breeding-calculator", "https://palworld.gg/breeding-calculator"),
    ("tier-list", "https://palworld.gg/tier-list"),
    ("capture-rate", "https://palworld.gg/capture-rate"),
]


def clean_text(text: str) -> str:
    """텍스트 정리"""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def fetch_page(session: HTMLSession, name: str, url: str) -> dict | None:
    """페이지 가져오기 (JavaScript 렌더링)"""
    print(f"  📡 {name}...", end=" ", flush=True)
    
    try:
        resp = session.get(url, timeout=30)
        
        if resp.status_code != 200:
            print(f"⚠️ HTTP {resp.status_code}")
            return None
        
        # JavaScript 렌더링
        print(f"🎨 렌더링...", end=" ", flush=True)
        resp.html.render(timeout=20, sleep=2)
        
        # BeautifulSoup으로 본문 추출
        soup = BeautifulSoup(resp.html.html, 'lxml')
        
        # 스크립트/스타일 제거
        for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        
        # 본문 추출
        text = soup.get_text(separator='\n', strip=True)
        text = clean_text(text)
        
        if len(text) > 200:
            filepath = OUTPUT_DIR / f"palworld_gg_{name}.txt"
            filepath.write_text(text, encoding='utf-8')
            print(f"✅ ({len(text):,}자)")
            return {"title": name, "length": len(text)}
        else:
            print("⏭️ 내용 부족")
            return None
            
    except Exception as e:
        print(f"❌ {e}")
        return None


def fetch_individual_pals(session: HTMLSession):
    """개별 팰 페이지 크롤링"""
    print("\n  🐾 개별 팰 페이지 수집 중...")
    
    try:
        resp = session.get("https://palworld.gg/pals", timeout=30)
        resp.html.render(timeout=20, sleep=2)
        
        # 팰 링크 추출
        soup = BeautifulSoup(resp.html.html, 'lxml')
        pal_links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/pal/' in href:
                pal_name = href.split('/pal/')[-1].split('?')[0].split('#')[0]
                if pal_name and pal_name not in pal_links:
                    pal_links.append(pal_name)
        
        pal_links = pal_links[:50]  # 최대 50개
        print(f"  → {len(pal_links)}개 팰 발견\n")
        
        results = []
        for i, pal in enumerate(pal_links, 1):
            print(f"    [{i}/{len(pal_links)}] {pal}...", end=" ", flush=True)
            
            try:
                r = session.get(f"https://palworld.gg/pal/{pal}", timeout=30)
                if r.status_code == 200:
                    r.html.render(timeout=20, sleep=1)
                    soup = BeautifulSoup(r.html.html, 'lxml')
                    
                    # 스크립트/스타일 제거
                    for tag in soup.find_all(['script', 'style', 'nav', 'footer', 'header']):
                        tag.decompose()
                    
                    text = soup.get_text(separator='\n', strip=True)
                    text = clean_text(text)
                    
                    if len(text) > 200:
                        filepath = OUTPUT_DIR / f"pal_{pal}.txt"
                        filepath.write_text(text, encoding='utf-8')
                        results.append({"title": f"pal_{pal}", "length": len(text)})
                        print(f"✅ ({len(text):,}자)")
                    else:
                        print("⏭️")
                else:
                    print(f"⚠️ {r.status_code}")
            except Exception as e:
                print(f"❌ {e}")
            
            time.sleep(2)
        
        return results
        
    except Exception as e:
        print(f"  ❌ 팰 목록 가져오기 실패: {e}")
        return []


def main():
    print("🎮 palworld.gg 크롤러 V2 (JavaScript 렌더링 지원)")
    print(f"📁 저장: {OUTPUT_DIR}")
    print("⏱️  렌더링으로 인해 시간이 걸립니다...\n")
    
    session = HTMLSession()
    results = []
    
    # 메인 페이지들
    print("📄 메인 페이지:")
    for name, url in PAGES:
        r = fetch_page(session, name, url)
        if r:
            results.append(r)
        time.sleep(3)
    
    # 개별 팰
    pal_results = fetch_individual_pals(session)
    results.extend(pal_results)
    
    session.close()
    
    # 메타데이터 업데이트
    meta_path = OUTPUT_DIR / "_meta.json"
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    total = sum(r["length"] for r in results)
    print(f"\n📊 완료: {len(results)}개 문서, 총 {total:,}자")
    print("\n✅ 완료! 이제 ingest.py로 벡터DB를 생성하세요.")


if __name__ == "__main__":
    main()
