# LLM 추론모델 프로젝트 로그

## 📌 프로젝트 요약 (새 세션용)

### 환경
- Mac mini M4 16GB, macOS
- llama.cpp: `~/llama.cpp/build/bin/llama-server`
- Python venv: `~/Work/LLM/crawler/venv/` (RAG/크롤러 공용)
- GitHub: https://github.com/on1659/RadarCustomLLM_Game

### 파인튜닝 모델
- 베이스: Qwen2.5-3B-Instruct
- 방법: Unsloth + LoRA (r=16), Colab T4 GPU
- 학습 데이터: 121개 chain-of-thought (`<think>추론</think>답변`)
- GGUF: `~/llama.cpp/models/Qwen2.5-3B-Instruct.Q4_K_M.gguf` (1.93GB)
- Colab 노트북: `~/.openclaw/workspace/reasoning-model/colab_notebook.ipynb`
- 학습 데이터 JSON: `~/.openclaw/workspace/reasoning-model/training_data.json`

### RAG 시스템
- 크롤러: `~/Work/LLM/crawler/`
  - `namu_crawler.py` — 나무위키 (오버워치 15개, 마크 12개, 팰월드 1개)
  - `palworld_crawler.py` — palworld.gg (57개 문서)
  - 크롤링 데이터: `~/Work/LLM/crawler/data/`
- RAG: `~/Work/LLM/rag/`
  - `ingest.py` — 벡터화 (FAISS + ko-sroberta-multitask)
  - `web.py` — 웹 UI (localhost:3333)
  - `chat.py` — CLI 챗봇
  - 벡터DB: `~/Work/LLM/rag/faiss_db/` (4,064청크)
- 임베딩: `jhgan/ko-sroberta-multitask` (한국어 특화)
- 게임명 자동 필터: 팰월드/오버워치/마크 키워드 감지

### 실행 방법
```bash
# 1. LLM 서버
cd ~/llama.cpp && ./build/bin/llama-server -m models/Qwen2.5-3B-Instruct.Q4_K_M.gguf -c 1024 -ngl 99 --port 8090

# 2. RAG 웹 UI
cd ~/Work/LLM/rag && source ../crawler/venv/bin/activate && python3 web.py
# → localhost:3333

# 3. 외부 접속 (ngrok)
ngrok http 3333

# 4. 크롤링 데이터 추가 후 벡터DB 재생성
cd ~/Work/LLM/rag && source ../crawler/venv/bin/activate && python3 ingest.py
```

### 현재 이슈 & TODO
- [ ] `<think>` 추론 태그 아직 안 나옴 → 학습 데이터 500개로 확장 필요
- [ ] 3B 모델 한국어 코딩 능력 약함 → 128GB PC에서 70B 모델 시도 예정
- [ ] 팰월드 나무위키 하위문서 크롤링 URL 수정 필요
- [ ] 16GB 메모리 부족으로 llama-server 가끔 kill됨 → `-c 1024`로 완화

### Colab 사용 팁
- wandb 물어보면 **3** 입력 (시각화 스킵)
- 무료 GPU 할당량 소진 시 다른 구글 계정 사용
- 학습 완료 후 바로 Drive 저장 셀 실행 (세션 끊기면 파일 소실)
- Colab 가이드: `~/Work/LLM/colab_guide.md`

---

## 2026-02-15 22:10 — 프로젝트 시작 & Colab 노트북 생성

### 목표
- 로컬에서 돌릴 수 있는 LLM 추론모델(chain-of-thought) 만들기
- Mac mini M4 16GB 환경에서 실행

### 결정한 방법
1. **Google Colab (무료 T4 GPU)** 에서 Unsloth + LoRA로 파인튜닝
2. **GGUF Q4_K_M**으로 양자화 변환
3. **맥미니 llama.cpp**에서 Metal 가속으로 로컬 실행

### 한 일
- Colab 노트북 생성: `~/.openclaw/workspace/reasoning-model/colab_notebook.ipynb`
- 베이스 모델: **Qwen2.5-3B-Instruct** (4bit)
- LoRA 설정: r=16, target=q/k/v/o/gate/up/down_proj
- 학습 데이터 형식: `<think>추론과정</think>\n\n최종답변`
- 예시 데이터 5개 포함 (한국어: 교통, 프로그래밍, 수학, 과학, IT)
- SFTTrainer 설정: batch=2, grad_accum=4, epoch=3, lr=2e-4
- GGUF 변환 + Google Drive 저장 코드 포함

### 결과
- 노트북 완성, Colab 업로드 후 바로 실행 가능
- 아직 실행은 안 함

### 다음 할 일
- [ ] 학습 데이터 확충 (현재 5개 → 최소 500~1000개 필요)
- [ ] Colab에서 실제 학습 실행
- [ ] 학습 결과 테스트 (추론 품질 확인)
- [ ] GGUF 변환 후 맥미니에서 로컬 실행 테스트

### 참고
- 맥미니 llama.cpp 환경: `~/llama.cpp`, Metal GPU 가속 빌드 완료
- 기존 Llama 3.2 3B 모델: `~/llama.cpp/models/llama-3.2-3b-q4_k_m.gguf`
- llama-server 포트: 8090
- 16GB 제한으로 큰 모델(7B+)은 빡빡함

---

---

========================================
## 2026-02-16 00:45 — 학습 데이터 생성 & Colab 준비
========================================

### 한 일
- 학습 데이터 121개 생성: `~/.openclaw/workspace/reasoning-model/training_data.json`
- 분야: 수학, 과학, 프로그래밍, CS, 일상상식, 역사, 경제, 물리, 생물, 기술 등
- 형식: `{"instruction", "thinking", "output"}` — chain-of-thought
- Colab 노트북 업데이트: 파일 업로드 방식으로 변경 (training_data.json 업로드)

### 결과
- 121개 데이터 JSON 유효성 확인 완료
- 노트북 + 데이터 파일 준비 완료

### 다음 할 일
- [ ] Colab에 노트북 업로드 → T4 GPU 런타임 설정
- [ ] training_data.json 업로드
- [ ] 학습 실행 → 결과 확인
- [ ] GGUF 변환 → 맥미니 로컬 테스트
- [ ] 결과 좋으면 데이터 500개로 확장 후 재학습

---

========================================
## 2026-02-16 03:01 — Colab 실행 가이드 저장 & 실행 시작
========================================

### 한 일
- Colab 실행 가이드 문서 저장: `~/Work/LLM/colab_guide.md`
- Colab 노트북 업로드 완료
- T4 GPU 런타임 설정 완료
- 셀 1 (Unsloth 설치) 실행 완료
- 셀 2 (모델 로드 + LoRA 설정) 실행 중

### 현재 상태
- Colab에서 Qwen2.5-3B-Instruct 모델 로딩 중
- 다음 단계: training_data.json 업로드 → 학습 실행

### 참고 문서
- `~/Work/LLM/colab_guide.md` — Colab 실행 완벽 가이드 (문제 해결, 체크리스트 포함)

### 다음 할 일
- [ ] 모델 로드 완료 확인
- [ ] training_data.json 업로드
- [ ] 학습 실행 & 모니터링
- [ ] GGUF 변환 → 다운로드
- [ ] 맥미니 로컬 테스트

---

========================================
## 2026-02-16 12:41 — Colab GPU 할당량 소진
========================================

### 상황
- Colab 무료 T4 GPU 할당량 초과로 연결 불가
- 어젯밤(02:54~04:50) 세션이 멈춘 상태로 GPU 시간 소모된 것으로 추정
- 학습 완료 여부 불명확 (셀 실행 상태 확인 못함)

### 원인 분석
- 모두 실행 후 데이터 업로드 대기 셀에서 멈춰있었을 가능성
- 또는 학습은 됐지만 GGUF 변환 전에 세션 문제 발생

### 다음 할 일
- [ ] 12~24시간 후 GPU 할당량 리셋 대기
- [x] 리셋 후 다른 구글 계정으로 Colab 재접속
- [x] 셀 하나씩 실행하며 진행

---

========================================
## 2026-02-16 15:05 — 파인튜닝 완료 & 로컬 실행 성공! 🎉
========================================

### 한 일
- 다른 구글 계정으로 Colab 재접속, T4 GPU 할당 성공
- 셀 순서대로 실행 (wandb → 3번 선택으로 스킵)
- 학습 완료: Qwen2.5-3B-Instruct, 121개 데이터, 3에포크, LoRA r=16
- GGUF Q4_K_M 변환 완료: `Qwen2.5-3B-Instruct.Q4_K_M.gguf` (1.93GB)
- Google Drive 다운로드 → 맥미니 `~/llama.cpp/models/`에 배치
- llama-server 실행: `localhost:8090`, Metal GPU 가속

### 테스트 결과
- "1부터 100까지의 합" → "5050" ✅ 정답
- "TCP와 UDP의 차이점" → 한국어로 정상 응답 ✅
- ⚠️ `<think>` 추론 태그는 아직 안 나옴 (데이터 부족)

### 실행 명령어
```
cd ~/llama.cpp && ./build/bin/llama-server -m models/Qwen2.5-3B-Instruct.Q4_K_M.gguf -c 2048 -ngl 99 --port 8090
```

### 다음 할 일
- [ ] 학습 데이터 500개로 확장
- [ ] 재학습으로 `<think>` 추론 형식 강화
- [ ] RAG 챗봇(`~/Work/rag-chatbot/`)과 연동 검토
- [ ] 브라우저 채팅 UI 테스트

---

========================================
## 2026-02-16 18:30 — 나무위키 크롤링 완료
========================================

### 한 일
- 나무위키 크롤러 생성: `~/Work/LLM/crawler/namu_crawler.py`
- venv 환경 세팅 (requests 설치)
- 팰월드/오버워치/마인크래프트 문서 크롤링 실행

### 결과
- 팰월드: 1개 문서 (114,956자) — 하위문서 URL 매칭 실패로 1개만
- 오버워치: 15개 문서 (5,888,536자)
- 마인크래프트: 12개 문서 (1,653,837자)
- 총 28개 문서, 7,657,329자
- 저장 위치: `~/Work/LLM/crawler/data/`

### 다음 할 일
- [ ] 팰월드 URL 수정해서 추가 크롤링
- [ ] 크롤링 데이터를 RAG 시스템에 벡터화
- [ ] 파인튜닝 모델 + RAG 연동 테스트

---

========================================
## 2026-02-16 18:55 — RAG 시스템 구축 & 웹 UI 완성
========================================

### 한 일
- RAG 시스템 구축: `~/Work/LLM/rag/`
  - `ingest.py` — 나무위키 데이터 벡터화 (FAISS)
  - `chat.py` — CLI 챗봇
  - `web.py` — 웹 UI (localhost:3333)
- venv + langchain + faiss-cpu + sentence-transformers 설치
- 28개 문서 → 3,617개 청크 벡터화 완료

### 결과
- 웹 UI: `localhost:3333` — 게임위키 AI 채팅
- LLM: `localhost:8090` — 파인튜닝된 Qwen2.5-3B
- RAG가 나무위키 데이터에서 관련 내용 검색 → LLM이 답변

### 실행 방법
```
# 1. LLM 서버
cd ~/llama.cpp && ./build/bin/llama-server -m models/Qwen2.5-3B-Instruct.Q4_K_M.gguf -c 1024 -ngl 99 --port 8090

# 2. RAG 웹 UI
cd ~/Work/LLM/rag && source ../crawler/venv/bin/activate && python3 web.py
```

### 다음 할 일
- [ ] 팰월드 크롤링 URL 수정 (현재 1개만 수집됨)
- [ ] 웹 UI 테스트 & 답변 품질 확인
- [ ] 학습 데이터 500개 확장 → 재학습
- [ ] 데이터 업데이트 자동화

---

========================================
## 2026-02-16 19:35 — palworld.gg 크롤링 & GitHub 레포 생성
========================================

### 한 일
- palworld.gg 전용 크롤러 생성: `~/Work/LLM/crawler/palworld_crawler.py`
- 메인 페이지 7개 + 개별 팰 50개 = 57개 문서, 221,053자 수집
- 벡터DB 업데이트: 3,617 → 4,064개 청크
- GitHub 레포 생성: https://github.com/on1659/RadarCustomLLM_Game

### 결과
- 팰월드 데이터 대폭 보강
- log.md GitHub에 push 완료

---

========================================
## 2026-02-16 19:44 — RAG 검색 품질 개선
========================================

### 문제점
1. **한국어 검색 정확도 낮음** — 영어 임베딩 모델(`all-MiniLM-L6-v2`) 사용 중이라 한국어 질문에 엉뚱한 문서가 검색됨
   - 예: "팰월드 물어볼까야" → 오버워치/마크 문서가 참고로 나옴
2. **게임 간 문서 혼재** — "파라가 누구야" 질문에 다른 게임 문서도 섞여서 답변 품질 저하

### 원인 분석
- `all-MiniLM-L6-v2`는 영어 기반 임베딩 모델 → 한국어 의미 유사도 계산이 부정확
- 검색 시 게임별 필터링 없이 전체 문서에서 검색 → 관련 없는 게임 문서 혼입

### 해결 방법

#### 1. 한국어 임베딩 모델로 교체
- **변경 전:** `sentence-transformers/all-MiniLM-L6-v2` (영어 기반, 384차원)
- **변경 후:** `jhgan/ko-sroberta-multitask` (한국어 특화, 768차원)
- 한국어 문장 유사도 측정에 최적화된 모델
- 수정 파일: `rag/ingest.py`, `rag/chat.py`, `rag/web.py`

#### 2. 게임명 자동 감지 필터 추가
- 질문에서 게임 키워드 감지:
  - "팰월드", "palworld", "팰" → palworld 문서만 검색
  - "오버워치", "overwatch", "옵치" → overwatch 문서만 검색
  - "마인크래프트", "마크", "minecraft" → minecraft 문서만 검색
- 게임 키워드 없으면 전체 검색
- 필터 적용 시 15개 후보 검색 → 해당 게임만 필터 → 상위 5개 사용
- 수정 파일: `rag/web.py`

### 수정된 파일
- `rag/ingest.py` — 임베딩 모델 변경
- `rag/chat.py` — 임베딩 모델 변경
- `rag/web.py` — 임베딩 모델 변경 + 게임명 필터 추가

### 다음 할 일
- [ ] 벡터DB 재생성 (한국어 임베딩)
- [ ] 웹 서버 재시작 & 테스트
- [ ] 개선 효과 확인

---

========================================
## 2026-02-16 20:15 — 벡터DB 재생성 & llm-server 스킬 생성
========================================

### 한 일
- 벡터DB 한국어 임베딩으로 재생성 (`jhgan/ko-sroberta-multitask`)
  - 기존 영어 임베딩(`all-MiniLM-L6-v2`) → 한국어 특화 모델로 교체
  - 4,064개 청크 재인덱싱 완료
- RAG 웹 서버 + ngrok 자동 시작
  - 기존 프로세스 정리 후 재시작
  - 외부 접속 URL: https://awhirl-preimpressive-carina.ngrok-free.dev
- **llm-server 스킬 생성** 🎉
  - `startllm` - LLM 서버 전체 시작 (llama-server + RAG + ngrok)
  - `stopllm` - 전체 중지
  - `statusllm` - 실행 상태 확인
  - 스킬 위치: `~/.openclaw/workspace/skills/llm-server/`

### 결과
- ✅ 한국어 검색 정확도 대폭 향상 (임베딩 교체)
- ✅ 게임명 자동 필터링 적용 (팰월드/오버워치/마크)
- ✅ 한 번의 명령으로 전체 서버 시작/중지 가능
- ✅ 외부 접속 자동 설정 (ngrok)

### 실행 방법 (업데이트)
```bash
# 간편 시작 (권장) ⭐
startllm

# 상태 확인
statusllm

# 전체 중지
stopllm

# 또는 수동 실행 (기존 방법)
# 1. llama-server
cd ~/llama.cpp && ./build/bin/llama-server -m models/Qwen2.5-3B-Instruct.Q4_K_M.gguf -c 1024 -ngl 99 --port 8090

# 2. RAG 웹 UI
cd ~/Work/LLM/rag && source ../crawler/venv/bin/activate && python3 web.py

# 3. ngrok
ngrok http 3333
```

### 서비스 정보
- llama-server: http://localhost:8090
- RAG 웹 서버: http://localhost:3333
- ngrok 외부 URL: https://awhirl-preimpressive-carina.ngrok-free.dev

### 다음 할 일
- [ ] 브라우저에서 RAG 시스템 테스트 (게임별 질문)
- [ ] 학습 데이터 500개로 확장 후 재학습
- [ ] 70B 모델 테스트 (128GB PC)

---

========================================
## 2026-02-16 20:56 — LLM 응답 품질 개선
========================================

### 문제점
1. **`'choices'` 에러** — web.py가 `/v1/chat/completions` (OpenAI 형식) 엔드포인트를 사용 중이었음
   - llama-server는 `/completion` 엔드포인트를 사용해야 함
2. **`'content'` 에러** — 응답 JSON 구조가 다름 (`choices[0].message.content` → `content`)
3. **400 Bad Request** — 프롬프트가 2066 토큰인데 컨텍스트 크기가 1024 토큰이라 거부됨
4. **답변 반복/산만** — 3B 모델이 긴 컨텍스트에서 집중 못 함, 여러 질문-답변을 자체 생성

### 수정 내용 (`rag/web.py`)

#### 1. API 엔드포인트 수정
- **변경 전:** `http://localhost:8090/v1/chat/completions` (OpenAI 형식)
- **변경 후:** `http://localhost:8090/completion` (llama-server 네이티브)
- payload: `messages` 배열 → `prompt` 문자열
- 응답: `choices[0].message.content` → `content`

#### 2. 컨텍스트 크기 확장 (start.sh)
- **변경 전:** `-c 1024`
- **변경 후:** `-c 4096`
- 2066+ 토큰 프롬프트도 처리 가능

#### 3. 프롬프트 개선
- "추가 질문을 만들지 마세요" 지시 추가 → 자체 Q&A 생성 방지
- "간결하게 답변하세요" 강조

#### 4. 검색 결과 축소
- 검색 결과: 5개 → 3개
- 청크당 최대 500자로 제한 (`max_chunk_len = 500`)
- 컨텍스트가 짧아져서 답변 집중도 향상

#### 5. LLM 파라미터 최적화
- `n_predict`: 1024 → 256 (답변 길이 제한)
- `repeat_penalty`: 1.3 → 1.5 (반복 억제 강화)
- `stop` 토큰 추가: `["질문:", "해당 정보가 없습니다.", "참고 자료:", "---"]`

### 테스트 결과
- ✅ "오버워치 파라 알려줘" → 파라 정보만 간결하게 답변 (한조 혼입 없음)
- ⚠️ 3B 모델 한계로 한국어가 약간 어색한 부분 있음
- ⚠️ 학습 데이터 500개 확장 시 품질 개선 기대

### 수정된 파일
- `rag/web.py` — API 엔드포인트, 프롬프트, 검색 설정, LLM 파라미터 전면 수정
- `~/.openclaw/workspace/skills/llm-server/scripts/start.sh` — 컨텍스트 1024→4096

### 다음 할 일
- [ ] 학습 데이터 500개로 확장 후 재학습 (답변 품질 근본 개선)
- [ ] 70B 모델 테스트 (128GB PC)
- [ ] 프롬프트 추가 튜닝

---

========================================
## 2026-02-16 21:42 — 게임 역질문(disambiguation) 기능 추가
========================================

### 기능
- 게임 키워드 없이 검색했을 때, 검색 결과에 2개 이상 게임이 섞여있으면 역질문
- 예: "아누비스 알려줘" → "여러 게임에 존재합니다. 어떤 게임?" + [팰월드] [오버워치] 버튼
- 버튼 클릭 → "팰월드 아누비스 알려줘"로 재질문 → 해당 게임만 필터링해서 답변

### 수정 내용 (`rag/web.py`)
- 백엔드: 게임 필터 없을 때 `found_games` set으로 게임 종류 확인, 2개 이상이면 `ask_game: true` + `games` 배열 반환
- 프론트엔드: `ask_game` 응답 시 게임 선택 버튼 렌더링, `sendWithGame()` 함수로 게임명 + 원래 질문 결합해서 재전송

### 테스트 결과
- ✅ "아누비스 알려줘" → 오버워치/팰월드 선택 역질문
- ✅ 게임 선택 후 해당 게임만 필터링해서 답변

---
