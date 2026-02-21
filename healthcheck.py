#!/usr/bin/env python3
"""
LLM RAG 서버 헬스 체크 및 자동 재시작
5분마다 실행 권장
"""
import subprocess
import time
from pathlib import Path
from datetime import datetime

# 로그 파일
LOG_FILE = Path(__file__).parent / "log" / f"{datetime.now().strftime('%Y-%m-%d')}.md"

def log(message):
    """로그 기록"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}\n"
    print(log_entry.strip())
    
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(log_entry)

def check_process(name, pattern):
    """프로세스 실행 여부 확인"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception as e:
        log(f"❌ {name} 프로세스 체크 실패: {e}")
        return False

def start_llama_server():
    """llama-server 시작"""
    try:
        subprocess.run(
            "cd ~/llama.cpp && ./build/bin/llama-server "
            "-m ./models/Qwen2.5-3B-Instruct.Q4_K_M.gguf "
            "-c 4096 --port 8090 > /dev/null 2>&1 &",
            shell=True,
            executable="/bin/zsh"
        )
        log("✅ llama-server 재시작 완료")
        return True
    except Exception as e:
        log(f"❌ llama-server 재시작 실패: {e}")
        return False

def start_rag_server():
    """RAG 웹 서버 시작"""
    try:
        subprocess.run(
            "cd ~/Work/LLM/rag && source venv/bin/activate && "
            "python web.py > /dev/null 2>&1 &",
            shell=True,
            executable="/bin/zsh"
        )
        log("✅ RAG 서버 재시작 완료")
        return True
    except Exception as e:
        log(f"❌ RAG 서버 재시작 실패: {e}")
        return False

def start_ngrok():
    """ngrok 시작"""
    try:
        subprocess.run(
            "ngrok http 3334 --log=stdout > /dev/null 2>&1 &",
            shell=True,
            executable="/bin/zsh"
        )
        log("✅ ngrok 재시작 완료")
        return True
    except Exception as e:
        log(f"❌ ngrok 재시작 실패: {e}")
        return False

def main():
    log("🔍 서버 헬스 체크 시작")
    
    issues = []
    
    # 1. llama-server 체크
    if not check_process("llama-server", "llama-server.*8090"):
        log("⚠️ llama-server 죽음 감지")
        issues.append("llama-server")
        time.sleep(1)
        if start_llama_server():
            time.sleep(5)  # 초기화 대기
    
    # 2. RAG 서버 체크
    if not check_process("RAG 서버", "web.py"):
        log("⚠️ RAG 서버 죽음 감지")
        issues.append("RAG 서버")
        time.sleep(1)
        if start_rag_server():
            time.sleep(2)
    
    # 3. ngrok 체크
    if not check_process("ngrok", "ngrok.*3334"):
        log("⚠️ ngrok 죽음 감지")
        issues.append("ngrok")
        time.sleep(1)
        if start_ngrok():
            time.sleep(3)
    
    if issues:
        log(f"🚨 복구 완료: {', '.join(issues)}")
        return f"복구: {', '.join(issues)}"
    else:
        log("✅ 모든 서버 정상")
        return "정상"

if __name__ == "__main__":
    result = main()
    print(result)
