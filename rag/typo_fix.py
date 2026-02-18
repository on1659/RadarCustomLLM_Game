"""오타 보정 모듈"""
from difflib import get_close_matches

# 게임별 주요 키워드 (영웅명, 아이템명 등)
GAME_KEYWORDS = {
    "overwatch": [
        "겐지", "한조", "정크랫", "리퍼", "솔저", "트레이서", "파라", "메이", 
        "라인하르트", "루시우", "머시", "아나", "디바", "자리야", "오리사",
        "둠피스트", "모이라", "브리기테", "애쉬", "바티스트", "시그마", "에코",
        "위도우메이커", "토르비욘", "바스티온", "맥크리", "캐서디", "시메트라",
        "젠야타", "윈스턴", "자리야", "로드호그", "레킹볼", "솜브라",
        "궁극기", "스킬", "카운터", "힐러", "탱커", "딜러", "공격군", "지원군",
        "오버워치", "overwatch", "옵치"  # 게임명 추가
    ],
    "minecraft": [
        "다이아몬드", "네더라이트", "크리퍼", "엔더드래곤", "위더", "좀비",
        "스켈레톤", "엔더맨", "블레이즈", "가스트", "피글린", "호글린",
        "철", "금", "석탄", "레드스톤", "청금석", "에메랄드",
        "곡괭이", "검", "도끼", "삽", "괭이", "낚싯대", "활", "화살",
        "포션", "마법부여", "인챈트", "양조", "조합", "제련",
        "네더", "엔드", "바이옴", "마을", "던전", "요새",
        "마인크래프트", "minecraft", "마크"  # 게임명 추가
    ],
    "palworld": [
        "팰", "람볼", "캣티바", "치키피", "펭킹", "펭귄", "아누비스", "조르노아",
        "번식", "교배", "작업", "채굴", "벌목", "수송", "농장", "목장",
        "고대문명", "파츠", "팰구", "팰볼", "보스", "전설", "희귀",
        "베이스", "건축", "제작", "무기", "방어구",  # "기지" 제거 (오버워치와 충돌)
        "팰월드", "palworld"  # 게임명 추가
    ]
}

# 전체 키워드 리스트 (중복 제거)
ALL_KEYWORDS = []
for keywords in GAME_KEYWORDS.values():
    ALL_KEYWORDS.extend(keywords)
ALL_KEYWORDS = list(set(ALL_KEYWORDS))

def fix_typo(query, threshold=0.7):
    """
    쿼리의 오타를 자동 보정
    
    Args:
        query: 원본 쿼리
        threshold: 유사도 임계값 (0.0-1.0, 높을수록 엄격)
    
    Returns:
        (보정된 쿼리, 변경 여부)
    """
    words = query.split()
    fixed_words = []
    changed = False
    
    for word in words:
        # 2글자 이상 단어만 체크
        if len(word) >= 2:
            # 정확히 일치하는 키워드 찾기
            if word in ALL_KEYWORDS:
                fixed_words.append(word)
                continue
            
            # 유사 키워드 찾기
            matches = get_close_matches(word, ALL_KEYWORDS, n=1, cutoff=threshold)
            if matches:
                fixed_words.append(matches[0])
                changed = True
            else:
                fixed_words.append(word)
        else:
            fixed_words.append(word)
    
    fixed_query = " ".join(fixed_words)
    return fixed_query, changed
