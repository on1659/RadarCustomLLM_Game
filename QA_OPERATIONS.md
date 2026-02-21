# LLM RAG QA 시스템 운영 가이드

자동화된 QA 테스트 시스템 운영 매뉴얼.

## ⚡ Quick Reference

```bash
# 📊 일일 체크 (30초)
ps aux | grep -E "llama-server|web\.py|ngrok" | grep -v grep  # 서버 3개 있나?
grep "🎯 테스트 시작" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | wc -l  # 오늘 몇 번?
tail -50 ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md  # 최근 결과

# 🔄 전체 재시작 (문제 시)
pkill llama-server; pkill -f "web.py"; pkill ngrok
cd ~/llama.cpp && ./build/bin/llama-server -m ./models/Qwen2.5-3B-Instruct.Q4_K_M.gguf -c 4096 --port 8090 > /dev/null 2>&1 &
sleep 5
cd ~/Work/LLM/rag && source venv/bin/activate && python web.py > /dev/null 2>&1 &
sleep 2
ngrok http 3334 --log=stdout > /dev/null 2>&1 &

# 🧪 수동 QA 테스트
cd ~/Work/LLM && python3 qa-test.py

# 📈 주간 분석 (월요일)
cd ~/.openclaw/workspace/skills/llm-improve && python3 scripts/analyze_qa.py ~/.openclaw/workspace/log/

# 🚨 크론 작업 문제
openclaw cron list  # 전체 크론 상태
openclaw cron run 82590edd-a405-426c-bb63-5463670c1e7a  # 헬스 체크 수동 실행
openclaw cron run 8935609d-a8e9-49e0-a9e1-196730ea8771  # QA 테스트 수동 실행
openclaw cron run 04b96b52-b13f-4438-8900-6352ba70b8e1  # 자동 개선 수동 실행

# 📈 개선 로그 확인
tail -100 ~/.openclaw/workspace/log/improvement-log.md

# 🔧 헬스 체크 수동 테스트
python3 ~/Work/LLM/healthcheck.py
```

---

## 시스템 구성

### 서버 스택
```
┌─────────────────────┐
│  llama-server       │  포트 8090 (Qwen2.5-3B-Instruct)
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  RAG 웹 서버        │  포트 3334 (Flask + FAISS)
│  (web.py)           │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  ngrok              │  공개 URL
│  포트 3334→3333     │  https://awhirl-preimpressive-carina.ngrok-free.dev
└─────────────────────┘
```

### 크론 작업

**1. 헬스 체크 (5분마다) 🆕**
- **작업 ID**: `82590edd-a405-426c-bb63-5463670c1e7a`
- **스크립트**: `~/Work/LLM/healthcheck.py`
- **로그**: `~/.openclaw/workspace/log/YYYY-MM-DD.md`
- **작동**: 서버 3개 (llama-server, web.py, ngrok) 프로세스 체크 → 죽으면 자동 재시작
- **알림**: 정상이면 조용, 복구 시에만 텔레그램 알림

**2. QA 테스트 (20분마다)**
- **작업 ID**: `8935609d-a8e9-49e0-a9e1-196730ea8771`
- **스크립트**: `~/Work/LLM/qa-test.py`
- **로그**: `~/.openclaw/workspace/log/YYYY-MM-DD.md`

**3. 자동 개선 (1시간마다)**
- **작업 ID**: `04b96b52-b13f-4438-8900-6352ba70b8e1`
- **스크립트**: `~/Work/LLM/auto-improve.py`
- **로그**: `~/.openclaw/workspace/log/improvement-log.md`
- **작동**: 정확도 80% 이하면 improve_prompt 자동 실행

## 일일 루틴 (30초)

**매일 오전 10시 권장**

### 1. 서버 상태 확인

```bash
# 전체 상태 한 번에
ps aux | grep -E "llama-server|web\.py|ngrok" | grep -v grep
```

**예상 출력:**
```
radar  <PID>  ... llama-server -m ... --port 8090
radar  <PID>  ... Python web.py
radar  <PID>  ... ngrok http 3334
```

**3개 모두 있으면 → OK ✅**  
**하나라도 없으면 → [전체 재시작](#전체-재시작-문제-발생-시) 필요 ⚠️**

### 2. 최근 QA 결과 확인

```bash
# 오늘 QA 테스트 몇 번 돌았나?
grep "🎯 테스트 시작" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | wc -l

# 최근 5개 결과
tail -50 ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md
```

**확인 사항:**
- ✅ 1시간마다 테스트 실행 중 (하루 24회 정도)
- ✅ "QA 통과" 나오는지
- ⚠️ "JSON 파싱 실패" 많으면 → 서버 문제
- ⚠️ 3시간 이상 로그 없으면 → 크론 멈춤

### 3. 크론 작업 동작 확인

```bash
# 크론 상태 (enabled: true 확인)
openclaw cron list | grep -A 5 "8935609d"

# 마지막 실행 시간 (1시간 이내여야 함)
openclaw cron runs 8935609d-a8e9-49e0-a9e1-196730ea8771 | head -3
```

**1시간 넘게 안 돌았으면:**
1. 서버 죽음 → 재시작
2. 크론 비활성화 → `openclaw cron update ... --enabled true`
3. 스크립트 오류 → 로그 확인

---

## 주간 루틴 (5분, 매주 월요일)

### 1. 지난 주 성능 분석

```bash
cd ~/.openclaw/workspace/skills/llm-improve
python3 scripts/analyze_qa.py ~/.openclaw/workspace/log/
```

**확인 사항:**
- 평균 정확도 70% 이상 → ✅ 유지
- 평균 정확도 40-70% → ⚠️ 모니터링
- 평균 정확도 <40% → 🚨 개선 필요

### 2. 트렌드 판단

**개선 추세 (40% → 45% → 50%):**
- 계속 모니터링만

**하락 추세 (60% → 55% → 50%):**
- 원인 파악 (데이터 변경? 파라미터 수정?)
- 3주 연속 하락이면 → 프롬프트 개선 검토

**정체 (<40%가 3일 이상):**
- 즉시 [프롬프트/파라미터 튜닝](#프롬프트파라미터-튜닝)

---

## 문제별 대응 (필요 시에만)

### 정확도 <80% (자동 개선 활성화됨)

**자동 프로세스:**
- 1시간마다 자동으로 improve_prompt 실행
- 개선안이 `improvement-log.md`에 기록됨
- 텔레그램으로 알림 수신

**수동 대응:**
```bash
# 1. 개선 로그 확인
tail -100 ~/.openclaw/workspace/log/improvement-log.md

# 2. 최신 개선안 적용 (web.py 수정)
nano ~/Work/LLM/rag/web.py

# 3. 서버 재시작
pkill -f "web.py"
cd ~/Work/LLM/rag && source venv/bin/activate && python web.py > /dev/null 2>&1 &

# 4. 1시간 후 재측정
```

### 정확도 <40% 지속 (3일 이상, 긴급)

```bash
# 파라미터까지 튜닝
cd ~/.openclaw/workspace/skills/llm-improve
python3 scripts/tune_params.py ~/Work/LLM/rag/web.py

# 프롬프트 전면 개선 (강력한 제약 패턴)
# references/prompt_patterns.md 참고
```

### 응답 시간 >5초 계속

```bash
# 파라미터 분석
python3 scripts/tune_params.py ~/Work/LLM/rag/web.py

# n_predict 감소 또는 모델 교체 고려
```

### 크론 작업이 3시간 이상 안 돌 때

```bash
# 1. 크론 활성화 확인
openclaw cron list | grep -A 5 "8935609d"

# 2. 비활성화되어 있으면
openclaw cron update 8935609d-a8e9-49e0-a9e1-196730ea8771 --enabled true

# 3. 활성화인데도 안 돌면 → 서버 문제
ps aux | grep -E "llama-server|web\.py|ngrok" | grep -v grep
# 3개 프로세스 없으면 → 전체 재시작

# 4. 수동 실행으로 확인
openclaw cron run 8935609d-a8e9-49e0-a9e1-196730ea8771
```

## 서버 관리

### 자동 재시작 (헬스 체크)

**5분마다 자동으로:**
- 서버 3개 프로세스 체크
- 죽은 서버 자동 재시작
- 복구 시 텔레그램 알림

**수동 실행 (즉시 체크):**
```bash
python3 ~/Work/LLM/healthcheck.py
```

### 전체 재시작 (문제 발생 시, 헬스 체크 실패할 때만)

**헬스 체크가 자동으로 복구하므로 수동 재시작은 드물게 필요**

```bash
# 1. 모든 서버 종료
pkill llama-server
pkill -f "web.py"
pkill ngrok

# 2. llama-server 시작
cd ~/llama.cpp
./build/bin/llama-server \
  -m ./models/Qwen2.5-3B-Instruct.Q4_K_M.gguf \
  -c 4096 \
  --port 8090 > /dev/null 2>&1 &

# 3. 5초 대기
sleep 5

# 4. RAG 서버 시작
cd ~/Work/LLM/rag
source venv/bin/activate
python web.py > /dev/null 2>&1 &

# 5. 2초 대기
sleep 2

# 6. ngrok 시작
ngrok http 3334 --log=stdout > /dev/null 2>&1 &

# 7. 확인
sleep 3
ps aux | grep -E "llama-server|web\.py|ngrok" | grep -v grep
```

### 개별 서버 재시작

**llama-server만:**
```bash
pkill llama-server
cd ~/llama.cpp && ./build/bin/llama-server \
  -m ./models/Qwen2.5-3B-Instruct.Q4_K_M.gguf \
  -c 4096 --port 8090 > /dev/null 2>&1 &
```

**RAG 서버만:**
```bash
pkill -f "web.py"
cd ~/Work/LLM/rag && source venv/bin/activate && \
  python web.py > /dev/null 2>&1 &
```

**ngrok만:**
```bash
pkill ngrok
ngrok http 3334 --log=stdout > /dev/null 2>&1 &
```

## QA 테스트

### 수동 테스트

```bash
# 즉시 실행
cd ~/Work/LLM
python3 qa-test.py

# 결과는 자동으로 ~/.openclaw/workspace/log/YYYY-MM-DD.md에 저장됨
```

### 크론 작업 제어

**헬스 체크 크론:**
```bash
# 수동 실행 (즉시 체크)
openclaw cron run 82590edd-a405-426c-bb63-5463670c1e7a

# 비활성화 (자동 복구 중단 - 권장하지 않음)
openclaw cron update 82590edd-a405-426c-bb63-5463670c1e7a --enabled false

# 재활성화
openclaw cron update 82590edd-a405-426c-bb63-5463670c1e7a --enabled true
```

**QA 테스트 크론:**
```bash
# 수동 실행
openclaw cron run 8935609d-a8e9-49e0-a9e1-196730ea8771

# 비활성화
openclaw cron update 8935609d-a8e9-49e0-a9e1-196730ea8771 --enabled false

# 재활성화
openclaw cron update 8935609d-a8e9-49e0-a9e1-196730ea8771 --enabled true
```

**자동 개선 크론:**
```bash
# 수동 실행
openclaw cron run 04b96b52-b13f-4438-8900-6352ba70b8e1

# 비활성화 (개선 중단)
openclaw cron update 04b96b52-b13f-4438-8900-6352ba70b8e1 --enabled false

# 재활성화
openclaw cron update 04b96b52-b13f-4438-8900-6352ba70b8e1 --enabled true
```

**전체 상태 확인:**
```bash
openclaw cron list
```

### QA 결과 분석

```bash
# llm-improve 스킬 사용
cd ~/.openclaw/workspace/skills/llm-improve
python3 scripts/analyze_qa.py ~/.openclaw/workspace/log/
```

출력 예시:
```
📊 QA 분석 리포트
총 테스트 세션: 24회
평균 정확도: 45.0%
평균 응답 시간: 3.20초

📈 최근 정확도 트렌드:
   40% → 42% → 45% → 48% → 50%
   ✅ 개선 추세

💡 권장 조치:
   [MEDIUM] 정확도 보통 → 프롬프트 미세 조정
```

## 데이터 업데이트

### 새 위키 페이지 추가

```bash
# 1. 나무위키 크롤링
cd ~/Work/LLM/crawler
python3 namu_crawler.py "페이지제목"

# 2. 벡터 DB 재생성
cd ~/Work/LLM/rag
source venv/bin/activate
python ingest.py

# 3. RAG 서버 재시작 (새 DB 로드)
pkill -f "web.py"
python web.py > /dev/null 2>&1 &

# 4. 테스트
curl -X POST "http://localhost:3334/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599" \
  -d '{"query": "새로추가한페이지 테스트", "session_id": "test"}' | jq .
```

### 벡터 DB 상태 확인

```bash
# DB 파일 확인
ls -lh ~/Work/LLM/rag/faiss_db/

# 청크 수 확인 (ingest.py 실행 시 출력)
cd ~/Work/LLM/rag && source venv/bin/activate && python ingest.py 2>&1 | grep "청크"
```

## 프롬프트/파라미터 튜닝

### 현재 설정 확인

```bash
# 프롬프트 분석
cd ~/.openclaw/workspace/skills/llm-improve
python3 scripts/improve_prompt.py ~/Work/LLM/rag/web.py

# 파라미터 분석
python3 scripts/tune_params.py ~/Work/LLM/rag/web.py
```

### 파라미터 수정

`~/Work/LLM/rag/web.py` 편집:

```python
payload = {
    "prompt": prompt,
    "n_predict": 400,        # 생성 토큰 수 (200-600)
    "temperature": 0.05,     # 창의성 (0.01-0.1)
    "repeat_penalty": 1.3,   # 반복 억제 (1.1-1.5)
    "stop": [...],
}
```

**수정 후 반드시:**
```bash
pkill -f "web.py"
cd ~/Work/LLM/rag && source venv/bin/activate && python web.py > /dev/null 2>&1 &
```

### A/B 테스트

```bash
# 1. 현재 설정으로 10회 테스트
for i in {1..10}; do
  python3 ~/Work/LLM/qa-test.py
  sleep 5
done

# 2. 평균 정확도 계산
grep "정확도" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | tail -10

# 3. 설정 변경 후 동일하게 10회 재테스트
# 4. 결과 비교 → 개선되었으면 유지, 아니면 롤백
```

## 문제 해결

### 🚨 크론 작업이 3시간 이상 안 돔

**증상:**
```bash
grep "🎯 테스트 시작" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | tail -1
# → 3시간 전 마지막 테스트
```

**진단 & 해결:**

1️⃣ **헬스 체크 확인 (5분마다 자동 복구됨)**
```bash
# 헬스 체크 로그 확인
grep "헬스 체크\|복구" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | tail -10
# 복구 기록 있으면 → 헬스 체크가 이미 처리 중
```

2️⃣ **크론 활성화 확인**
```bash
openclaw cron list
# enabled: false면 → openclaw cron update ... --enabled true
```

3️⃣ **서버 상태 확인**
```bash
ps aux | grep -E "llama-server|web\.py|ngrok" | grep -v grep
# 3개 프로세스 있어야 함 → 없으면 헬스 체크가 5분 내 재시작
```

4️⃣ **수동 실행 테스트**
```bash
cd ~/Work/LLM && python3 qa-test.py
# 오류 메시지 확인 → JSON 파싱 실패? LLM 오류?
```

5️⃣ **크론 강제 실행**
```bash
openclaw cron run 8935609d-a8e9-49e0-a9e1-196730ea8771
# 결과 로그 확인 → 오류 있으면 아래 트러블슈팅
```

---

### ❌ "JSON 파싱 실패" 반복

**원인:** RAG 서버가 HTML 또는 오류 응답

**해결:**
```bash
# 1. 서버 직접 테스트
curl http://localhost:3334/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599" \
  -d '{"query": "테스트", "session_id": "test"}'

# 2. HTML 응답 → web.py 죽음 → 재시작
pkill -f "web.py"
cd ~/Work/LLM/rag && source venv/bin/activate && python web.py > /dev/null 2>&1 &

# 3. 연결 거부 → 포트 문제 → 전체 재시작
```

---

### ⚡ "LLM 오류: Connection refused"

**원인:** llama-server가 꺼짐

**해결:**
```bash
# llama-server 재시작
pkill llama-server
cd ~/llama.cpp && ./build/bin/llama-server \
  -m ./models/Qwen2.5-3B-Instruct.Q4_K_M.gguf \
  -c 4096 --port 8090 > /dev/null 2>&1 &

# 5초 후 재테스트
sleep 5 && cd ~/Work/LLM && python3 qa-test.py
```

---

### 📉 정확도 갑자기 하락

**진단 순서:**
1. **최근 변경**: `git log ~/Work/LLM/rag/web.py` 확인
2. **로그 비교**: 어제 vs 오늘 답변 품질
3. **벡터 DB**: `ls ~/Work/LLM/rag/faiss_db/` 용량 확인 (갑자기 작아졌나?)
4. **모델**: `ps aux | grep llama-server` 모델 경로 확인

**복구:**
- 변경 롤백 또는 [프롬프트/파라미터 튜닝](#프롬프트파라미터-튜닝)

---

### 🐌 응답 시간 급증 (>10초)

1. **서버 부하**: `top` → llama-server CPU 100%? 메모리 부족?
2. **n_predict**: `grep "n_predict" ~/Work/LLM/rag/web.py` → 600 이상이면 감소
3. **메모리 누수**: web.py 메모리 2GB 넘으면 재시작

## 보안

### API 키 관리

```bash
# 환경변수 확인
echo $GAME_WIKI_API_KEY

# 없으면 추가 (~/.zshrc)
export GAME_WIKI_API_KEY="93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599"
source ~/.zshrc
```

### ngrok URL 변경 시

1. ngrok 재시작하면 URL 바뀜
2. 새 URL 확인:
   ```bash
   curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
   ```
3. 크론 작업 업데이트 필요 (qa-test.py에 하드코딩됨)

## 백업

### 중요 파일

```bash
# 매주 백업 권장
tar -czf llm-backup-$(date +%Y%m%d).tar.gz \
  ~/Work/LLM/rag/faiss_db \
  ~/Work/LLM/crawler/data \
  ~/Work/LLM/rag/web.py \
  ~/Work/LLM/qa-test.py \
  ~/.openclaw/workspace/log
```

### 복구

```bash
tar -xzf llm-backup-YYYYMMDD.tar.gz -C /
# 서버 전체 재시작
```

## 성능 목표

- **정확도**: 70% 이상 (주간 평균)
- **응답 시간**: 3초 이하 (평균)
- **가용성**: 1시간마다 테스트 실행 (하루 24회)
- **크론 안정성**: 3시간 이상 미실행 없음

### 빠른 체크 (매일)

```bash
# 오늘 테스트 몇 번 돌았나?
grep "🎯 테스트 시작" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | wc -l
# 목표: 시간당 1회 (현재 시각 기준)

# 최근 정확도
grep "정확도" ~/.openclaw/workspace/log/$(date +%Y-%m-%d).md | tail -3
```

### 주간 리포트 (월요일)

```bash
cd ~/.openclaw/workspace/skills/llm-improve
python3 scripts/analyze_qa.py ~/.openclaw/workspace/log/
```

## 연락처

문제 발생 시:
1. 이 가이드 확인
2. 로그 확인 (`~/.openclaw/workspace/log/`)
3. 서버 재시작 시도
4. 안 되면 OpenClaw에 "LLM 서버 문제" 메시지

---

**마지막 업데이트**: 2026-02-18  
**작성자**: 이더봇 ⚡
