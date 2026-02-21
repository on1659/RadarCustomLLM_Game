#!/usr/bin/env python3
"""LLM RAG 자율 개선 시스템
- 질문 테스트
- 웹 검색으로 정답 검증
- 문제 진단 및 자동 개선
- 크롤링, 파라미터 조정 등
"""

import json
import random
import subprocess
import time
import re
from datetime import datetime
from pathlib import Path

# 설정
API_URL = "https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat"
LOG_DIR = Path.home() / ".openclaw/workspace/log"
LOG_FILE = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"
CRAWL_DIR = Path.home() / "Work/LLM/crawler"

# 질문 풀
QUESTIONS = {
    # 마인크래프트
    "마인크래프트 엔더드래곤": "minecraft",
    "마인크래프트 위더": "minecraft",
    "마인크래프트 네더라이트": "minecraft",
    "마인크래프트 다이아몬드": "minecraft",
    
    # 팰월드
    "팰월드 아누비스": "palworld",
    "팰월드 펜킹": "palworld",
    "팰월드 람볼": "palworld",
    
    # 오버워치
    "오버워치 한조": "overwatch",
    "오버워치 겐지": "overwatch",
    "오버워치 리퍼": "overwatch",
}

def test_rag(question):
    """RAG 서버에 질문"""
    cmd = [
        "curl", "-s", "-X", "POST", API_URL,
        "-H", "Content-Type: application/json",
        "-d", json.dumps({"query": question}),
        "--max-time", "30"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        if result.stdout:
            data = json.loads(result.stdout)
            return data.get("answer", "")
    except:
        pass
    return None

def web_search(query):
    """웹 검색으로 정답 확인 (Brave Search API 필요)"""
    # TODO: 실제 웹 검색 구현
    # 지금은 간단한 키워드 기반 검증
    
    # 임시: 알려진 정답 DB
    known_answers = {
        "팰월드 펜킹": "Penking은 팰월드의 얼음/물 속성 팰입니다. 펭귄 외형을 가지고 있습니다.",
        "오버워치 정크랫": "정크랫(Junkrat)은 오버워치의 공격 영웅으로 폭발물을 사용합니다.",
        "마인크래프트 네더라이트": "네더라이트는 고대 잔해를 채굴하여 얻을 수 있는 최강 광물입니다.",
    }
    
    return known_answers.get(query, "정답을 찾을 수 없음")

def compare_answers(rag_answer, correct_answer):
    """RAG 답변과 정답 비교"""
    if not rag_answer or not correct_answer:
        return 0, "답변 없음"
    
    # 키워드 추출 및 비교
    rag_keywords = set(re.findall(r'\w+', rag_answer.lower()))
    correct_keywords = set(re.findall(r'\w+', correct_answer.lower()))
    
    if len(correct_keywords) == 0:
        return 0, "정답 키워드 없음"
    
    overlap = rag_keywords & correct_keywords
    accuracy = len(overlap) / len(correct_keywords) * 100
    
    return accuracy, f"일치: {len(overlap)}/{len(correct_keywords)}"

def diagnose_problem(question, rag_answer, accuracy, game):
    """문제 진단"""
    problems = []
    solutions = []
    
    # 1. 데이터 누락 확인
    data_dir = CRAWL_DIR / "data" / game
    
    # 검색어 추출 (예: "팰월드 펜킹" → "penking")
    search_term = question.split()[-1].lower()
    
    # 파일 존재 확인
    if data_dir.exists():
        files = list(data_dir.glob("*.txt"))
        file_names = [f.stem.lower() for f in files]
        
        # 펜킹 → penking, 정크랫 → junkrat 매핑
        name_map = {
            "펜킹": "penking",
            "정크랫": "junkrat",
            "위더": "wither",
        }
        
        search_term = name_map.get(search_term, search_term)
        
        found = any(search_term in name for name in file_names)
        
        if not found:
            problems.append(f"❌ 데이터 누락: {search_term}")
            solutions.append(f"크롤링 필요: {game}/{search_term}")
    
    # 2. 답변 품질 확인
    if accuracy < 40:
        problems.append(f"❌ 정확도 매우 낮음: {accuracy:.0f}%")
        
        if "참고 자료에 없음" in rag_answer or "정보가 없습니다" in rag_answer:
            solutions.append("검색 알고리즘 개선 또는 데이터 추가 필요")
        else:
            solutions.append("잘못된 문서 검색됨 - 가중치 조정 필요")
    
    elif accuracy < 70:
        problems.append(f"⚠️ 정확도 낮음: {accuracy:.0f}%")
        solutions.append("검색 정확도 개선 필요")
    
    return problems, solutions

def auto_improve(solutions):
    """자동 개선 실행"""
    improvements = []
    
    for solution in solutions:
        if "크롤링 필요" in solution:
            # TODO: 자동 크롤링 실행
            improvements.append(f"📥 {solution} (수동 실행 필요)")
        
        elif "가중치 조정" in solution:
            # TODO: web.py 파라미터 조정
            improvements.append(f"⚙️ {solution} (수동 조정 필요)")
    
    return improvements

def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # 랜덤 질문 선택
    questions = random.sample(list(QUESTIONS.keys()), min(4, len(QUESTIONS)))
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    results = []
    all_problems = []
    all_solutions = []
    
    print(f"\n🎯 RAG 자율 개선 시스템 시작: {timestamp}\n")
    
    for i, q in enumerate(questions, 1):
        print(f"{i}. {q}")
        game = QUESTIONS[q]
        
        # RAG 테스트
        rag_answer = test_rag(q)
        print(f"   RAG: {rag_answer[:80] if rag_answer else '응답 없음'}...")
        
        # 웹 검색으로 정답 확인
        correct = web_search(q)
        print(f"   정답: {correct[:80]}...")
        
        # 비교
        accuracy, detail = compare_answers(rag_answer, correct)
        print(f"   정확도: {accuracy:.0f}% ({detail})")
        
        # 진단
        problems, solutions = diagnose_problem(q, rag_answer, accuracy, game)
        
        if problems:
            print(f"   문제: {', '.join(problems)}")
            print(f"   해결: {', '.join(solutions)}")
            all_problems.extend(problems)
            all_solutions.extend(solutions)
        
        results.append({
            "question": q,
            "rag": rag_answer[:100] if rag_answer else None,
            "correct": correct[:100],
            "accuracy": accuracy,
            "problems": problems,
            "solutions": solutions
        })
        
        print()
    
    # 자동 개선 시도
    if all_solutions:
        print("🔧 자동 개선 시도...")
        improvements = auto_improve(all_solutions)
        for imp in improvements:
            print(f"   {imp}")
    
    # 로그 기록
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n## [{timestamp}] RAG 자율 개선 테스트\n\n")
        
        for r in results:
            f.write(f"### {r['question']} ({r['accuracy']:.0f}%)\n")
            f.write(f"- RAG: {r['rag']}\n")
            f.write(f"- 정답: {r['correct']}\n")
            
            if r['problems']:
                f.write(f"- 문제: {', '.join(r['problems'])}\n")
                f.write(f"- 해결: {', '.join(r['solutions'])}\n")
            
            f.write("\n")
    
    print(f"\n📝 로그 저장: {LOG_FILE}")

if __name__ == "__main__":
    main()
