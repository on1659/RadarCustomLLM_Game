# 챗봇 통합 가이드 (게임위키 AI API)

이 API를 여러분의 챗봇 서비스(카카오톡, 디스코드, 텔레그램 등)에 연결하는 방법을 설명합니다.

## 🚀 빠른 시작 (3분)

### 1️⃣ API 호출 기본

```bash
# 테스트 요청 (curl)
curl -X POST "https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: 93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599" \
  -d '{
    "query": "마인크래프트 다이아몬드 어디서 구해?",
    "session_id": "user_12345"
  }'
```

**응답:**
```json
{
  "answer": "다이아몬드는 보루 잔해의 상자에서 종종 나온다...",
  "sources": ["minecraft/마인크래프트_아이템"],
  "session_id": "user_12345"
}
```

### 2️⃣ 핵심 개념

| 항목 | 설명 | 예시 |
|------|------|------|
| **query** | 사용자 질문 (게임명 포함 권장) | "오버워치 한조 궁극기" |
| **session_id** | 대화 연속성 유지용 ID | 사용자 ID, 채팅방 ID 등 |
| **answer** | AI 답변 | "한조는 초자연적인 능력을..." |
| **sources** | 참고 문서 목록 | `["overwatch/한조(오버워치)"]` |

---

## 💬 대화 연속성 (핵심!)

### ✅ 같은 session_id → 대화 이어짐

```python
# 1번째 요청
{"query": "마인크래프트 다이아몬드는?", "session_id": "user_123"}
# → "보루 상자에서 나온다..."

# 2번째 요청 (같은 session_id)
{"query": "어떻게 구해?", "session_id": "user_123"}
# → "다이아몬드는 보루 상자에서..." (맥락 기억!)
```

### ❌ 다른 session_id → 독립 대화

```python
{"query": "어떻게 구해?", "session_id": "user_456"}
# → "여러 게임에 존재합니다. 어떤 게임?" (맥락 없음)
```

### 📌 session_id 설정 팁

**1:1 채팅봇:**
```python
session_id = f"user_{user_id}"  # 사용자별 독립 대화
```

**그룹 채팅봇 (⚠️ 중요!):**

❌ **잘못된 방법** (그룹 전체가 하나의 대화):
```python
session_id = f"group_{group_id}"
# 문제: A가 "한조 알려줘" → B가 "궁극기는?" 하면
# B의 질문이 A의 맥락으로 이어짐 (혼란!)
```

✅ **올바른 방법** (그룹 내 개인별 대화):
```python
session_id = f"group_{group_id}_user_{user_id}"
# A: "한조 알려줘" → A만의 세션
# B: "겐지 알려줘" → B만의 세션 (A와 독립!)
```

**웹 채팅:**
```python
session_id = f"web_{uuid.uuid4()}"  # 브라우저 세션별
```

---

## 🎭 그룹 채팅 시나리오 비교

### ❌ 잘못된 구현 (그룹 전체 세션)

```python
# 모든 사용자가 같은 session_id 사용
session_id = f"group_{chat_id}"
```

**문제 발생:**
```
👤 철수: 오버워치 한조 알려줘
🤖 AI: 한조는 시마다 일족의 암살자입니다...

👤 영희: 마인크래프트 다이아몬드는?
🤖 AI: 다이아몬드는 보루 상자에서...

👤 철수: 궁극기는?
🤖 AI: 다이아몬드의 궁극기는... ❌ (한조 궁극기를 물은 건데!)

👤 영희: 어떻게 구해?
🤖 AI: 한조는 상점에서... ❌ (다이아몬드 획득법을 물은 건데!)
```

**원인:** 모두가 같은 세션을 공유해서 대화가 뒤섞임!

### ✅ 올바른 구현 (개인별 세션)

```python
# 각 사용자마다 다른 session_id
session_id = f"group_{chat_id}_user_{user_id}"
```

**정상 작동:**
```
👤 철수: 오버워치 한조 알려줘
🤖 AI: 한조는 시마다 일족의 암살자입니다...

👤 영희: 마인크래프트 다이아몬드는?
🤖 AI: 다이아몬드는 보루 상자에서...

👤 철수: 궁극기는?
🤖 AI: 한조의 궁극기는 용의 일격입니다... ✅

👤 영희: 어떻게 구해?
🤖 AI: 다이아몬드는 Y좌표 -64~16에서... ✅
```

**핵심:** 각자 독립된 대화 맥락 유지!

---

## 🛠️ 실전 예제

### Python (카카오톡 챗봇)

```python
import requests
import json

API_URL = "https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat"
API_KEY = "93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599"

def ask_game_wiki(user_message, user_id):
    """게임위키 AI에게 질문"""
    payload = {
        "query": user_message,
        "session_id": f"kakao_{user_id}"  # 카카오 사용자ID로 세션 관리
    }
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["answer"]
    except requests.exceptions.Timeout:
        return "⏱️ 응답 시간 초과 (30초). 다시 시도해주세요."
    except Exception as e:
        return f"❌ 오류 발생: {e}"

# 카카오톡 스킬 핸들러
@app.route("/skill", methods=["POST"])
def kakao_skill():
    req = request.json
    user_msg = req["userRequest"]["utterance"]
    user_id = req["userRequest"]["user"]["id"]
    
    answer = ask_game_wiki(user_msg, user_id)
    
    return jsonify({
        "version": "2.0",
        "template": {
            "outputs": [{"simpleText": {"text": answer}}]
        }
    })
```

### Node.js (디스코드 봇)

```javascript
const axios = require('axios');
const { Client, GatewayIntentBits } = require('discord.js');

const API_URL = 'https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat';
const API_KEY = '93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599';

async function askGameWiki(query, sessionId) {
  try {
    const response = await axios.post(API_URL, 
      { query, session_id: sessionId },
      { 
        headers: { 
          'Content-Type': 'application/json',
          'X-API-Key': API_KEY 
        },
        timeout: 30000
      }
    );
    return response.data.answer;
  } catch (error) {
    if (error.code === 'ECONNABORTED') {
      return '⏱️ 응답 시간 초과. 다시 시도해주세요.';
    }
    return `❌ 오류: ${error.message}`;
  }
}

const client = new Client({ 
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent] 
});

client.on('messageCreate', async (message) => {
  if (message.author.bot) return;
  
  // "!게임 질문" 형식
  if (message.content.startsWith('!게임 ')) {
    const query = message.content.slice(4);
    
    // ✅ 그룹 채널: 개인별 세션 관리 (추천)
    const sessionId = `discord_${message.channel.id}_user_${message.author.id}`;
    
    const answer = await askGameWiki(query, sessionId);
    await message.reply(answer);
  }
});

client.login('YOUR_BOT_TOKEN');
```

**왜 이렇게 해야 하나요?**

```javascript
// ❌ 채널별 세션 (문제 발생)
const sessionId = `discord_${message.channel.id}`;

// 시나리오:
// - 철수: "!게임 오버워치 한조"
// - AI: "한조는 초자연적인 능력을..."
// - 영희: "!게임 궁극기는?" 
// - AI: "한조의 궁극기는..." (← 영희가 한조를 안 물어봤는데!)

// ✅ 개인별 세션 (올바른 방법)
const sessionId = `discord_${message.channel.id}_user_${message.author.id}`;

// 시나리오:
// - 철수: "!게임 오버워치 한조"
// - AI: "한조는 초자연적인 능력을..."
// - 영희: "!게임 궁극기는?" 
// - AI: "여러 게임에 존재합니다. 어떤 게임?" (← 영희 세션은 독립!)
```

### Python (텔레그램 봇 - 그룹 지원)

```python
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

API_URL = "https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat"
API_KEY = "93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599"

def ask_game_wiki(query: str, session_id: str) -> str:
    """게임위키 AI에게 질문"""
    payload = {"query": query, "session_id": session_id}
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": API_KEY
    }
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()["answer"]
    except requests.exceptions.Timeout:
        return "⏱️ 응답 시간 초과 (30초). 다시 시도해주세요."
    except Exception as e:
        return f"❌ 오류: {e}"

async def game_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """그룹/개인 채팅 모두 지원"""
    user_query = " ".join(context.args)
    if not user_query:
        await update.message.reply_text("사용법: /게임 질문내용")
        return
    
    # ✅ 그룹 채팅: 개인별 세션 관리
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if update.effective_chat.type in ['group', 'supergroup']:
        # 그룹: chat_id + user_id 조합
        session_id = f"telegram_group_{chat_id}_user_{user_id}"
    else:
        # 개인 채팅: user_id만 사용
        session_id = f"telegram_user_{user_id}"
    
    answer = ask_game_wiki(user_query, session_id)
    await update.message.reply_text(answer)

def main():
    app = Application.builder().token("YOUR_BOT_TOKEN").build()
    app.add_handler(CommandHandler("게임", game_command))
    app.run_polling()

if __name__ == '__main__':
    main()
```

**실제 사용 예시 (텔레그램 그룹):**

```
👤 철수: /게임 오버워치 한조
🤖 AI: 한조는 초자연적인 능력을 사용하는 영웅입니다...

👤 영희: /게임 겐지는?
🤖 AI: 겐지는 시마다 일족의...

👤 철수: /게임 궁극기는?
🤖 AI: 한조의 궁극기는... (← 철수의 이전 대화 맥락 유지!)

👤 영희: /게임 궁극기는?
🤖 AI: 겐지의 궁극기는... (← 영희의 이전 대화 맥락 유지!)
```

**session_id 구조:**
- 철수: `telegram_group_-123456789_user_111111`
- 영희: `telegram_group_-123456789_user_222222`
- → 같은 그룹이지만 **각자 독립된 대화!**

### JavaScript (웹 채팅)

```javascript
// 브라우저 세션ID 생성 (최초 1회)
let sessionId = localStorage.getItem('game_wiki_session');
if (!sessionId) {
  sessionId = 'web_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  localStorage.setItem('game_wiki_session', sessionId);
}

async function askGameWiki(query) {
  const response = await fetch('https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': '93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599'
    },
    body: JSON.stringify({
      query: query,
      session_id: sessionId
    })
  });
  
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  
  const data = await response.json();
  return data.answer;
}

// 사용 예시
document.getElementById('sendBtn').addEventListener('click', async () => {
  const userInput = document.getElementById('userInput').value;
  const answer = await askGameWiki(userInput);
  displayMessage('AI', answer);
});
```

---

## 🎯 고급 기능

### 1️⃣ 오타 자동 보정

사용자가 "오버워치 칸조"라고 입력하면:
```json
{
  "answer": "🔍 혹시 '오버워치 한조'를 찾으시나요?\n\n한조는 초자연적인 능력을...",
  "sources": ["overwatch/한조(오버워치)"]
}
```

→ **자동으로 보정된 키워드로 재검색해서 답변!**

### 2️⃣ 게임 선택 (다중 게임 감지)

"다이아몬드"처럼 여러 게임에 존재하는 키워드:
```json
{
  "answer": "'다이아몬드'은(는) 여러 게임에 존재합니다. 어떤 게임에 대해 알고 싶으신가요?",
  "sources": [],
  "ask_game": true,
  "games": ["마인크래프트", "팰월드"]
}
```

→ **사용자에게 게임 선택 요청**

후속 질문:
```json
{"query": "마인크래프트", "session_id": "same_session"}
```

→ **마인크래프트 다이아몬드 정보 출력**

### 3️⃣ 세션 초기화

대화를 처음부터 다시 시작하려면:
```python
# 새로운 session_id 생성
new_session_id = f"user_{user_id}_{timestamp}"
```

---

## ⚠️ 에러 처리

### 타임아웃 처리

```python
try:
    response = requests.post(API_URL, json=payload, timeout=30)
except requests.exceptions.Timeout:
    return "응답 시간이 너무 오래 걸립니다. 잠시 후 다시 시도해주세요."
```

### HTTP 에러

```python
try:
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        return "API 키가 유효하지 않습니다."
    elif e.response.status_code == 500:
        return "서버 오류입니다. 잠시 후 다시 시도해주세요."
    else:
        return f"오류 발생 ({e.response.status_code})"
```

### 빈 응답 처리

```python
data = response.json()
if not data.get("answer"):
    return "답변을 생성할 수 없습니다. 질문을 다시 입력해주세요."
```

---

## 📊 성능 최적화

### 1️⃣ 응답 시간 단축

- **게임명 명시**: "한조" → "오버워치 한조" (검색 정확도 ↑)
- **구체적 질문**: "정보" → "궁극기 알려줘" (관련 문서만 검색)

### 2️⃣ 동시 요청 제한

```python
import asyncio
from aiohttp import ClientSession

# 동시 최대 3개 요청
semaphore = asyncio.Semaphore(3)

async def ask_with_limit(query, session_id):
    async with semaphore:
        async with ClientSession() as session:
            async with session.post(API_URL, json={...}) as resp:
                return await resp.json()
```

### 3️⃣ 캐싱 (선택)

자주 묻는 질문은 캐싱:
```python
import redis
r = redis.Redis()

def ask_with_cache(query, session_id):
    cache_key = f"qa:{query}"
    cached = r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    answer = ask_game_wiki(query, session_id)
    r.setex(cache_key, 3600, json.dumps(answer))  # 1시간 캐시
    return answer
```

---

## 🔐 보안

### API 키 관리

**❌ 절대 하지 마세요:**
```javascript
// 클라이언트 JavaScript에 API 키 노출
const API_KEY = '93bedb...';  // ← 위험!
```

**✅ 올바른 방법:**
```javascript
// 백엔드 서버에서만 API 호출
app.post('/ask', async (req, res) => {
  const answer = await askGameWiki(req.body.query, req.session.id);
  res.json({ answer });
});
```

### 환경 변수 사용

```bash
# .env
GAME_WIKI_API_KEY=93bedb51b1faf8f507813267ce9f268e5b818da82ae90312c3a954f44fcc9599
GAME_WIKI_API_URL=https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat
```

```python
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('GAME_WIKI_API_KEY')
```

---

## 🧪 테스트 시나리오

### 1️⃣ 기본 질문

```bash
curl -X POST "API_URL" \
  -H "X-API-Key: YOUR_KEY" \
  -d '{"query":"오버워치 겐지 궁극기","session_id":"test1"}'
```
**기대:** 겐지 궁극기 정보 출력

### 2️⃣ 후속 질문

```bash
# 1번째
curl ... -d '{"query":"마인크래프트 다이아몬드","session_id":"test2"}'
# 2번째 (같은 session_id)
curl ... -d '{"query":"어떻게 구해?","session_id":"test2"}'
```
**기대:** 다이아몬드 구하는 법 출력 (맥락 유지)

### 3️⃣ 오타 보정

```bash
curl ... -d '{"query":"오버워치 칸조","session_id":"test3"}'
```
**기대:** "혹시 '한조'를 찾으시나요?" + 한조 정보

---

## 📞 문제 해결

### "응답을 생성할 수 없습니다"

**원인:**
- LLM 서버 다운
- 검색 결과 없음

**해결:**
1. 게임명을 명시: "한조" → "오버워치 한조"
2. 질문을 구체화: "정보" → "궁극기 알려줘"

### 타임아웃 (30초 초과)

**원인:**
- 서버 과부하
- 네트워크 지연

**해결:**
```python
# 재시도 로직
for attempt in range(3):
    try:
        return ask_game_wiki(query, session_id)
    except Timeout:
        if attempt == 2:
            return "서버 응답 없음"
        time.sleep(2 ** attempt)  # 지수 백오프
```

### 대화가 이어지지 않음

**원인:**
- session_id가 매번 다름

**해결:**
```python
# ❌ 잘못된 예
session_id = f"user_{uuid.uuid4()}"  # 매번 새 ID 생성

# ✅ 올바른 예
session_id = f"user_{user_id}"  # 사용자별 고정 ID
```

---

## 📚 참고 자료

- **전체 API 문서**: `API_GUIDE.md`
- **GitHub 저장소**: `on1659/RadarCustomLLM_Game`
- **서버 상태**: `https://awhirl-preimpressive-carina.ngrok-free.dev/api/chat` (POST)

---

## 💡 FAQ

**Q: 무료로 사용 가능한가요?**
A: 현재는 개인 프로젝트용 무료 제공. 상업적 이용은 문의 필요.

**Q: 응답 속도는?**
A: 평균 2-5초 (질문 복잡도에 따라 다름)

**Q: 지원 게임은?**
A: 마인크래프트, 오버워치, 팰월드 (추가 예정)

**Q: 한국어만 지원?**
A: 현재 한국어 전용. 영어/일본어는 일부만 인식.

**Q: 세션은 언제까지 유지?**
A: 마지막 대화 후 30분간 유지 (이후 자동 만료)

---

**🎮 Happy Coding!**
