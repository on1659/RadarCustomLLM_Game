#!/bin/bash

# LLM RAG 서버 QA 자동 테스트 스크립트
# 매번 랜덤 4개 질문 선택 + 로그 기록

API_URL="https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat"
LOG_DIR="$HOME/.openclaw/workspace/log"
LOG_FILE="$LOG_DIR/$(date +%Y-%m-%d).md"

# 질문 풀
MINECRAFT_POOL=("엔더드래곤" "위더" "네더라이트" "레드스톤" "다이아몬드" "쿠키" "크리퍼" "좀비" "엔더진주" "엔더맨" "TNT" "피스톤" "호퍼")
PALWORLD_POOL=("아누비스" "펜킹" "람볼" "컬러리스" "제트래곤" "프로스탈론" "크레모리스" "치키파이" "토큰토스" "루나리스" "라바" "그림사")
OVERWATCH_POOL=("한조" "겐지" "솔저:76" "매리" "리퍼" "위도우메이커" "아나" "정크랫" "트레이서" "라인하르트" "메르시" "루시오")

# 역질문 풀
HOW_POOL=("펜킹 외형" "네더라이트 얻는 방법" "한조의 궁극기" "엔더드래곤 잡는 법" "위더 소환 방법" "다이아몬드 찾는 법")

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

# 랜덤 선택 함수
random_pick() {
    local -n arr=$1
    local count=$2
    local picked=()
    
    while [ ${#picked[@]} -lt $count ]; do
        local idx=$((RANDOM % ${#arr[@]}))
        local item="${arr[$idx]}"
        
        # 중복 체크
        local is_dup=0
        for p in "${picked[@]}"; do
            if [ "$p" == "$item" ]; then
                is_dup=1
                break
            fi
        done
        
        if [ $is_dup -eq 0 ]; then
            picked+=("$item")
        fi
    done
    
    echo "${picked[@]}"
}

# 질문 선택 (각 카테고리에서 1개 + 역질문 1개)
QUESTIONS=()
QUESTIONS+=($(random_pick MINECRAFT_POOL 1))
QUESTIONS+=($(random_pick PALWORLD_POOL 1))
QUESTIONS+=($(random_pick OVERWATCH_POOL 1))
QUESTIONS+=($(random_pick HOW_POOL 1))

# 섞기
QUESTIONS=($(printf '%s\n' "${QUESTIONS[@]}" | shuf))

# 테스트 실행
TIMESTAMP=$(date +"%H:%M:%S")
RESULTS=()
SUCCESS_COUNT=0

echo "## [$TIMESTAMP] LLM RAG QA 테스트" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

for i in "${!QUESTIONS[@]}"; do
    Q="${QUESTIONS[$i]}"
    RESPONSE=$(curl -s -X POST "$API_URL" \
        -H "Content-Type: application/json" \
        -d "{\"query\":\"$Q\"}" \
        --max-time 30)
    
    if echo "$RESPONSE" | grep -q '"answer"'; then
        # 성공: answer 필드에서 첫 30자 추출
        ANSWER=$(echo "$RESPONSE" | jq -r '.answer' | head -c 30 | tr '\n' ' ')
        RESULTS+=("$((i+1)). $Q → $ANSWER...")
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    else
        # 실패
        RESULTS+=("$((i+1)). $Q → ❌ 실패 (응답 없음)")
    fi
done

# 결과 로그 기록
if [ $SUCCESS_COUNT -eq 4 ]; then
    echo "✅ QA 통과 (4/4)" >> "$LOG_FILE"
else
    echo "❌ QA 실패 ($SUCCESS_COUNT/4)" >> "$LOG_FILE"
fi

for result in "${RESULTS[@]}"; do
    echo "$result" >> "$LOG_FILE"
done

echo "" >> "$LOG_FILE"

# 텔레그램 알림 (OpenClaw message tool 사용)
if [ $SUCCESS_COUNT -eq 4 ]; then
    SUMMARY="✅ QA 통과 (4/4)\n$(printf '%s\n' "${RESULTS[@]}")"
else
    SUMMARY="❌ QA 실패 ($SUCCESS_COUNT/4)\n$(printf '%s\n' "${RESULTS[@]}")"
fi

echo "$SUMMARY"
