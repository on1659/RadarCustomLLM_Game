#!/usr/bin/env python3
"""DPO 학습용 데이터 수집 스크립트
qa-test.py 결과에서 정확도 낮은 답변 수집
"""

import json
import re
from pathlib import Path
from datetime import datetime, timedelta

# 설정
LOG_DIR = Path(__file__).parent.parent / "log"
DATASET_DIR = Path(__file__).parent / "dataset"
DATASET_DIR.mkdir(exist_ok=True)

REJECTED_FILE = DATASET_DIR / "rejected.jsonl"
CHOSEN_FILE = DATASET_DIR / "chosen.jsonl"
PENDING_FILE = DATASET_DIR / "pending.json"

# 정확도 임계값 (이하이면 수집)
ACCURACY_THRESHOLD = 70


def parse_qa_log(log_file):
    """QA 로그 파일 파싱"""
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 질문 블록 추출 (새 형식)
    # 예: 1. 마인크래프트 크리퍼 (12.1s, 50%)
    #    → ⚠️정확도보통(50%) 답변 내용...
    pattern = r'\d+\.\s+(.+?)\s+\([^,]+,\s+(\d+)%\)\s*\n\s*→\s+[^\n]*?\s+(.+?)(?=\[키워드:|\d+\.\s+|\n\n|$)'
    matches = re.findall(pattern, content, re.DOTALL)
    
    results = []
    for question, accuracy, answer in matches:
        accuracy = int(accuracy)
        if accuracy < ACCURACY_THRESHOLD:
            # 이모지 제거
            answer_clean = re.sub(r'[⚠️✅❌]', '', answer).strip()
            answer_clean = re.sub(r'정확도[^\s]+\s*', '', answer_clean).strip()
            answer_clean = re.sub(r'느림\([^)]+\)\s*', '', answer_clean).strip()
            
            results.append({
                "question": question.strip(),
                "answer": answer_clean[:500],  # 500자로 제한
                "accuracy": accuracy,
                "timestamp": datetime.now().isoformat()
            })
    
    return results


def collect_rejected():
    """최근 7일간 로그에서 rejected 데이터 수집"""
    rejected_data = []
    
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        log_file = LOG_DIR / f"{date.strftime('%Y-%m-%d')}.md"
        
        if log_file.exists():
            print(f"📖 {log_file.name} 파싱 중...")
            results = parse_qa_log(log_file)
            rejected_data.extend(results)
    
    # JSONL로 저장 (중복 제거)
    existing = set()
    if REJECTED_FILE.exists():
        with open(REJECTED_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                existing.add(data["question"])
    
    new_count = 0
    with open(REJECTED_FILE, 'a', encoding='utf-8') as f:
        for item in rejected_data:
            if item["question"] not in existing:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                existing.add(item["question"])
                new_count += 1
    
    print(f"✅ {new_count}개 새 rejected 답변 수집 (총 {len(existing)}개)")
    return new_count


def load_pending():
    """pending 데이터 로드 (수동 수정 대기 중)"""
    if PENDING_FILE.exists():
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_pending(data):
    """pending 데이터 저장"""
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def create_pending_queue():
    """rejected → pending 큐 생성 (수동 수정 대기)"""
    pending = load_pending()
    pending_questions = {item["question"] for item in pending}
    
    with open(REJECTED_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line)
            if data["question"] not in pending_questions:
                pending.append({
                    "question": data["question"],
                    "rejected_answer": data["answer"],
                    "accuracy": data["accuracy"],
                    "chosen_answer": None,  # 수동 입력 대기
                    "status": "pending"
                })
                pending_questions.add(data["question"])
    
    save_pending(pending)
    pending_count = sum(1 for item in pending if item["status"] == "pending")
    print(f"📋 수동 수정 대기 중: {pending_count}개")
    
    return pending


def show_stats():
    """현재 데이터셋 통계"""
    rejected_count = 0
    chosen_count = 0
    pending = load_pending()
    pending_count = sum(1 for item in pending if item["status"] == "pending")
    
    if REJECTED_FILE.exists():
        with open(REJECTED_FILE, 'r', encoding='utf-8') as f:
            rejected_count = sum(1 for _ in f)
    
    if CHOSEN_FILE.exists():
        with open(CHOSEN_FILE, 'r', encoding='utf-8') as f:
            chosen_count = sum(1 for _ in f)
    
    print("\n📊 DPO 데이터셋 현황:")
    print(f"  - Rejected: {rejected_count}개")
    print(f"  - Chosen: {chosen_count}개")
    print(f"  - Pending (수정 대기): {pending_count}개")
    print(f"  - 학습 가능 페어: {chosen_count}개")
    print(f"\n🎯 권장 학습량: 500쌍 (현재 진행률: {chosen_count/500*100:.1f}%)")


if __name__ == "__main__":
    print("🚀 DPO 데이터 수집 시작\n")
    
    # 1. Rejected 데이터 수집
    new_count = collect_rejected()
    
    # 2. Pending 큐 생성
    create_pending_queue()
    
    # 3. 통계 출력
    show_stats()
    
    print("\n✅ 수집 완료!")
    print("\n다음 단계:")
    print("  1. python dpo/manual-fix.py  # 수동 답변 작성")
    print("  2. python dpo/train.py       # DPO 학습 시작")
