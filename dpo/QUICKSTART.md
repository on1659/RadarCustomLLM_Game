# DPO 학습 빠른 시작 가이드 ⚡

**목표:** 10분 안에 첫 데이터 수집 + 학습 파이프라인 이해

## 0️⃣ 설치 (1회만)

```bash
cd ~/Work/LLM/dpo
chmod +x install.sh
./install.sh
```

예상 시간: 5~10분

---

## 1️⃣ 데이터 수집 (30초)

```bash
cd ~/Work/LLM
python3 dpo/collect-data.py
```

**결과:**
```
✅ 54개 새 rejected 답변 수집
📋 수동 수정 대기 중: 54개
🎯 권장 학습량: 500쌍 (현재 진행률: 0.0%)
```

**무슨 일이 일어났나?**
- 최근 7일 QA 로그에서 정확도 70% 이하 답변 추출
- `dpo/dataset/rejected.jsonl` 생성
- `dpo/dataset/pending.json` 수정 큐 생성

---

## 2️⃣ 수동 답변 작성 (시간 가변)

```bash
python3 dpo/manual-fix.py
```

**대화형 UI:**
```
[1/54]
❓ 질문: 마인크래프트 엔더드래곤
❌ 기존 답변 (정확도 40%):
엔더드래곤은 공격적인 몹으로, 체력 100을...

옵션:
  1. 올바른 답변 작성
  2. 건너뛰기 (skip)
  3. 삭제
  q. 종료

선택: 1

✏️  올바른 답변 입력 (빈 줄 + Enter로 완료):
엔더드래곤은 마인크래프트의 최종 보스입니다.
엔드 차원에서 엔드 크리스탈을 파괴하며 공략합니다.
처치 시 대량의 경험치와 드래곤 알을 획득합니다.
[빈 줄]

✅ 저장 완료!
```

**팁:**
- 처음엔 10개만 해보기 (테스트용)
- 주말에 몰아서 50개+ 작성
- JSON 파일로 배치 import 가능

---

## 3️⃣ 학습 (최소 10개 페어 필요)

```bash
python3 dpo/train.py
```

**요구사항:**
- 최소 10개 페어 (권장 50+)
- M4 16GB: 4bit LoRA로 학습 가능
- 예상 시간: 데이터 50개 기준 ~15분

**과정:**
```
🚀 DPO 학습 시작
📚 데이터셋 로드: 50개 페어
🔧 모델 로드: Qwen/Qwen2.5-7B-Instruct
🎯 LoRA 어댑터 설정 (rank=16)
🔥 학습 시작!

[에폭 1/3] Loss: 0.523
[에폭 2/3] Loss: 0.412
[에폭 3/3] Loss: 0.387

✅ 학습 완료!
```

---

## 4️⃣ GGUF 변환

```bash
python3 dpo/convert-to-gguf.py
```

**과정:**
1. LoRA 어댑터 병합
2. HuggingFace → GGUF 변환
3. Q4_K_M 양자화
4. `~/Work/LLM/models/` 배포

---

## 5️⃣ 서버 재시작

```bash
llmcron restart
```

또는 수동:
```bash
pkill llama-server
cd ~/Work/LLM
nohup ./build/bin/llama-server \
  -m models/Qwen2.5-7B-DPO-Q4_K_M.gguf \
  -c 8192 --port 8090 > llama-server.log 2>&1 &
```

---

## 6️⃣ 검증

```bash
python3 qa-test.py
tail -50 log/$(date +%Y-%m-%d).md
```

**기대 효과:**
- 정확도 10~20% 향상
- 특정 실패 케이스 개선

---

## 📅 일일 루틴

### 매일 (자동)
- QA 테스트 실행 (20분마다 cron)
- 데이터 자동 수집 (새벽 3시 cron)

### 주 1회 (수동, 30분)
1. `python3 dpo/collect-data.py` - 신규 데이터 확인
2. `python3 dpo/manual-fix.py` - 10~20개 수정
3. 데이터 50개 모이면 → 학습

### 월 1회 (학습)
- 500개 모이면 대규모 학습
- before/after 비교
- 모델 버전 관리

---

## 🎯 마일스톤

- [ ] 1주차: 설치 완료 + 첫 10개 수정
- [ ] 2주차: 50개 수집 → 첫 학습
- [ ] 3주차: 150개 → 2차 학습
- [ ] 4주차: 500개 → 프로덕션 배포

---

## ⚡ 치트시트

```bash
# 전체 파이프라인 (한 번에)
cd ~/Work/LLM
python3 dpo/collect-data.py              # 데이터 수집
python3 dpo/manual-fix.py                # 수동 작업
python3 dpo/train.py                     # 학습
python3 dpo/convert-to-gguf.py           # 변환
llmcron restart                          # 배포

# 현황 확인
python3 dpo/collect-data.py | tail -10   # 데이터 통계
ls -lh dpo/dataset/                      # 파일 확인
tail -100 log/$(date +%Y-%m-%d).md       # 최근 QA 결과

# 학습 모니터링
tail -f dpo/models/checkpoints/trainer_state.json
watch -n 5 nvidia-smi                    # GPU 사용량 (NVIDIA)
```

---

## 🆘 문제 해결

### Q: 데이터가 0개 수집됨
**A:** QA 테스트가 아직 안 돌았거나 모두 70% 이상. 기다리거나 임계값 상향.

### Q: 메모리 부족 (OOM)
**A:** `train.py`에서 `load_in_4bit=True` 확인. batch_size=1 유지.

### Q: llama.cpp 없음
**A:** `cd ~/Work/LLM && git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make`

### Q: 학습 너무 느림
**A:** GPU/MPS 사용 확인. CPU는 1~2시간 소요.

---

**더 알아보기:** `dpo/README.md`
