"""답변 검증 — 품질 체크 및 자기 검증"""
import re

def validate_answer(answer, query, sources):
    """
    답변 품질 검증 (휴리스틱 기반)
    
    Returns:
        (is_valid, confidence, issues)
        confidence: 0.0 - 1.0
        issues: [문제점 목록]
    """
    issues = []
    confidence = 1.0
    
    # 1) 길이 체크
    if len(answer) < 20:
        issues.append("답변이 너무 짧음")
        confidence -= 0.5
    
    # 2) "없습니다" 패턴
    negative_patterns = [
        "참고 자료에 없습니다",
        "참고자료에 없습니다",
        "정보가 없습니다",
        "찾을 수 없습니다",
        "잘 모르겠",
        "알 수 없",
    ]
    if any(p in answer for p in negative_patterns):
        issues.append("참고자료에 정보 없음")
        confidence -= 0.4
    
    # 3) 출처 없음
    if not sources or len(sources) == 0:
        issues.append("출처 없음")
        confidence -= 0.3
    
    # 4) 의미 없는 반복 (같은 단어 5회 이상)
    words = answer.split()
    if len(words) > 10:
        word_counts = {}
        for w in words:
            if len(w) >= 3:
                word_counts[w] = word_counts.get(w, 0) + 1
        if max(word_counts.values(), default=0) >= 5:
            issues.append("단어 반복 과다")
            confidence -= 0.2
    
    # 5) 중국어/일본어 잔존 (clean_answer 후에도)
    if re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', answer):
        issues.append("외국어 혼입")
        confidence -= 0.3
    
    # 6) 질문 키워드가 답변에 전혀 없음 (너무 동떨어진 답변)
    query_words = [w for w in query.split() if len(w) >= 2]
    if len(query_words) >= 2:
        match_count = sum(1 for w in query_words if w in answer)
        if match_count == 0:
            issues.append("질문과 답변 불일치")
            confidence -= 0.3
    
    # 최종 신뢰도
    confidence = max(confidence, 0.0)
    is_valid = confidence >= 0.4  # 40% 이상이면 valid
    
    return is_valid, confidence, issues


def improve_answer_prompt(answer, query, issues):
    """
    답변 개선용 프롬프트 생성 (추후 LLM 재시도용)
    """
    issue_str = ", ".join(issues)
    return f"""원본 답변에 문제가 있습니다: {issue_str}

질문: {query}
원본 답변: {answer}

문제를 개선해서 다시 답변해주세요. 없는 정보는 추측하지 말고, 있는 정보만 정확히 전달하세요."""
