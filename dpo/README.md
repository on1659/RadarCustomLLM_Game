# DPO (Direct Preference Optimization) 학습 파이프라인

Qwen2.5-7B 모델을 게임 위키 RAG에 특화되도록 fine-tuning하는 시스템.

## 📋 개요

**목표:** QA 테스트에서 틀린 답변(rejected)을 올바른 답변(chosen)으로 학습시켜 정확도 향상.

**방법:** DPO (사람의 선호도 학습) + LoRA (효율적 fine-tuning)

**필요 데이터:** 500쌍 권장 (최소 50쌍)

## 🛠️ 설치

### 1. 필수 라이브러리

```bash
cd ~/Work/LLM
pip install unsloth trl datasets peft bitsandbytes accelerate transformers torch
```

### 2. llama.cpp (GGUF 변환용)

```bash
cd ~/Work/LLM
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
```

## 🚀 워크플로우

### 1️⃣ 데이터 수집 (자동)

```bash
python dpo/collect-data.py
```

**동작:**
- 최근 7일간 QA 로그에서 정확도 70% 이하 답변 수집
- `dataset/rejected.jsonl` 생성
- `dataset/pending.json` 큐 생성 (수동 수정 대기)

**출력 예시:**
```
📖 2026-02-22.md 파싱 중...
✅ 12개 새 rejected 답변 수집 (총 45개)
📋 수동 수정 대기 중: 45개

📊 DPO 데이터셋 현황:
  - Rejected: 45개
  - Chosen: 0개
  - Pending (수정 대기): 45개
  - 학습 가능 페어: 0개

🎯 권장 학습량: 500쌍 (현재 진행률: 0.0%)
```

---

### 2️⃣ 수동 답변 작성 (인간 피드백)

```bash
python dpo/manual-fix.py
```

**대화형 모드:**
```
[1/45]

❓ 질문: 마인크래프트 엔더드래곤
❌ 기존 답변 (정확도 45%):
엔더드래곤은 마인크래프트의 몬스터입니다...

옵션:
  1. 올바른 답변 작성
  2. 건너뛰기 (skip)
  3. 삭제 (이 질문 제외)
  q. 종료

선택: 1

✏️  올바른 답변을 입력하세요 (여러 줄 입력 가능, 빈 줄 + Enter로 완료):
엔더드래곤은 마인크래프트의 최종 보스 몬스터입니다.
엔드 차원에서 만날 수 있으며, 엔드 크리스탈을 파괴하면서 공략해야 합니다.
처치하면 대량의 경험치와 드래곤 알을 얻을 수 있습니다.
[빈 줄]

✅ 저장 완료!
```

**배치 가져오기:**
- JSON 파일로 대량 import 가능
- 형식: `[{"question": "...", "rejected": "...", "chosen": "..."}]`

---

### 3️⃣ DPO 학습

```bash
python dpo/train.py
```

**요구사항:**
- 최소 10개 페어 (권장 50+)
- GPU/MPS 권장 (CPU도 가능하나 느림)
- M4 16GB: LoRA 4bit로 학습 가능

**학습 과정:**
```
🚀 DPO 학습 시작

📚 데이터셋 로드: 50개 페어
✅ 데이터셋 준비 완료: 50개

📦 라이브러리 로드 중...
🔧 모델 로드: Qwen/Qwen2.5-7B-Instruct
🎯 LoRA 어댑터 설정

⚙️  학습 설정
🔥 학습 시작!
  - 데이터: 50개
  - 에폭: 3
  - 배치 크기: 1
  - 예상 시간: ~15 분

[에폭 1/3] Step 10/150 | Loss: 0.523
[에폭 2/3] Step 60/150 | Loss: 0.412
[에폭 3/3] Step 150/150 | Loss: 0.387

💾 모델 저장 중...
✅ 학습 완료!

저장 위치: ~/Work/LLM/dpo/models/lora_adapter
```

**학습 파라미터:**
- **LoRA rank:** 16
- **Learning rate:** 5e-5
- **Beta (DPO):** 0.1
- **Batch size:** 1 (gradient accumulation 4)
- **Epochs:** 3

---

### 4️⃣ GGUF 변환 및 배포

```bash
python dpo/convert-to-gguf.py
```

**과정:**
1. LoRA 어댑터를 기본 모델에 병합
2. HuggingFace → FP16 GGUF
3. FP16 → Q4_K_M 양자화
4. `~/Work/LLM/models/` 에 배포

**출력 예시:**
```
🔄 LoRA → GGUF 변환 파이프라인

🔄 LoRA 어댑터 병합 중...
✅ 병합 완료: ~/Work/LLM/dpo/models/merged_model

🔧 GGUF 변환 중...
실행: python convert_hf_to_gguf.py ...
✅ FP16 GGUF 생성: model-f16.gguf

🔧 양자화 중 (Q4_K_M)...
실행: llama-quantize model-f16.gguf model-Q4_K_M.gguf Q4_K_M
✅ 양자화 완료: model-Q4_K_M.gguf

🚀 서버 배포
✅ 배포 완료: ~/Work/LLM/models/Qwen2.5-7B-DPO-Q4_K_M.gguf
```

---

### 5️⃣ 서버 재시작

```bash
# 자동 재시작 (권장)
llmcron restart

# 수동 재시작
pkill llama-server
cd ~/Work/LLM
nohup ./build/bin/llama-server \
  -m models/Qwen2.5-7B-DPO-Q4_K_M.gguf \
  -c 8192 --port 8090 > llama-server.log 2>&1 &
```

---

## 📂 디렉토리 구조

```
dpo/
├── README.md              # 이 파일
├── collect-data.py        # 1️⃣ 데이터 수집
├── manual-fix.py          # 2️⃣ 수동 답변 작성
├── train.py               # 3️⃣ DPO 학습
├── convert-to-gguf.py     # 4️⃣ GGUF 변환
├── dataset/
│   ├── rejected.jsonl     # 틀린 답변 모음
│   ├── chosen.jsonl       # 학습 페어 (Q + rejected + chosen)
│   └── pending.json       # 수동 작업 큐
└── models/
    ├── lora_adapter/      # 학습된 LoRA 어댑터
    ├── merged_model/      # 병합된 HF 모델
    ├── model-f16.gguf     # FP16 GGUF
    └── model-Q4_K_M.gguf  # 양자화 GGUF
```

## 🎯 데이터 수집 전략

### 자동 수집 (일일)

```bash
# cron으로 매일 실행
0 3 * * * cd ~/Work/LLM && python dpo/collect-data.py >> dpo/collect.log 2>&1
```

### 수동 작업 루틴

**매주 1회 (30분):**
1. `python dpo/manual-fix.py`
2. 대화형 모드로 10~20개 수정
3. 주말에 집중 작업 (50~100개)

**목표:**
- 1주차: 50개
- 2주차: 150개
- 3주차: 300개
- 4주차: 500개 → 첫 학습

### 크라우드소싱 (선택)

- 게임 커뮤니티에 요청
- JSON 템플릿 배포
- `manual-fix.py` 배치 가져오기로 병합

## 📊 품질 관리

### 학습 전 체크리스트

- [ ] 최소 50개 페어 확보
- [ ] chosen 답변 품질 검수
- [ ] 중복 질문 제거
- [ ] 게임별 균형 (마크/팰/오버 각 30%+)

### 학습 후 검증

```bash
# 새 모델로 QA 테스트
llmcron restart
sleep 30
python qa-test.py

# 로그 확인
tail -100 log/$(date +%Y-%m-%d).md
```

**기대 효과:**
- 정확도 10~20% 향상
- 특정 실패 케이스 개선
- 답변 일관성 증가

## 🔧 트러블슈팅

### 1. CUDA/MPS 없음

```
⚠️  경고: GPU/MPS를 찾을 수 없습니다.
```

**해결:**
- M1/M2/M3/M4 Mac: `pip install torch torchvision`
- NVIDIA GPU: CUDA 11.8+ 설치
- CPU 학습: 느리지만 가능 (1~2시간)

### 2. 메모리 부족

```
torch.cuda.OutOfMemoryError: ...
```

**해결:**
- `train.py` 에서 `load_in_4bit=True` 확인
- `per_device_train_batch_size=1` 유지
- `gradient_accumulation_steps` 증가 (4→8)

### 3. llama.cpp 오류

```
❌ 변환 스크립트를 찾을 수 없습니다
```

**해결:**
```bash
cd ~/Work/LLM
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make
pip install -r requirements.txt
```

## 🚀 고급 옵션

### A/B 테스트

```bash
# 기존 모델
llama-server -m models/Qwen2.5-7B-Instruct-Q4_K_M.gguf --port 8090

# DPO 모델
llama-server -m models/Qwen2.5-7B-DPO-Q4_K_M.gguf --port 8091

# 비교 테스트
python qa-test.py --port 8090 > baseline.log
python qa-test.py --port 8091 > dpo.log
diff baseline.log dpo.log
```

### 반복 학습

```bash
# 1차 학습 (50개)
python dpo/train.py

# 배포 + 테스트
python dpo/convert-to-gguf.py
llmcron restart
python qa-test.py

# 추가 데이터 수집 (100개)
python dpo/collect-data.py
python dpo/manual-fix.py

# 2차 학습 (150개)
python dpo/train.py
```

### 모델 버전 관리

```bash
# 날짜별 백업
cp models/model-Q4_K_M.gguf \
   models/model-Q4_K_M-$(date +%Y%m%d).gguf

# 성능 비교 로그
echo "$(date) | v1.0 | 정확도 72% | 데이터 150개" >> models/changelog.txt
```

## 📈 로드맵

- [x] 데이터 수집 자동화
- [x] 수동 수정 도구
- [x] DPO 학습 파이프라인
- [x] GGUF 변환 자동화
- [ ] 웹 UI (수동 작업용)
- [ ] 자동 QA 비교 (before/after)
- [ ] 멀티 모델 앙상블
- [ ] 커뮤니티 데이터 크라우드소싱

## 📚 참고자료

- [Unsloth DPO 가이드](https://github.com/unslothai/unsloth)
- [TRL DPO Trainer](https://huggingface.co/docs/trl/dpo_trainer)
- [Qwen2.5 모델](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)
- [llama.cpp](https://github.com/ggerganov/llama.cpp)

---

**문의:** 이더 (@YTRadar)
