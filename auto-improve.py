#!/usr/bin/env python3
"""
정확도 모니터링 및 자동 개선
80% 이하면 improve_prompt 실행
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# 경로
LOG_DIR = Path(__file__).parent / "log"
WEB_PY = Path(__file__).parent / "rag/web.py"
IMPROVE_SCRIPT = Path.home() / ".openclaw/workspace/skills/llm-improve/scripts/improve_prompt.py"
IMPROVEMENT_LOG = Path(__file__).parent / "log/improvement-log.md"

def get_latest_qa_accuracy():
    """오늘 로그에서 최근 정확도 가져오기"""
    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{today}.md"
    
    if not log_file.exists():
        return None
    
    content = log_file.read_text()
    
    # "평균 정확도 XX%" 또는 "정확도 XX%" 패턴 찾기
    import re
    matches = re.findall(r'정확도[:\s]+(\d+)%', content)
    
    if not matches:
        return None
    
    # 최근 정확도 (마지막 값)
    return int(matches[-1])

def run_improve_prompt(accuracy):
    """improve_prompt.py 실행"""
    try:
        result = subprocess.run(
            ["python3", str(IMPROVE_SCRIPT), str(WEB_PY), str(accuracy)],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except Exception as e:
        return f"❌ improve_prompt 실행 실패: {e}"

def log_improvement(accuracy, output):
    """개선 로그 기록"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    log_entry = f"""
## [{timestamp}] 자동 개선 실행

**트리거**: 정확도 {accuracy}% (임계값: 80%)

### improve_prompt 결과:
```
{output}
```

---
"""
    
    # 로그 파일에 추가
    IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(IMPROVEMENT_LOG, "a") as f:
        f.write(log_entry)

def main():
    accuracy = get_latest_qa_accuracy()
    
    if accuracy is None:
        print("⚠️ QA 정확도 데이터를 찾을 수 없습니다")
        return
    
    print(f"📊 현재 정확도: {accuracy}%")
    
    if accuracy <= 80:
        print(f"🚨 정확도 {accuracy}% ≤ 80% → improve_prompt 실행")
        
        output = run_improve_prompt(accuracy)
        print(output)
        
        # 로그 기록
        log_improvement(accuracy, output)
        
        print(f"\n✅ 개선 로그 저장: {IMPROVEMENT_LOG}")
        print("\n💡 권장: 개선안을 검토하고 web.py 수정 후 서버 재시작")
    else:
        print(f"✅ 정확도 {accuracy}% > 80% → 개선 불필요")

if __name__ == "__main__":
    main()
