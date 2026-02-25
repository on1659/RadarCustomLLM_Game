#!/usr/bin/env python3
"""DPO 학습 스크립트 (TRL 직접 사용, unsloth 불필요)
chosen/rejected 페어로 모델 학습
"""

import json
from pathlib import Path
from datasets import Dataset
import torch
import sys

# venv 활성화 확인
if not hasattr(sys, 'real_prefix') and not (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
    print("⚠️  venv가 활성화되지 않았습니다.")
    print("   source ~/Work/LLM/dpo/venv/bin/activate")
    exit(1)

# 설정
DATASET_DIR = Path(__file__).parent / "dataset"
CHOSEN_FILE = DATASET_DIR / "chosen.jsonl"
OUTPUT_DIR = Path(__file__).parent / "models"
OUTPUT_DIR.mkdir(exist_ok=True)

# 모델 경로
BASE_MODEL = "Qwen/Qwen2.5-3B-Instruct"


def load_dataset():
    """chosen.jsonl 로드"""
    data = []
    with open(CHOSEN_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line))
    
    print(f"📚 데이터셋 로드: {len(data)}개 페어")
    
    if len(data) < 10:
        print("⚠️  경고: 데이터가 10개 미만입니다. 최소 50개 이상 권장!")
        choice = input("계속하시겠습니까? (y/N): ").strip().lower()
        if choice != 'y':
            return None
    
    return data


def prepare_dpo_dataset(data):
    """DPO 형식으로 변환"""
    formatted = []
    
    for item in data:
        formatted.append({
            "prompt": item['question'],
            "chosen": item["chosen"],
            "rejected": item["rejected"]
        })
    
    return Dataset.from_list(formatted)


def train_dpo():
    """DPO 학습 실행"""
    print("\n🚀 DPO 학습 시작 (TRL)\n")
    
    # 데이터 로드
    data = load_dataset()
    if not data:
        return
    
    dataset = prepare_dpo_dataset(data)
    print(f"✅ 데이터셋 준비 완료: {len(dataset)}개")
    
    try:
        print("\n📦 라이브러리 로드 중...")
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments
        )
        from peft import LoraConfig, get_peft_model
        from trl import DPOTrainer, DPOConfig
        
        # 모델 로드 (4bit)
        print(f"\n🔧 모델 로드: {BASE_MODEL}")
        
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            llm_int8_enable_fp32_cpu_offload=True,
        )
        
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        
        model_ref = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )
        
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        
        # LoRA 설정
        print("\n🎯 LoRA 어댑터 설정")
        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", 
                          "gate_proj", "up_proj", "down_proj"],
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        )
        
        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()
        
        # DPO 학습 설정
        print("\n⚙️  학습 설정")
        training_args = DPOConfig(
            output_dir=str(OUTPUT_DIR / "checkpoints"),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            num_train_epochs=3,
            learning_rate=5e-5,
            fp16=True,
            logging_steps=5,
            save_steps=100,
            optim="adamw_8bit",
            warmup_ratio=0.1,
            max_length=2048,
            max_prompt_length=1024,
            beta=0.1,
            remove_unused_columns=False,
        )
        
        # Tokenize 함수
        def tokenize_fn(example):
            prompt_full = f"<|im_start|>user\n{example['prompt']}<|im_end|>\n<|im_start|>assistant\n"
            
            prompt_tokens = tokenizer(prompt_full, truncation=True, max_length=1024)
            chosen_tokens = tokenizer(example['chosen'], truncation=True, max_length=1024)
            rejected_tokens = tokenizer(example['rejected'], truncation=True, max_length=1024)
            
            return {
                "prompt": prompt_full,
                "chosen": example['chosen'],
                "rejected": example['rejected'],
            }
        
        dataset = dataset.map(tokenize_fn)
        
        trainer = DPOTrainer(
            model=model,
            ref_model=model_ref,
            args=training_args,
            train_dataset=dataset,
            tokenizer=tokenizer,
        )
        
        # 학습 시작
        print("\n🔥 학습 시작!")
        print(f"  - 데이터: {len(dataset)}개")
        print(f"  - 에폭: {training_args.num_train_epochs}")
        print(f"  - 배치 크기: {training_args.per_device_train_batch_size}")
        print(f"  - 예상 시간: ~{len(dataset) * training_args.num_train_epochs // 10} 분\n")
        
        trainer.train()
        
        # 모델 저장
        print("\n💾 모델 저장 중...")
        model.save_pretrained(str(OUTPUT_DIR / "lora_adapter"))
        tokenizer.save_pretrained(str(OUTPUT_DIR / "lora_adapter"))
        
        print("\n✅ 학습 완료!")
        print(f"\n저장 위치: {OUTPUT_DIR / 'lora_adapter'}")
        print("\n다음 단계:")
        print("  1. python3 dpo/convert-to-gguf.py  # GGUF 변환")
        print("  2. llmcron restart                 # 서버 재시작")
    
    except ImportError as e:
        print(f"\n❌ 라이브러리 설치 필요:")
        print(f"   source ~/Work/LLM/dpo/venv/bin/activate")
        print(f"   pip install transformers trl peft bitsandbytes")
        print(f"\n상세 오류: {e}")
    
    except Exception as e:
        print(f"\n❌ 학습 실패: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # CUDA/MPS 사용 가능 여부 확인
    if not torch.cuda.is_available() and not torch.backends.mps.is_available():
        print("⚠️  경고: GPU/MPS를 찾을 수 없습니다.")
        print("   CPU로 학습하면 매우 느릴 수 있습니다.")
        choice = input("\n계속하시겠습니까? (y/N): ").strip().lower()
        if choice != 'y':
            exit(0)
    
    train_dpo()
