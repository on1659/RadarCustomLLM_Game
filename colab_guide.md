# 🚀 Google Colab 노트북 실행 완벽 가이드

LLM 파인튜닝을 위한 단계별 실습 가이드입니다.

---

## 📋 목차

1. [준비물](#준비물)
2. [Colab 접속](#1단계-colab-접속)
3. [노트북 업로드](#2단계-노트북-업로드)
4. [GPU 설정](#3단계-gpu-설정-중요)
5. [코드 실행](#4단계-코드-실행)
6. [데이터 업로드](#5단계-데이터-업로드)
7. [학습 모니터링](#6단계-학습-모니터링)
8. [결과 다운로드](#7단계-결과-다운로드)
9. [문제 해결](#문제-해결)
10. [체크리스트](#체크리스트)

---

## 준비물

### 📁 필수 파일

- `colab_notebook.ipynb` - Colab 노트북 파일
- `training_data.json` - 학습 데이터 (121개 샘플)

### ✅ 필수 조건

- 구글 계정 (Gmail)
- 인터넷 연결
- 웹 브라우저 (Chrome 권장)

---

## 1단계: Colab 접속

### 브라우저에서 접속

**URL:** https://colab.research.google.com/

### 로그인

1. 구글 계정으로 로그인
2. Colab 시작 페이지 확인

```
┌─────────────────────────────────────┐
│  🔶🔶 Google Colab                  │
│                                     │
│  Colab 시작 페이지                   │
│  - VS Code에서 Google Colab 사용     │
│  - 미국 대학생은 Gemini...           │
│  - API 키 없이...                   │
└─────────────────────────────────────┘
```

---

## 2단계: 노트북 업로드

### 방법 1: 파일 메뉴 사용 (추천)

1. 상단 메뉴바 **"파일"** 클릭
2. **"노트북 업로드"** 선택
3. `colab_notebook.ipynb` 파일 선택
4. 업로드 완료 대기

```
파일 ▼
├─ 새 노트북
├─ 노트북 열기...
├─ ► 노트북 업로드 ◀◀◀ 여기 클릭!
├─ GitHub에서 노트북 열기
├─ Drive에서 노트북 열기
└─ ...
```

### 방법 2: 드래그 앤 드롭

1. 파일 탐색기에서 `colab_notebook.ipynb` 찾기
2. 파일을 Colab 브라우저 창으로 드래그
3. 마우스 버튼 놓기 (Drop)
4. 자동으로 노트북 열림

### 업로드 성공 확인

```
┌──────────────────────────────────────────┐
│ colab_notebook.ipynb          [연결 ▼]   │
├──────────────────────────────────────────┤
│                                          │
│ [ ] # 1단계: 환경 설정                    │
│     !pip install unsloth                 │
│     ▶                                    │
├──────────────────────────────────────────┤
│ [ ] # 2단계: 라이브러리 import             │
│     import torch                         │
│     ▶                                    │
└──────────────────────────────────────────┘
```

---

## 3단계: GPU 설정 ⭐ 중요!

### 왜 GPU가 필요한가?

```
CPU 모드:  학습 시간: 8-12시간 😰
GPU 모드:  학습 시간: 1-2시간 🚀
차이: 4-6배!
```

### GPU 설정 방법

#### 1️⃣ 런타임 메뉴 클릭

```
파일  수정  보기  삽입  [런타임]  도구  도움말
                      ↑
                   여기 클릭!
```

#### 2️⃣ 런타임 유형 변경 선택

```
런타임 ▼
├─ 모두 실행
├─ 런타임 다시 시작
├─ ► 런타임 유형 변경 ◀◀◀ 여기!
├─ 실행 중단
└─ ...
```

#### 3️⃣ GPU 선택

```
┌─────────────────────────────────┐
│  노트북 설정                     │
├─────────────────────────────────┤
│                                 │
│  하드웨어 가속기:                │
│  ┌─────────────────┐            │
│  │ None      ▼     │ ← 기본값   │
│  └─────────────────┘            │
│                                 │
│  이것을 변경:                    │
│  ┌─────────────────┐            │
│  │ T4 GPU    ▼     │ ← 선택!    │
│  └─────────────────┘            │
│                                 │
│         [취소]  [저장]          │
└─────────────────────────────────┘
```

**옵션 설명:**
- `None`: CPU만 사용 (느림)
- `T4 GPU`: 무료 GPU (권장!) ⭐
- `TPU`: 특수 목적용 (사용 안 함)

#### 4️⃣ 저장 버튼 클릭

### GPU 활성화 확인

```
⚡ 연결됨  RAM 디스크 GPU
          ↑        ↑
      메모리 사용량  GPU 활성화!
```

GPU 아이콘이 보이면 성공!

---

## 4단계: 코드 실행

### 셀(Cell) 이해하기

노트북은 여러 개의 "셀"로 구성됩니다:

```python
[ ] 코드 셀
    print("Hello World")
    ▶ ← 실행 버튼

출력:
Hello World
```

### 실행 방법

#### 방법 1: 마우스 클릭

1. 셀 왼쪽 **▶** 버튼 클릭
2. 실행 완료될 때까지 대기
3. 체크 표시 **✓** 확인
4. 다음 셀로 이동

#### 방법 2: 키보드 단축키

- **Shift + Enter**: 현재 셀 실행 + 자동으로 다음 셀로 이동
- **Ctrl + Enter**: 현재 셀만 실행 (이동 안 함)

### ⚠️ 실행 순서 (중요!)

**반드시 위에서 아래로 순서대로!**

```
셀 1 → 셀 2 → 셀 3 → ...

중간 건너뛰면 에러 발생!
```

### 첫 번째 셀 실행 예시

```python
# 1단계: Unsloth 설치
!pip install unsloth -q
print("✅ 설치 완료!")
```

**실행 과정:**

```
[ ] ▶ 클릭
    ↓
[*] 실행 중... (회전 아이콘)
    ↓
    진행 상황 표시:
    Installing unsloth...
    ████████████ 100%
    ↓
[✓] 완료!
    
출력:
✅ 설치 완료!
```

### 소요 시간

- 첫 셀 (패키지 설치): **2-3분**
- 이후 셀들: 각 **10초-1분**

---

## 5단계: 데이터 업로드

### 업로드 셀 찾기

노트북 중간쯤 이런 코드 찾기:

```python
# 학습 데이터 업로드
from google.colab import files
uploaded = files.upload()
```

### 실행 과정

#### 1️⃣ 셀 실행

▶ 버튼 클릭

#### 2️⃣ 파일 선택 버튼 표시

```
┌─────────────────────────────┐
│ 업로드할 파일을 선택하세요    │
│                             │
│    [파일 선택]  버튼         │
│                             │
└─────────────────────────────┘
```

#### 3️⃣ 파일 선택

1. "파일 선택" 버튼 클릭
2. `training_data.json` 찾기
3. "열기" 클릭

#### 4️⃣ 업로드 진행

```
training_data.json 업로드 중...
████████████████ 100%

✅ training_data.json (50.2 KB) 업로드 완료
```

#### 5️⃣ 확인 메시지

```python
print(f"✅ 데이터 {len(data)}개 로드 완료")

# 출력:
✅ 데이터 121개 로드 완료
```

### 업로드 주의사항

```
❌ 브라우저 새로고침 금지  → 업로드한 파일 사라짐
❌ 탭 닫기 금지           → 세션 종료됨

✅ 업로드 완료까지 대기
✅ "100%" 표시 확인
```

---

## 6단계: 학습 모니터링

### 학습 시작 셀

```python
# 모델 학습 시작
trainer.train()
```

▶ 실행하면 학습 시작!

### 진행 상황 표시

**에포크(Epoch) 진행:**

```
Epoch 1/3
███████████░░░░░░░░ 60%  
Step 36/60 [01:23<00:55, 0.43it/s]
Loss: 0.5234
```

**의미:**

```
Epoch 1/3      → 전체 3번 반복 중 1번째
60%            → 현재 에포크 60% 완료
Step 36/60     → 60개 스텝 중 36번째
[01:23<00:55]  → 경과 시간: 01:23, 남은 시간: 00:55
0.43it/s       → 초당 0.43 iteration (속도)
Loss: 0.5234   → 손실값 (낮을수록 좋음)
```

### 전체 학습 과정

```
Epoch 1/3: 100%|██████████| 60/60 [02:15<00:00, 0.44it/s]
Loss: 0.5234
────────────────────────────────────────

Epoch 2/3: 100%|██████████| 60/60 [02:12<00:00, 0.45it/s]
Loss: 0.3156
────────────────────────────────────────

Epoch 3/3: 100%|██████████| 60/60 [02:14<00:00, 0.45it/s]
Loss: 0.2341
────────────────────────────────────────

✅ 학습 완료!
최종 Loss: 0.2341
```

### 예상 소요 시간

121개 데이터, 3 에포크 기준:

- **T4 GPU**: 1-2시간
- **V100 GPU (Pro)**: 30분-1시간
- **CPU (비권장)**: 8-12시간

### 학습 중 할 일

```
✅ 커피 마시기 ☕
✅ 산책하기 🚶
✅ 다른 작업하기 💻
✅ 가끔 진행 상황 확인

❌ 브라우저 새로고침
❌ Colab 탭 닫기
❌ 노트북 재시작
```

---

## 7단계: 결과 다운로드

### 학습 완료 후

#### 1️⃣ 테스트 실행 (선택)

```python
# 테스트 프롬프트
test_prompt = "UE5에서 액터 스폰하는 방법은?"
response = model.generate(test_prompt)
print(response)
```

**출력:**
```
GetWorld()->SpawnActor<AActor>(...)를 사용하세요.
```

#### 2️⃣ GGUF 변환

```python
# GGUF로 변환
model.save_pretrained_gguf(
    "model",
    tokenizer,
    quantization_method = "q4_k_m"
)
```

**출력:**
```
Converting to GGUF...
✅ model-q4_k_m.gguf 생성 완료!
```

#### 3️⃣ 파일 다운로드

```python
# 내 컴퓨터로 다운로드
from google.colab import files
files.download('model-q4_k_m.gguf')
```

실행하면:
- 브라우저 다운로드 시작
- Downloads 폴더에 저장됨

### 다운로드 파일

```
model-q4_k_m.gguf
├─ 크기: 약 800MB-1.2GB (모델에 따라)
├─ 형식: GGUF (llama.cpp 호환)
└─ 용도: Ollama, LM Studio 등에서 실행
```

### Google Drive 저장 (추천)

영구 보관용:

```python
# Google Drive 연동
from google.colab import drive
drive.mount('/content/drive')

# 파일 복사
!cp model-q4_k_m.gguf /content/drive/MyDrive/Models/
```

**출력:**
```
✅ Google Drive에 저장 완료!
경로: MyDrive/Models/model-q4_k_m.gguf
```

**장점:**
- Colab 세션 종료돼도 파일 보존
- 언제든 다시 접근 가능
- 용량 제한 (15GB 무료)

---

## 문제 해결

### Q1: "런타임 유형 변경"이 비활성화됨

**증상:**
- 런타임 유형 변경 메뉴가 회색
- 클릭이 안 됨

**해결:**

1. **노트북을 먼저 열어야 함**
   - 메인 페이지에서는 안 보임
   - 노트북 업로드 후 다시 확인

2. **구글 계정 재로그인**
   - 로그아웃 → 다시 로그인 → 새로고침

3. **다른 브라우저 시도**
   - Chrome, Firefox, Edge

---

### Q2: GPU 할당 실패

**증상:**
```
"GPU 할당량을 모두 사용했습니다"
"GPU를 사용할 수 없습니다"
```

**원인:**
- 하루 GPU 사용 시간 초과 (12시간)
- 피크 타임 (저녁 시간대)
- 계정 제한

**해결:**

- **방법 1**: 기다리기 → 24시간 후 할당량 리셋
- **방법 2**: Colab Pro ($9.99/월) → 우선 GPU 할당, 더 긴 사용 시간
- **방법 3**: CPU로 실행 (비권장) → None 선택, 매우 느리지만 작동함
- **방법 4**: 다른 시간대 → 새벽/오전 시도, 사용자 적은 시간

---

### Q3: 파일 업로드 실패

**증상:**
- 파일 선택 후 업로드 안 됨
- "업로드 실패" 메시지

**해결:**

1. **파일 크기 확인**
   - 100MB 이하 권장
   - training_data.json은 보통 작음 (괜찮음)

2. **파일 이름 확인**
   - 한글 파일명 피하기
   - 공백 없는 이름
   - training_data.json (영문)

3. **브라우저 재시작**
   - Colab 탭 닫기 → 브라우저 재시작 → 다시 접속

4. **Google Drive 사용**

```python
from google.colab import drive
drive.mount('/content/drive')

# Drive의 파일 사용
data_path = '/content/drive/MyDrive/training_data.json'
with open(data_path, 'r') as f:
    data = json.load(f)
```

---

### Q4: 실행 중 세션 종료

**증상:**
```
"런타임 연결이 끊어졌습니다"
"세션이 종료되었습니다"
```

**원인:**
- 90분 idle (아무 작업 없음)
- 12시간 최대 실행 시간 초과
- 브라우저 닫음

**해결:**

1. **재연결**
   - "다시 연결" 버튼 클릭
   - 마지막 체크포인트부터 재시작

2. **idle 타임아웃 방지**
   - 학습 중엔 자동으로 방지됨
   - 코드 실행 중 = active 상태

3. **장시간 학습 시 체크포인트 저장**

```python
# 1시간마다 자동 저장
trainer = Trainer(
    ...
    save_steps=500,  # 500스텝마다 저장
)
```

---

### Q5: 패키지 설치 에러

**증상:**
```
ERROR: Could not find a version...
ERROR: No matching distribution found...
```

**해결:**

1. **셀 재실행** (가끔 네트워크 일시 오류)

2. **pip 업그레이드**
```bash
!pip install --upgrade pip
!pip install unsloth
```

3. **특정 버전 명시**
```bash
!pip install unsloth==2023.12
```

4. **캐시 삭제 후 재설치**
```bash
!pip cache purge
!pip install unsloth
```

---

### Q6: 메모리 부족 (OOM)

**증상:**
```
RuntimeError: CUDA out of memory
Killed (메모리 부족)
```

**해결:**

1. **배치 크기 줄이기**
```python
per_device_train_batch_size = 2  # 4→2
```

2. **Gradient Accumulation 늘리기**
```python
gradient_accumulation_steps = 8  # 4→8
```

3. **모델 크기 줄이기**
   - 7B 대신 3B
   - 1B도 학습 가능

4. **Quantization**
```python
load_in_4bit = True  # 이미 적용돼 있을 것
```

---

### Q7: 학습이 너무 느림

**증상:**
```
0.1 it/s (초당 0.1 iteration)
예상 시간: 10시간+
```

**확인 사항:**

1. **GPU 활성화 확인!**
   - 런타임 유형 = T4 GPU?
   - 우측 상단 GPU 아이콘 있나?

2. **CPU로 실행 중이면**
   - 런타임 → 런타임 다시 시작
   - 런타임 유형 → T4 GPU
   - 처음부터 다시 실행

3. **정상 속도**
   - T4 GPU: 0.4-0.5 it/s
   - CPU: 0.01-0.05 it/s (느림!)

---

### Q8: 다운로드 실패

**증상:**
```
files.download() 실행해도 다운로드 안 됨
```

**해결:**

1. **팝업 차단 해제**
   - 브라우저 설정
   - colab.research.google.com 팝업 허용

2. **파일 크기 확인**
   - 너무 크면 (2GB+) 시간 걸림
   - 진행바 확인

3. **Google Drive 사용 (추천)**
   - Drive에 저장 → Drive에서 다운로드
   - 더 안정적

4. **우클릭 저장**
   - 파일 탭에서 파일 찾기
   - 우클릭 → 다운로드

---

### Q9: 코드 실행 순서 꼬임

**증상:**
```
NameError: name 'model' is not defined
ModuleNotFoundError: No module named 'unsloth'
```

**원인:**
- 셀을 순서대로 안 실행함
- 중간 셀을 건너뛰었음

**해결:**

1. **런타임 다시 시작**
   - 런타임 → 런타임 다시 시작

2. **처음부터 순서대로**
   - 런타임 → 모두 실행
   - 또는 Shift+Enter 연타 (위→아래)

3. **순서 지키기**
   - 셀 1 → 셀 2 → 셀 3 → ...

---

### Q10: 결과가 이상함

**증상:**
- 테스트 시 엉뚱한 답변
- 학습 안 된 것 같음

**확인:**

1. **Loss 값 확인**
   - 최종 Loss가 너무 높으면 (1.0+) 학습 부족
   - 0.2-0.5 정도가 정상

2. **학습 데이터 확인**
   - training_data.json 제대로 업로드?
   - 121개 모두 로드?

3. **에포크 수**
   - 3 에포크 권장
   - 1 에포크는 부족할 수 있음

4. **재학습**
   - 하이퍼파라미터 조정
   - learning_rate 낮추기 (2e-4 → 1e-4)

---

## 체크리스트

### 실행 전
- [ ] 구글 계정 로그인 완료
- [ ] colab_notebook.ipynb 파일 준비
- [ ] training_data.json 파일 준비
- [ ] 인터넷 연결 안정적
- [ ] 충분한 시간 확보 (2-3시간)

### 설정 단계
- [ ] Colab 접속 완료
- [ ] 노트북 업로드 완료
- [ ] GPU를 T4로 변경 완료
- [ ] GPU 아이콘 확인됨

### 실행 단계
- [ ] 첫 번째 셀 (패키지 설치) 완료
- [ ] training_data.json 업로드 완료
- [ ] 121개 데이터 로드 확인
- [ ] 학습 시작됨
- [ ] 진행바 정상 작동

### 모니터링
- [ ] Epoch 1/3 완료
- [ ] Epoch 2/3 완료
- [ ] Epoch 3/3 완료
- [ ] 최종 Loss 값 확인 (0.2-0.5)

### 완료 단계
- [ ] 테스트 실행 (선택)
- [ ] GGUF 변환 완료
- [ ] model-q4_k_m.gguf 다운로드 완료
- [ ] 파일 크기 확인 (800MB-1.2GB)
- [ ] Google Drive 백업 (선택)

---

## 예상 소요 시간

### 전체 프로세스

```
┌─────────────────────────────────┐
│ 단계               소요 시간     │
├─────────────────────────────────┤
│ 1. 접속 & 업로드    5분         │
│ 2. GPU 설정         2분         │
│ 3. 패키지 설치      3분         │
│ 4. 데이터 업로드    2분         │
│ 5. 학습 실행        1-2시간     │
│ 6. GGUF 변환        10분        │
│ 7. 다운로드         5분         │
├─────────────────────────────────┤
│ 총합               1.5-2.5시간  │
└─────────────────────────────────┘
```

### 시간대별 권장

```
✅ 추천 시간:
├─ 평일 오전 (9-12시)
├─ 평일 오후 (2-5시)
└─ 주말 오전

⚠️ 피크 타임 (느릴 수 있음):
├─ 평일 저녁 (7-10시)
└─ 주말 저녁
```

---

## 다음 단계 (학습 완료 후)

### 1. Ollama 설치

로컬에서 모델 실행하기

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows
# ollama.com에서 다운로드
```

### 2. 모델 등록

```bash
# Modelfile 생성
cat > Modelfile << EOF
FROM ./model-q4_k_m.gguf
PARAMETER temperature 0.7
PARAMETER top_p 0.9
EOF

# 모델 생성
ollama create my-ue5-assistant -f Modelfile
```

### 3. 모델 실행

```bash
ollama run my-ue5-assistant

>>> UE5에서 액터 스폰하는 방법은?
GetWorld()->SpawnActor<AActor>()를 사용하세요...
```

---

## 유용한 단축키

### Colab 단축키

**실행:**
- `Shift + Enter`: 셀 실행 + 다음으로
- `Ctrl + Enter`: 셀 실행 (이동 안 함)
- `Alt + Enter`: 셀 실행 + 아래에 새 셀 추가

**편집:**
- `Ctrl + M B`: 아래에 셀 추가
- `Ctrl + M A`: 위에 셀 추가
- `Ctrl + M D`: 셀 삭제
- `Ctrl + M Y`: 코드 셀로 변환

**일반:**
- `Ctrl + S`: 저장
- `Ctrl + F`: 찾기
- `Ctrl + /`: 주석 토글

---

## 추가 팁

### 1. 학습 로그 저장

```python
# 로그를 파일로 저장
import sys

class Logger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w")
   
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
   
    def flush(self):
        pass

sys.stdout = Logger("training.log")
```

### 2. 진행 알림

```python
# 학습 완료 시 알림 (소리)
from IPython.display import Audio, display

# 완료음
display(Audio(url='https://sound.peal.io/ps/audios/000/000/537/original/woo_vu_luvub_dub_dub.wav', autoplay=True))
```

### 3. Google Drive 자동 연동

```python
# 노트북 시작 시 자동 연동
from google.colab import drive
drive.mount('/content/drive', force_remount=True)
```

### 4. 체크포인트 자동 저장

```python
# 1시간마다 중간 저장
trainer = Trainer(
    ...
    save_strategy="steps",
    save_steps=500,
    output_dir="/content/drive/MyDrive/checkpoints",
)
```

---

## 참고 자료

### 공식 문서

- [Google Colab 가이드](https://colab.research.google.com/)
- [Unsloth 문서](https://github.com/unslothai/unsloth)
- [Ollama 문서](https://ollama.com/docs)

### 커뮤니티

- Reddit: r/LocalLLaMA
- Discord: Unsloth 서버
- GitHub: Unsloth Issues

---

## 최종 확인

### 성공 기준

**✅ 완전 성공:**
- ✓ model-q4_k_m.gguf 다운로드 완료
- ✓ 파일 크기 800MB+ 확인
- ✓ 테스트 실행 시 정상 응답
- ✓ 최종 Loss < 0.5

**✅ 부분 성공 (재학습 권장):**
- ✓ 파일은 생성됨
- ⚠️ Loss > 0.5 (학습 부족)
- ⚠️ 테스트 응답이 부정확

**❌ 실패 (문제 해결 필요):**
- ✗ 파일 생성 안 됨
- ✗ 에러로 중단됨
- ✗ 메모리 부족으로 실패

---

## 마무리

### 축하합니다! 🎉

이 가이드를 완료하셨다면:

✅ Google Colab 사용법 마스터  
✅ LLM 파인튜닝 경험 습득  
✅ 나만의 AI 모델 생성 완료  

### 다음 학습 과제

1. 더 많은 데이터로 재학습 (500-1000개)
2. 다른 베이스 모델 실험 (7B → 13B)
3. 하이퍼파라미터 튜닝
4. 로컬 환경 구축 (Ollama)
5. 실제 프로젝트 통합

### 문의사항이나 문제 발생 시:

다음 정보와 함께 질문해주세요:
- 에러 메시지 스크린샷
- 실행한 셀 번호
- GPU 활성화 여부

**화이팅! 🚀**
