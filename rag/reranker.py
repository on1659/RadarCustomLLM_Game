"""리랭킹 — 검색 결과 품질 평가 및 재정렬"""
import re

def calculate_search_quality(ranked_docs, query, rrf_scores):
    """
    검색 결과 품질 점수 계산
    
    Args:
        ranked_docs: [(score, doc), ...]
        query: 원본 질문
        rrf_scores: {doc_id: rrf_score}
    
    Returns:
        quality_score (0.0 - 1.0)
    """
    if not ranked_docs:
        return 0.0
    
    # 1) 상위 3개 문서의 평균 RRF 점수
    top3_scores = [score for score, _ in ranked_docs[:3]]
    avg_score = sum(top3_scores) / len(top3_scores) if top3_scores else 0.0
    
    # 2) 제목 매칭 비율 (상위 5개 중)
    query_clean = query.lower().replace(" ", "")
    query_words = [w for w in query.split() if len(w) > 1]
    
    title_match_count = 0
    for _, doc in ranked_docs[:5]:
        title = doc.metadata.get("title", "").lower()
        title_clean = title.replace(" ", "").replace(":", "").replace("_", "").replace("/", "").replace("-", "")
        
        # 정확 매칭 또는 부분 매칭
        if query_clean in title_clean or title_clean in query_clean:
            title_match_count += 1
        elif sum(1 for word in query_words if word in title) >= 2:
            title_match_count += 0.5
    
    title_ratio = title_match_count / 5.0
    
    # 3) 점수 분산 (낮을수록 좋음 - 상위 문서들이 비슷하면 신뢰도 높음)
    if len(top3_scores) >= 2:
        mean = sum(top3_scores) / len(top3_scores)
        variance = sum((s - mean) ** 2 for s in top3_scores) / len(top3_scores)
        consistency = 1.0 / (1.0 + variance * 10)  # 분산 → 일관성 점수
    else:
        consistency = 0.5
    
    # 종합 품질 점수 (가중 평균)
    quality = (
        avg_score * 0.4 +      # RRF 점수
        title_ratio * 0.4 +     # 제목 매칭
        consistency * 0.2       # 일관성
    )
    
    return min(quality, 1.0)


def should_retry_search(quality_score, threshold=0.15):
    """
    검색 재시도 필요 여부 판단
    
    Args:
        quality_score: 품질 점수 (0.0 - 1.0)
        threshold: 재시도 임계값
    
    Returns:
        bool
    """
    return quality_score < threshold


def expand_query_for_retry(query):
    """
    재검색용 쿼리 확장
    - 동의어 추가
    - 관련 키워드 추가
    """
    expanded_terms = []
    
    # 동의어 확장
    SYNONYMS = {
        "체력": ["HP", "생명력", "피통"],
        "공격력": ["데미지", "딜", "피해"],
        "스킬": ["능력", "기술"],
        "궁극기": ["궁", "필살기"],
        "만드는법": ["제작법", "조합법", "크래프트"],
        "잡는법": ["사냥법", "킬법", "공략"],
    }
    
    query_lower = query.lower()
    for word, synonyms in SYNONYMS.items():
        if word in query_lower:
            expanded_terms.extend(synonyms)
    
    # 확장 쿼리 생성
    if expanded_terms:
        return query + " " + " ".join(expanded_terms[:2])
    
    return query


def contextual_boost(doc, query, base_score):
    """
    문맥 기반 부스트 (휴리스틱)
    - 질문 유형과 문서 내용 일치도
    """
    content = doc.page_content.lower()
    query_lower = query.lower()
    boost = 0.0
    
    # 1) 수치 질문 + 문서에 숫자 포함
    if any(kw in query_lower for kw in ["체력", "공격", "데미지", "수치", "몇", "얼마"]):
        if re.search(r'\d+', content):
            boost += 1.0
    
    # 2) 방법 질문 + 절차 키워드
    if any(kw in query_lower for kw in ["어떻게", "방법", "하는법", "만드는법"]):
        if any(kw in content for kw in ["먼저", "다음", "이후", "그리고", "단계"]):
            boost += 0.8
    
    # 3) 목록 질문 + 나열 패턴
    if any(kw in query_lower for kw in ["종류", "목록", "뭐가있", "알려줘"]):
        # 여러 항목이 나열되어 있는지 (반복 패턴)
        if content.count(",") >= 3 or content.count("·") >= 2:
            boost += 0.6
    
    return base_score + boost
