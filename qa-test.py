#!/usr/bin/env python3
"""LLM RAG 서버 QA 자동 테스트 스크립트 (정확도 검증 포함)"""

import json
import random
import subprocess
import time
from datetime import datetime
from pathlib import Path

# 설정
API_URL = "https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat"
LOG_DIR = Path.home() / ".openclaw/workspace/log"
LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"

# 질문 풀 (게임명 명시 + 정답 키워드)
QUESTIONS = {
    # 마인크래프트
    "마인크래프트 엔더드래곤": ["보스", "엔더", "드래곤", "최종", "엔드"],
    "마인크래프트 위더": ["보스", "위더", "소환", "네더"],
    "마인크래프트 네더라이트": ["네더", "다이아몬드", "강한", "갑옷", "고대"],
    "마인크래프트 레드스톤": ["레드스톤", "회로", "전기", "신호"],
    "마인크래프트 다이아몬드": ["다이아몬드", "채굴", "광물", "Y좌표", "레벨"],
    "마인크래프트 크리퍼": ["크리퍼", "폭발", "초록", "몬스터"],
    "마인크래프트 좀비": ["좀비", "몬스터", "언데드", "밤"],
    "마인크래프트 엔더맨": ["엔더맨", "텔레포트", "엔더진주", "눈"],
    
    # 팰월드
    "팰월드 아누비스": ["아누비스", "땅", "팰", "에픽", "어둠"],
    "팰월드 펜킹": ["펜킹", "팰", "킹", "불"],
    "팰월드 람볼": ["람볼", "팰", "양", "노멀"],
    "팰월드 컬러리스": ["컬러리스", "팰", "드래곤"],
    "팰월드 제트래곤": ["제트래곤", "팰", "드래곤", "레전더리"],
    "팰월드 치키파이": ["치키", "팰", "닭", "불"],
    
    # 오버워치
    "오버워치 한조": ["한조", "영웅", "궁극기", "용", "화살"],
    "오버워치 겐지": ["겐지", "영웅", "사이보그", "닌자", "용검"],
    "오버워치 솔저:76": ["솔저", "76", "영웅", "힐", "전술"],
    "오버워치 리퍼": ["리퍼", "영웅", "죽음의 꽃", "샷건"],
    "오버워치 아나": ["아나", "영웅", "저격", "힐", "수면총"],
    "오버워치 라인하르트": ["라인하르트", "영웅", "방패", "탱커", "망치"],
    
    # 역질문
    "팰월드 펜킹 외형": ["펜킹", "모습", "외형", "생김새"],
    "마인크래프트 네더라이트 얻는 방법": ["네더라이트", "고대", "잔해", "채굴", "Y좌표"],
    "오버워치 한조의 궁극기": ["한조", "용", "궁극기", "화살"],
    "마인크래프트 엔더드래곤 잡는 법": ["엔더드래곤", "크리스탈", "엔드", "보스", "공략"],
}

def check_accuracy(question, answer):
    """답변 정확도 체크 (키워드 기반)"""
    if question not in QUESTIONS:
        return 0, []
    
    keywords = QUESTIONS[question]
    found = []
    
    answer_lower = answer.lower()
    for keyword in keywords:
        if keyword.lower() in answer_lower:
            found.append(keyword)
    
    accuracy = (len(found) / len(keywords)) * 100
    return accuracy, found

def test_question(question):
    """질문 테스트 (응답 시간 + 정확도 측정)"""
    cmd = [
        "curl", "-s", "-X", "POST", API_URL,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"query": question}),
        "--max-time", "30"
    ]
    
    start_time = time.time()
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        elapsed = time.time() - start_time
        
        if not result.stdout:
            return False, "응답 없음", elapsed, 0, []
        
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, f"JSON 파싱 실패", elapsed, 0, []
        
        if "answer" in response:
            answer = response["answer"]
            
            # 정확도 체크
            accuracy, found_keywords = check_accuracy(question, answer)
            
            # 답변 100자 요약
            summary = answer[:100].replace("\n", " ").strip()
            
            # 느린 응답 경고
            if elapsed > 5:
                summary = f"⚠️느림({elapsed:.1f}s) {summary}"
            
            # 정확도 낮으면 경고
            if accuracy < 40:
                summary = f"❌정확도낮음({accuracy:.0f}%) {summary}"
            elif accuracy < 70:
                summary = f"⚠️정확도보통({accuracy:.0f}%) {summary}"
            else:
                summary = f"✅정확({accuracy:.0f}%) {summary}"
            
            return True, summary, elapsed, accuracy, found_keywords
        else:
            return False, f"answer 필드 없음", elapsed, 0, []
            
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return False, f"타임아웃 (>{elapsed:.1f}s)", elapsed, 0, []
    except Exception as e:
        elapsed = time.time() - start_time
        return False, f"에러: {type(e).__name__}", elapsed, 0, []

def main():
    # 로그 디렉토리 생성
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 질문 선택 (풀에서 랜덤 4개)
    available_questions = list(QUESTIONS.keys())
    selected = random.sample(available_questions, 4)
    
    # 테스트 실행
    timestamp = datetime.now().strftime("%H:%M:%S")
    results = []
    success_count = 0
    total_time = 0
    total_accuracy = 0
    
    print(f"\n🎯 테스트 시작: {timestamp}")
    print(f"질문: {selected}\n")
    
    for i, q in enumerate(selected, 1):
        print(f"{i}. {q}...", flush=True)
        success, answer, elapsed, accuracy, keywords = test_question(q)
        total_time += elapsed
        
        if success:
            total_accuracy += accuracy
            keyword_str = f" [키워드: {', '.join(keywords)}]" if keywords else ""
            results.append(f"{i}. {q} ({elapsed:.1f}s, {accuracy:.0f}%)\n   → {answer}{keyword_str}")
            success_count += 1
            print(f"   {answer[:80]}...")
            if keywords:
                print(f"   🔍 발견: {', '.join(keywords)}")
        else:
            results.append(f"{i}. {q} ({elapsed:.1f}s)\n   → ❌ {answer}")
            print(f"   ❌ {answer}")
    
    avg_time = total_time / 4
    avg_accuracy = total_accuracy / success_count if success_count > 0 else 0
    
    # 로그 기록
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## [{timestamp}] LLM RAG QA 테스트\n\n")
        
        if success_count == 4:
            f.write(f"✅ QA 통과 (4/4) - 평균 {avg_time:.1f}s, 정확도 {avg_accuracy:.0f}%\n")
        else:
            f.write(f"❌ QA 실패 ({success_count}/4) - 평균 {avg_time:.1f}s\n")
        
        for result in results:
            f.write(f"{result}\n")
    
    # 요약 출력
    summary = "\n" + (
        f"✅ QA 통과 (4/4) - 평균 {avg_time:.1f}s, 정확도 {avg_accuracy:.0f}%" 
        if success_count == 4 
        else f"❌ QA 실패 ({success_count}/4)"
    )
    summary += "\n" + "\n".join(results)
    
    print(summary)
    print(f"\n📝 로그 저장: {LOG_FILE}")

if __name__ == "__main__":
    main()
