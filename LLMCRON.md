# llmcron - LLM RAG 크론 관리 CLI

간단한 명령어로 LLM RAG 자동화 시스템 제어.

## 설치

```bash
# 이미 설치됨
# ~/bin/llmcron (PATH에 추가됨)
```

## 사용법

### 상태 확인

```bash
llmcron status
```

**출력 예시:**
```
📊 LLM RAG 크론 작업 상태

✅ LLM 서버 헬스 체크 및 자동 재시작 (5분마다) - 다음: 3분 후
✅ LLM RAG QA 자동 테스트 (20분마다) - 다음: 15분 후
✅ LLM 정확도 모니터링 및 자동 개선 (1시간마다) - 다음: 45분 후
```

### 크론 시작

```bash
llmcron start [QA주기_분]
```

**예시:**
```bash
llmcron start         # 기본 20분마다 QA
llmcron start 10      # 10분마다 QA
llmcron start 30      # 30분마다 QA
```

**실행 내용:**
- 헬스 체크: 5분마다 (고정)
- QA 테스트: 지정한 주기
- 자동 개선: 1시간마다 (고정)

### 크론 중지

```bash
llmcron stop
```

모든 크론 작업 즉시 중지.

### 크론 재시작

```bash
llmcron restart [QA주기_분]
```

**예시:**
```bash
llmcron restart       # 기본 20분으로 재시작
llmcron restart 15    # 15분으로 재시작
```

## 자주 묻는 질문

### Q. QA 주기만 바꾸고 싶어

```bash
llmcron start 10   # 10분으로 변경
```

다른 크론 (헬스 체크, 자동 개선)은 그대로 유지됨.

### Q. 잠깐 멈췄다가 다시 켜고 싶어

```bash
llmcron stop     # 중지
# ... 작업 ...
llmcron start    # 재개
```

### Q. 크론이 실제로 도는지 확인하려면?

```bash
llmcron status                    # 다음 실행 시간 확인
tail -f ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md   # 실시간 로그
```

### Q. 수동으로 QA 테스트 돌리려면?

```bash
cd ~/Work/LLM && python3 qa-test.py
```

크론과 별개로 즉시 실행.

### Q. 크론 ID를 직접 쓰고 싶어

```bash
# 헬스 체크
openclaw cron run 82590edd-a405-426c-bb63-5463670c1e7a

# QA 테스트
openclaw cron run 8935609d-a8e9-49e0-a9e1-196730ea8771

# 자동 개선
openclaw cron run 04b96b52-b13f-4438-8900-6352ba70b8e1
```

## 크론 ID 참고

- **헬스 체크**: `82590edd-a405-426c-bb63-5463670c1e7a`
- **QA 테스트**: `8935609d-a8e9-49e0-a9e1-196730ea8771`
- **자동 개선**: `04b96b52-b13f-4438-8900-6352ba70b8e1`

## 예시 워크플로우

### 개발 중 (빠른 테스트)

```bash
llmcron start 5    # 5분마다 QA
# 개발 작업...
llmcron stop       # 개발 끝
```

### 일반 운영 (표준)

```bash
llmcron start 20   # 20분마다 QA (권장)
```

### 야간 (부하 감소)

```bash
llmcron start 60   # 1시간마다 QA
```

## 트러블슈팅

### "command not found: llmcron"

```bash
# PATH 확인
echo $PATH | grep "$HOME/bin"

# 없으면 추가
export PATH="$HOME/bin:$PATH"

# 또는 새 셸 시작
zsh
```

### 크론이 안 돌아

```bash
llmcron status   # enabled가 ✅인지 확인

# 중지되어 있으면
llmcron start
```

### QA 주기가 안 바뀌어

```bash
llmcron restart 10   # stop → start로 확실히 적용
```

---

**위치**: `~/Work/LLM/llmcron`  
**심볼릭 링크**: `~/bin/llmcron`
