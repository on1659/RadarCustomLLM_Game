# 🎮 게임위키 AI RAG 서버

로컬 LLM 기반 게임 정보 검색 서버 — 나무위키 데이터 + 하이브리드 RAG + 자동 QA

## 📋 프로젝트 개요

마인크래프트, 오버워치, 팰월드 게임 정보를 자연어로 질문하면 **로컬 LLM**이 나무위키 크롤링 데이터를 검색해서 답변하는 RAG(Retrieval-Augmented Generation) 서버입니다.

**특징:**
- 🤖 **로컬 LLM**: Qwen2.5-3B-Instruct (llama-server)
- 🔍 **하이브리드 검색**: Vector DB (FAISS) + BM25
- 🧠 **대화 기억**: 세션별 맥락 유지
- ✍️ **오타 보정**: "힌조" → "한조" 자동 감지 + 재검색
- 🚀 **자동 QA**: 20분마다 정확도 테스트 + 1시간마다 자동 개선
- 🔐 **API 보안**: 선택적 API 키 인증

## 🏗️ 시스템 구성

```
┌─────────────────────────────────────┐
│  외부 클라이언트 (챗봇, 웹앱 등)    │
└────────────┬────────────────────────┘
             │ HTTPS (ngrok)
             ▼
┌─────────────────────────────────────┐
│  RAG Web Server (Flask, port 3334) │
│  - API 엔드포인트 (/api/chat)       │
│  - 세션 관리 (대화 기록)            │
│  - 오타 보정 (typo_fix.py)         │
└────────┬────────────┬───────────────┘
         │            │
         │            ▼
         │   ┌──────────────────────┐
         │   │  Vector DB (FAISS)   │
         │   │  + BM25 Index        │
         │   │  4,179 chunks        │
         │   └──────────────────────┘
         ▼
┌─────────────────────────────────────┐
│  LLM Server (llama-server, port 8090)│
│  Model: Qwen2.5-3B-Instruct         │
└─────────────────────────────────────┘
```

## 📂 디렉토리 구조

```
~/Work/LLM/
├── README.md                # 👈 현재 문서 (프로젝트 설명)
├── API_GUIDE.md             # 👈 API 사용 가이드 (챗봇 통합)
├── QA_OPERATIONS.md         # QA 시스템 운영 가이드
├── LLMCRON.md               # llmcron CLI 사용법
│
├── rag/                     # RAG 서버 (Flask)
│   ├── web.py               # API 서버 메인
│   ├── typo_fix.py          # 오타 보정 모듈
│   ├── faiss_db/            # Vector DB 저장소
│   ├── bm25_index.pkl       # BM25 인덱스
│   └── venv/                # Python 가상환경
│
├── crawler/                 # 나무위키 크롤러
│   ├── namu_crawler.py      # 나무위키 크롤링
│   ├── palworld_crawler.py  # 팰월드 전용
│   └── data/                # 크롤링된 텍스트 (*.txt)
│
├── qa-test.py               # 20분마다 정확도 테스트
├── auto-improve.py          # 1시간마다 자동 개선
├── healthcheck.py           # 5분마다 서버 헬스 체크
├── llmcron                  # 크론 관리 CLI
│
└── log/                     # 📝 QA/개선 작업 히스토리
    ├── YYYY-MM-DD.md        # 날짜별 로그 (QA 테스트, 헬스 체크)
    └── improvement-log.md   # 자동 개선 제안 기록
```

## 🚀 빠른 시작

### 1. 서버 실행

```bash
# LLM 서버 시작 (llama-server)
llama-server --model ~/Work/LLM/models/qwen2.5-3b-instruct.gguf --port 8090 &

# RAG 웹 서버 시작
cd ~/Work/LLM/rag
source venv/bin/activate
python web.py &

# ngrok 터널 (외부 접근용)
ngrok http 3334 &
```

또는 통합 명령어:
```bash
llmcron start
```

### 2. API 호출

```bash
curl -X POST "https://your-ngrok-url.ngrok-free.dev/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "query": "마인크래프트 다이아몬드 어디서 구해?",
    "session_id": "user_123"
  }'
```

**응답:**
```json
{
  "answer": "다이아몬드는 보루 잔해의 상자에서 종종 나온다...",
  "sources": ["minecraft/마인크래프트_아이템"],
  "session_id": "user_123"
}
```

## 📚 API 사용 가이드

**챗봇에 통합하고 싶다면?**

👉 **[API_GUIDE.md](./API_GUIDE.md)** 참고

- ✅ 빠른 시작 (3분)
- ✅ 실전 예제 (카카오톡, 디스코드, 텔레그램, 웹)
- ✅ session_id 관리 (그룹 채팅 대응)
- ✅ 보안 설정 (API 키 인증)
- ✅ 에러 처리 및 최적화

## 🤖 자동 QA 시스템

**헬스 체크** (5분마다):
- 서버 다운 시 자동 재시작
- 크론 ID: `82590edd-a405-426c-bb63-5463670c1e7a`

**QA 테스트** (20분마다):
- 랜덤 4개 질문 테스트
- 정확도 측정 (키워드 기반)
- 크론 ID: `8935609d-a8e9-49e0-a9e1-196730ea8771`

**자동 개선** (1시간마다):
- 정확도 ≤80% 감지 → 개선안 제시
- 크론 ID: `04b96b52-b13f-4438-8900-6352ba70b8e1`

**관리 CLI:**
```bash
llmcron status   # 모든 크론 상태 확인
llmcron start 20 # QA 간격 20분으로 시작
llmcron stop     # 모든 크론 중지
```

자세한 내용: [QA_OPERATIONS.md](./QA_OPERATIONS.md)

**⚠️ 작업 시 필수**: 프롬프트 수정, 데이터 추가, 알고리즘 튜닝 등 모든 작업을 `log/YYYY-MM-DD.md`에 **개선 사이클 4단계** (문제 발견 → 개선 작업 → 재테스트 → 결론)로 기록! ([가이드](./QA_OPERATIONS.md#-개선-사이클-기록-방법) | [템플릿](./log/IMPROVEMENT_TEMPLATE.md))

## 📊 데이터

- **출처**: 나무위키 (Namu Wiki)
- **게임**: 마인크래프트, 오버워치, 팰월드
- **문서**: 57개 (총 792만자)
- **청크**: 4,179개 (Vector DB)
- **모델**: Qwen2.5-3B-Instruct (3.09GB)

## 🔧 기술 스택

| 구성 요소 | 기술 |
|----------|------|
| **LLM** | Qwen2.5-3B-Instruct (llama.cpp) |
| **Vector DB** | FAISS (HuggingFace Embeddings) |
| **BM25** | rank-bm25 (한국어 형태소 분석) |
| **웹 서버** | Python Flask (HTTP server) |
| **크롤러** | BeautifulSoup4 + Selenium |
| **외부 접근** | ngrok (HTTPS 터널) |
| **스케줄링** | OpenClaw 크론 |

## 🎯 주요 기능

### 1️⃣ 하이브리드 검색 (RRF)
- **Vector 검색** (의미 기반) + **BM25** (키워드 기반)
- Reciprocal Rank Fusion으로 결과 병합
- 의도별 가중치 조절 (stat/howto/list/compare/general)

### 2️⃣ 오타 자동 보정 + 재검색
```
사용자: "오버워치 칸조"
시스템: [오타 감지] "칸조" → "한조" (유사도 50%)
       [재검색] "오버워치 한조"
응답: "🔍 혹시 '오버워치 한조'를 찾으시나요?
      한조는 시마다 일족의..."
```

### 3️⃣ 대화 맥락 유지
```python
# 1번째 질문
{"query": "마인크래프트 다이아몬드", "session_id": "user_123"}
# → "보루 상자에서..."

# 2번째 질문 (같은 session_id)
{"query": "어떻게 구해?", "session_id": "user_123"}
# → "다이아몬드는 Y좌표 -64~16에서..." (맥락 기억!)
```

### 4️⃣ 게임 자동 감지
```
질문: "다이아몬드"
시스템: [여러 게임 감지] minecraft, palworld
응답: "여러 게임에 존재합니다. 어떤 게임?"
```

## 🛠️ 설치 및 설정

### 필수 요구사항

- Python 3.9+
- llama.cpp (llama-server)
- ngrok (외부 접근용)
- OpenClaw (크론 관리)

### 설치

```bash
# 1. Python 가상환경
cd ~/Work/LLM/rag
python3 -m venv venv
source venv/bin/activate

# 2. 패키지 설치
pip install flask langchain faiss-cpu rank-bm25 beautifulsoup4 selenium

# 3. llama-server 설치
brew install llama.cpp  # macOS
# 또는 GitHub에서 빌드

# 4. ngrok 설치
brew install ngrok  # macOS
```

### 환경 변수 (선택)

```bash
# ~/.zshrc 또는 ~/.bashrc
export GAME_WIKI_API_KEY="$(openssl rand -hex 32)"
```

## 📈 성능

- **응답 시간**: 평균 2-5초
- **정확도**: 약 70-80% (키워드 기반)
- **동시 요청**: 최대 10개 (FIFO 큐)
- **세션 유지**: 마지막 대화 후 30분

## 🤝 기여

이슈, PR 환영합니다!

- **버그 리포트**: GitHub Issues
- **기능 제안**: GitHub Discussions
- **문의**: GitHub Issues 또는 이메일

## 📜 라이선스

개인 프로젝트 — 상업적 이용 시 문의 필요

## 🔗 관련 링크

- **API 가이드**: [API_GUIDE.md](./API_GUIDE.md)
- **QA 운영**: [QA_OPERATIONS.md](./QA_OPERATIONS.md)
- **크론 관리**: [LLMCRON.md](./LLMCRON.md)
- **GitHub**: https://github.com/on1659/RadarCustomLLM_Game

---

**Made with ❤️ by 이더 (KimYoungtae)**
