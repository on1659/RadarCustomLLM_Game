"""멀티스텝 추론 — 복합 질문을 서브쿼리로 분해하고 각각 검색"""
import re

def detect_complex_query(query):
    """
    복합 질문 감지
    
    Returns:
        (is_complex, type, subqueries)
        type: "compare", "list", "multi"
    """
    query_lower = query.lower()
    
    # 게임명 제거 (패턴 매칭 전에)
    query_clean = re.sub(r'(팰월드|마인크래프트|오버워치|마크|옵치)\s*', '', query, flags=re.IGNORECASE)
    
    # 비교 질문 패턴 (느슨한 매칭)
    compare_patterns = [
        r"(.+?)[와과]\s*(.+?)\s*(?:차이|비교|vs)",
        r"(.+?)랑\s*(.+?)\s*(?:차이|비교)",
        r"(.+?)\s*vs\s*(.+)",
        r"(.+?)\s*대\s*(.+?)\s*(?:차이|비교)",
    ]
    
    for pattern in compare_patterns:
        match = re.search(pattern, query_clean)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()
            # 노이즈 제거
            entity1 = re.sub(r'(게임|에서|의)', '', entity1).strip()
            entity2 = re.sub(r'(게임|에서|의)', '', entity2).strip()
            if entity1 and entity2 and len(entity1) >= 2 and len(entity2) >= 2:
                return True, "compare", [entity1, entity2]
    
    # 목록/복수 질문 패턴
    list_patterns = [
        r"(.+?)와\s*(.+?)\s*(뭐|뭘|어떻게|어떤|알려)",
        r"(.+?)과\s*(.+?)\s*(뭐|뭘|어떻게|어떤|알려)",
        r"(.+?)랑\s*(.+?)\s*(뭐|뭘|어떻게|어떤|알려)",
        r"(.+?),\s*(.+?)\s*알려",
    ]
    
    for pattern in list_patterns:
        match = re.search(pattern, query)
        if match:
            entity1 = match.group(1).strip()
            entity2 = match.group(2).strip()
            entity1 = re.sub(r'(팰월드|마인크래프트|오버워치|게임|에서|의)', '', entity1).strip()
            entity2 = re.sub(r'(팰월드|마인크래프트|오버워치|게임|에서|의)', '', entity2).strip()
            if entity1 and entity2:
                return True, "multi", [entity1, entity2]
    
    # "A는? B는?" 패턴
    if query.count("?") >= 2 or query.count("？") >= 2:
        parts = re.split(r'[?？]', query)
        subqueries = [p.strip() for p in parts if p.strip()]
        if len(subqueries) >= 2:
            return True, "multi", subqueries
    
    return False, None, []


def merge_results(subquery_results, query_type):
    """
    서브쿼리 검색 결과를 통합
    
    Args:
        subquery_results: [(subquery, docs, sources), ...]
        query_type: "compare" | "multi"
    
    Returns:
        (merged_context, merged_sources)
    """
    if query_type == "compare":
        # 비교 질문 → 각 엔티티별로 구분해서 제공
        context = ""
        sources = []
        for i, (subquery, docs, srcs) in enumerate(subquery_results):
            context += f"\n### [{subquery}]\n"
            for doc in docs:
                title = doc.metadata.get("title", "")
                chunk = doc.page_content[:400]
                context += f"[{title}]\n{chunk}\n\n"
            sources.extend(srcs)
        return context, list(set(sources))
    
    elif query_type == "multi":
        # 복수 질문 → 순서대로 제공
        context = ""
        sources = []
        for i, (subquery, docs, srcs) in enumerate(subquery_results):
            context += f"\n### 질문 {i+1}: {subquery}\n"
            for doc in docs:
                title = doc.metadata.get("title", "")
                chunk = doc.page_content[:350]
                context += f"[{title}]\n{chunk}\n\n"
            sources.extend(srcs)
        return context, list(set(sources))
    
    return "", []


def build_multi_step_prompt(query, context, query_type):
    """
    멀티스텝 추론용 프롬프트 생성
    """
    if query_type == "compare":
        system = """너는 게임 위키 도우미야. 두 대상을 비교해서 명확히 설명해줘.

# 규칙
1. 각 대상의 주요 특징을 먼저 요약
2. 차이점을 구체적으로 비교 (능력, 용도, 강점/약점)
3. 추천 상황이 있으면 알려줘
4. **참고 자료의 정보만 사용** (추측 금지)

# 참고 자료
{context}"""
    elif query_type == "multi":
        system = """너는 게임 위키 도우미야. 여러 질문에 대해 각각 답변해줘.

# 규칙
1. 각 질문별로 명확히 구분해서 답변
2. 순서대로 답변 (질문1 → 답변1, 질문2 → 답변2)
3. **참고 자료의 정보만 사용** (추측 금지)

# 참고 자료
{context}"""
    else:
        system = """너는 게임 위키 도우미야. **참고 자료의 정보를 EXACTLY 그대로 전달**해야 해.

# 참고 자료
{context}"""

    return system.format(context=context) + f"\n\n질문: {query}\n\n답변:"
