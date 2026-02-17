# LLM 추론모델 프로젝트 로그

> 일별 상세 로그는 `logs/YYYY-MM-DD_log.md`에 저장됩니다.

## 📌 프로젝트 요약

### 환경
- Mac mini M4 16GB, macOS
- llama.cpp: `~/llama.cpp/build/bin/llama-server`
- Python venv: `~/Work/LLM/crawler/venv/` (RAG/크롤러 공용)
- GitHub: https://github.com/on1659/RadarCustomLLM_Game

### 파인튜닝 모델
- Qwen2.5-3B-Instruct + LoRA, GGUF Q4_K_M (1.93GB)
- 121개 chain-of-thought 데이터, Colab T4 학습

### RAG 시스템
- 크롤링: 나무위키(28문서) + palworld.gg(57문서)
- 임베딩: `jhgan/ko-sroberta-multitask` (한국어 특화)
- 검색: 하이브리드 (벡터 유사도 + BM25 키워드)
- 벡터DB: 4,084청크 (FAISS)
- 기능: 게임명 자동 필터, 역질문(disambiguation)

### 실행
```bash
startllm / stopllm / statusllm
```

### TODO
- [ ] `<think>` 추론 태그 → 학습 데이터 500개 확장 필요
- [ ] palworld.gg 인코딩 깨짐 재크롤링
- [ ] 팰월드 나무위키 하위문서 URL 수정
- [ ] 70B 모델 테스트 (128GB PC)

---

## 로그 목록
| 날짜 | 주요 내용 |
|------|-----------|
| [2026-02-17](logs/2026-02-17_log.md) | QA 2/4→4/4: 엔더드래곤/아누비스 데이터 추가, 동의어 매핑, 질문 자동보정 |
| [2026-02-16](logs/2026-02-16_log.md) | 프로젝트 시작, Colab 파인튜닝, RAG 구축, 하이브리드 검색 도입 |
