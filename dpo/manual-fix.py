#!/usr/bin/env python3
"""DPO 학습용 수동 답변 작성 도구
pending 큐에서 하나씩 꺼내서 올바른 답변 작성
"""

import json
from pathlib import Path

DATASET_DIR = Path(__file__).parent / "dataset"
PENDING_FILE = DATASET_DIR / "pending.json"
CHOSEN_FILE = DATASET_DIR / "chosen.jsonl"


def load_pending():
    """pending 데이터 로드"""
    if PENDING_FILE.exists():
        with open(PENDING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_pending(data):
    """pending 데이터 저장"""
    with open(PENDING_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_chosen(item):
    """chosen 데이터 저장"""
    CHOSEN_FILE.parent.mkdir(exist_ok=True)
    with open(CHOSEN_FILE, 'a', encoding='utf-8') as f:
        data = {
            "question": item["question"],
            "rejected": item["rejected_answer"],
            "chosen": item["chosen_answer"],
            "accuracy_before": item["accuracy"]
        }
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def interactive_fix():
    """대화형 답변 작성"""
    pending = load_pending()
    pending_items = [item for item in pending if item["status"] == "pending"]
    
    if not pending_items:
        print("✅ 모든 답변이 완료되었습니다!")
        return
    
    print(f"\n📝 수정 대기 중: {len(pending_items)}개\n")
    
    for i, item in enumerate(pending_items):
        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(pending_items)}]")
        print(f"\n❓ 질문: {item['question']}")
        print(f"\n❌ 기존 답변 (정확도 {item['accuracy']}%):")
        print(f"{item['rejected_answer'][:200]}...")
        print(f"\n{'='*60}")
        
        print("\n옵션:")
        print("  1. 올바른 답변 작성")
        print("  2. 건너뛰기 (skip)")
        print("  3. 삭제 (이 질문 제외)")
        print("  q. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == 'q':
            print("\n💾 저장하고 종료합니다...")
            save_pending(pending)
            break
        
        elif choice == '1':
            print("\n✏️  올바른 답변을 입력하세요 (여러 줄 입력 가능, 빈 줄 + Enter로 완료):")
            lines = []
            while True:
                line = input()
                if not line and lines:  # 빈 줄이고 이미 입력이 있으면 종료
                    break
                lines.append(line)
            
            chosen_answer = "\n".join(lines).strip()
            
            if chosen_answer:
                item["chosen_answer"] = chosen_answer
                item["status"] = "completed"
                save_chosen(item)
                print("✅ 저장 완료!")
            else:
                print("⚠️  답변이 비어있어 건너뜁니다.")
        
        elif choice == '2':
            print("⏭️  건너뜁니다.")
            continue
        
        elif choice == '3':
            item["status"] = "deleted"
            print("🗑️  삭제됨.")
    
    save_pending(pending)
    
    # 통계
    completed = sum(1 for item in pending if item["status"] == "completed")
    remaining = sum(1 for item in pending if item["status"] == "pending")
    print(f"\n📊 진행 상황:")
    print(f"  - 완료: {completed}개")
    print(f"  - 남음: {remaining}개")


def batch_import():
    """배치 가져오기 (JSON 파일에서)"""
    print("\n📥 배치 가져오기")
    print("형식: [{\"question\": \"...\", \"rejected\": \"...\", \"chosen\": \"...\"}]")
    
    file_path = input("JSON 파일 경로: ").strip()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        count = 0
        for item in data:
            if all(k in item for k in ["question", "rejected", "chosen"]):
                save_chosen({
                    "question": item["question"],
                    "rejected_answer": item["rejected"],
                    "chosen_answer": item["chosen"],
                    "accuracy": 0
                })
                count += 1
        
        print(f"✅ {count}개 가져옴!")
    
    except Exception as e:
        print(f"❌ 오류: {e}")


if __name__ == "__main__":
    print("🛠️  DPO 수동 답변 작성 도구\n")
    
    while True:
        print("\n메뉴:")
        print("  1. 대화형 수정")
        print("  2. 배치 가져오기")
        print("  q. 종료")
        
        choice = input("\n선택: ").strip()
        
        if choice == '1':
            interactive_fix()
        elif choice == '2':
            batch_import()
        elif choice == 'q':
            break
