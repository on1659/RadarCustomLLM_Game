#!/usr/bin/env python3
"""LoRA 어댑터를 GGUF로 변환
학습한 어댑터를 기존 모델에 병합 후 GGUF 변환
"""

from pathlib import Path
import subprocess

# 경로
DPO_DIR = Path(__file__).parent
ADAPTER_DIR = DPO_DIR / "models/lora_adapter"
OUTPUT_DIR = DPO_DIR / "models"
LLAMA_CPP_DIR = Path.home() / "Work/LLM/llama.cpp"  # llama.cpp 경로
BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def check_requirements():
    """필수 조건 확인"""
    if not ADAPTER_DIR.exists():
        print("❌ LoRA 어댑터를 찾을 수 없습니다.")
        print(f"   먼저 `python dpo/train.py`로 학습하세요.")
        return False
    
    if not LLAMA_CPP_DIR.exists():
        print("❌ llama.cpp를 찾을 수 없습니다.")
        print(f"   예상 경로: {LLAMA_CPP_DIR}")
        print(f"   git clone https://github.com/ggerganov/llama.cpp")
        return False
    
    return True


def merge_lora():
    """LoRA 어댑터를 기본 모델에 병합"""
    print("\n🔄 LoRA 어댑터 병합 중...")
    
    try:
        from unsloth import FastLanguageModel
        
        # 모델 + 어댑터 로드
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=str(ADAPTER_DIR),
            max_seq_length=2048,
            dtype=None,
            load_in_4bit=False,  # 병합 시에는 full precision
        )
        
        # 병합
        merged_dir = OUTPUT_DIR / "merged_model"
        merged_dir.mkdir(exist_ok=True)
        
        model = FastLanguageModel.for_inference(model)  # LoRA 병합
        model.save_pretrained(str(merged_dir))
        tokenizer.save_pretrained(str(merged_dir))
        
        print(f"✅ 병합 완료: {merged_dir}")
        return merged_dir
    
    except Exception as e:
        print(f"❌ 병합 실패: {e}")
        return None


def convert_to_gguf(merged_dir):
    """HuggingFace 모델을 GGUF로 변환"""
    print("\n🔧 GGUF 변환 중...")
    
    convert_script = LLAMA_CPP_DIR / "convert_hf_to_gguf.py"
    quantize_bin = LLAMA_CPP_DIR / "llama-quantize"
    
    if not convert_script.exists():
        print(f"❌ 변환 스크립트를 찾을 수 없습니다: {convert_script}")
        return None
    
    # FP16 GGUF 생성
    fp16_output = OUTPUT_DIR / "model-f16.gguf"
    
    cmd = [
        "python", str(convert_script),
        str(merged_dir),
        "--outfile", str(fp16_output),
        "--outtype", "f16"
    ]
    
    print(f"실행: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ 변환 실패:\n{result.stderr}")
        return None
    
    print(f"✅ FP16 GGUF 생성: {fp16_output}")
    
    # Q4_K_M 양자화
    if quantize_bin.exists():
        q4_output = OUTPUT_DIR / "model-Q4_K_M.gguf"
        
        cmd = [
            str(quantize_bin),
            str(fp16_output),
            str(q4_output),
            "Q4_K_M"
        ]
        
        print(f"\n🔧 양자화 중 (Q4_K_M)...")
        print(f"실행: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"✅ 양자화 완료: {q4_output}")
            return q4_output
        else:
            print(f"⚠️  양자화 실패, FP16 모델 사용:\n{result.stderr}")
            return fp16_output
    
    return fp16_output


def deploy(gguf_path):
    """새 모델을 서버에 배포"""
    print("\n🚀 서버 배포")
    
    target_dir = Path.home() / "Work/LLM/models"
    target_path = target_dir / "Qwen2.5-7B-DPO-Q4_K_M.gguf"
    
    # 복사
    import shutil
    shutil.copy(gguf_path, target_path)
    
    print(f"✅ 배포 완료: {target_path}")
    print("\n다음 단계:")
    print(f"  1. llama-server 재시작:")
    print(f"     pkill llama-server")
    print(f"     cd ~/Work/LLM")
    print(f"     nohup ./build/bin/llama-server -m {target_path} -c 8192 --port 8090 > llama-server.log 2>&1 &")
    print(f"\n  2. 또는 자동 재시작:")
    print(f"     llmcron restart")


if __name__ == "__main__":
    print("🔄 LoRA → GGUF 변환 파이프라인\n")
    
    if not check_requirements():
        exit(1)
    
    # 1. LoRA 병합
    merged_dir = merge_lora()
    if not merged_dir:
        exit(1)
    
    # 2. GGUF 변환
    gguf_path = convert_to_gguf(merged_dir)
    if not gguf_path:
        exit(1)
    
    # 3. 배포
    deploy(gguf_path)
    
    print("\n✅ 모든 과정 완료!")
