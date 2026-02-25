#!/bin/bash
# DPO 학습 환경 설치 스크립트

set -e

echo "🚀 DPO 학습 환경 설치"
echo ""

# Python 버전 확인
echo "📌 Python 버전 확인..."
python3 --version || {
    echo "❌ Python3이 설치되어 있지 않습니다."
    exit 1
}

# Virtual environment 생성
VENV_DIR="$HOME/Work/LLM/dpo/venv"

if [ ! -d "$VENV_DIR" ]; then
    echo ""
    echo "🔧 Virtual environment 생성 중..."
    python3 -m venv "$VENV_DIR"
    echo "✅ venv 생성 완료: $VENV_DIR"
else
    echo ""
    echo "✅ venv 이미 존재: $VENV_DIR"
fi

# venv 활성화
echo ""
echo "🔌 venv 활성화..."
source "$VENV_DIR/bin/activate"

# pip 업그레이드
echo ""
echo "📦 pip 업그레이드..."
pip install --upgrade pip

# 필수 라이브러리 설치
echo ""
echo "📚 필수 라이브러리 설치 중..."
pip install \
    torch \
    transformers \
    datasets \
    accelerate \
    peft \
    bitsandbytes \
    trl

echo ""
echo "⚠️  unsloth 제외됨 (xformers 빌드 이슈)"
echo "   → trl DPOTrainer로 학습 (동일 기능)"

echo ""
echo "✅ 라이브러리 설치 완료!"

# llama.cpp 확인
echo ""
echo "🔧 llama.cpp 확인..."
if [ ! -d "$HOME/Work/LLM/llama.cpp" ]; then
    echo "⚠️  llama.cpp가 설치되어 있지 않습니다."
    echo ""
    read -p "지금 설치하시겠습니까? (y/N): " install_llama
    
    if [ "$install_llama" = "y" ] || [ "$install_llama" = "Y" ]; then
        cd ~/Work/LLM
        git clone https://github.com/ggerganov/llama.cpp
        cd llama.cpp
        make
        pip3 install -r requirements.txt
        echo "✅ llama.cpp 설치 완료!"
    else
        echo "⏭️  건너뜀. 나중에 수동으로 설치하세요:"
        echo "   cd ~/Work/LLM"
        echo "   git clone https://github.com/ggerganov/llama.cpp"
        echo "   cd llama.cpp && make"
    fi
else
    echo "✅ llama.cpp 이미 설치됨"
fi

# GPU/MPS 확인
echo ""
echo "🎮 GPU/MPS 확인..."
python3 -c "
import torch
if torch.cuda.is_available():
    print('✅ CUDA 사용 가능:', torch.cuda.get_device_name(0))
elif torch.backends.mps.is_available():
    print('✅ MPS (Apple Silicon) 사용 가능')
else:
    print('⚠️  GPU/MPS 없음 - CPU 학습 (느림)')
"

echo ""
echo "🎉 설치 완료!"
echo ""
echo "다음 단계:"
echo "  1. python3 dpo/collect-data.py  # 데이터 수집"
echo "  2. python3 dpo/manual-fix.py    # 수동 답변 작성"
echo "  3. python3 dpo/train.py         # DPO 학습"
