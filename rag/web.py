"""게임위키 AI — localhost:3333 (하이브리드 검색 + 대화 세션)"""
import os
import json
import re
import sqlite3
import time
import uuid
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")
CHAT_DB = os.path.join(os.path.dirname(__file__), "chat.db")
LLAMA_URL = "http://localhost:8090/completion"
PORT = 3333

SYSTEM_PROMPT = """당신은 게임 위키 도우미입니다. 아래 [참고 자료]만을 근거로 답변하세요.

절대 규칙:
1. 참고 자료에 명확한 답이 있을 때만 답변하세요.
2. 참고 자료에 답이 없거나 불확실하면 반드시 "해당 정보를 찾을 수 없습니다."라고만 답하세요. 절대 추측하거나 지어내지 마세요.
3. 답변은 한국어로, 간결하게 하세요.
4. 추가 질문을 만들지 마세요.

[참고 자료]
{context}"""

# ── SQLite 초기화 ──
def init_chat_db():
    conn = sqlite3.connect(CHAT_DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        title TEXT,
        created_at REAL,
        updated_at REAL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        sources TEXT,
        created_at REAL,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )""")
    conn.commit()
    conn.close()

def get_chat_conn():
    return sqlite3.connect(CHAT_DB)

init_chat_db()

# ── HTML ──
HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>🎮 게임위키 AI</title>
<style>
  /* ── 🎨 테마 (여기만 바꾸면 전체 적용) ── */
  :root {
    --c-dark:     #96A78D;   /* 진한 세이지 — 액센트, 버튼 */
    --c-mid:      #B6CEB4;   /* 중간 세이지 — 사이드바, 호버 */
    --c-light:    #D9E9CF;   /* 연한 세이지 — 유저 메시지, 배경 */
    --c-pale:     #F0F0F0;   /* 오프화이트 — 메인 배경 */

    --bg-body:    #f7f7f5;
    --bg-sidebar: #eef3eb;
    --bg-header:  #e8efe4;
    --bg-input:   #ffffff;
    --bg-chat:    #f7f7f5;
    --bg-user:    var(--c-dark);
    --bg-bot:     #ffffff;
    --bg-system:  #eef6e8;

    --border:     #d4ddd0;
    --border-light: #e2ebe0;

    --text:       #2c3e2c;
    --text-light: #6b7b6b;
    --text-pale:  #8a9a8a;
    --text-user:  #ffffff;
    --text-bot:   #2c3e2c;

    --accent:     var(--c-dark);
    --accent-hover: #849a7b;
    --danger:     #c45;
    --danger-hover: #b33;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Pretendard', sans-serif; background: var(--bg-body); color: var(--text); height: 100vh; display: flex; }

  /* 사이드바 */
  .sidebar { width: 260px; background: var(--bg-sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
  .sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
  .sidebar-header button { width: 100%; padding: 10px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 500; }
  .sidebar-header button:hover { background: var(--accent-hover); }
  .session-list { flex: 1; overflow-y: auto; padding: 8px; }
  .session-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text-light); margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 8px; transition: background 0.15s; }
  .session-item:hover { background: var(--c-light); }
  .session-item.active { background: var(--c-mid); color: var(--text); font-weight: 500; }
  .session-item .delete-btn { margin-left: auto; opacity: 0; color: var(--text-pale); font-size: 16px; flex-shrink: 0; transition: opacity 0.15s; }
  .session-item:hover .delete-btn { opacity: 1; }
  .session-item .delete-btn:hover { color: var(--danger); }

  /* 메인 */
  .main { flex: 1; display: flex; flex-direction: column; }
  .header { padding: 16px 24px; background: var(--bg-header); border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .header h1 { font-size: 18px; color: var(--text); }
  .header p { font-size: 12px; color: var(--text-pale); }
  .header .clear-btn { padding: 6px 14px; background: var(--c-light); color: var(--text-light); border: 1px solid var(--border); border-radius: 6px; font-size: 12px; cursor: pointer; transition: all 0.15s; }
  .header .clear-btn:hover { background: var(--c-mid); color: var(--text); }
  .chat { flex: 1; overflow-y: auto; padding: 24px; background: var(--bg-chat); }
  .msg { max-width: 700px; margin: 12px auto; padding: 14px 18px; border-radius: 12px; line-height: 1.7; font-size: 14.5px; }
  .user { background: var(--bg-user); color: var(--text-user); margin-left: auto; max-width: 500px; text-align: right; border-radius: 12px 12px 2px 12px; }
  .bot { background: var(--bg-bot); color: var(--text-bot); border: 1px solid var(--border-light); box-shadow: 0 1px 3px rgba(0,0,0,0.04); border-radius: 12px 12px 12px 2px; }
  .bot .sources { font-size: 12px; color: var(--text-pale); margin-top: 8px; border-top: 1px solid var(--border-light); padding-top: 8px; }
  .system-msg { max-width: 700px; margin: 12px auto; padding: 10px 16px; border-radius: 8px; background: var(--bg-system); border: 1px solid var(--c-light); color: var(--c-dark); font-size: 13px; text-align: center; }
  .input-area { padding: 16px 24px; background: var(--bg-header); border-top: 1px solid var(--border); }
  .input-wrap { max-width: 700px; margin: 0 auto; display: flex; gap: 10px; }
  input { flex: 1; padding: 12px 16px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 15px; outline: none; transition: border 0.15s; }
  input:focus { border-color: var(--accent); }
  input::placeholder { color: var(--text-pale); }
  button.send-btn { padding: 12px 24px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; font-weight: 500; transition: background 0.15s; }
  button.send-btn:hover { background: var(--accent-hover); }
  button.send-btn:disabled { background: var(--border); cursor: not-allowed; }
  .loading { color: var(--text-pale); font-style: italic; }
  .empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-pale); font-size: 18px; }

  /* 게임 선택 버튼 */
  .game-btns button { background: var(--accent) !important; transition: background 0.15s; }
  .game-btns button:hover { background: var(--accent-hover) !important; }

  /* 모바일 */
  @media (max-width: 768px) {
    .sidebar { width: 220px; }
  }
</style>
</head><body>
<div class="sidebar">
  <div class="sidebar-header">
    <button onclick="newSession()">+ 새 대화</button>
  </div>
  <div class="session-list" id="sessionList"></div>
</div>
<div class="main">
  <div class="header">
    <div>
      <h1>🎮 게임위키 AI</h1>
      <p>팰월드 · 오버워치 · 마인크래프트 — RAG</p>
    </div>
    <button class="clear-btn" onclick="clearSession()" title="대화 컨텍스트 초기화">/clear</button>
  </div>
  <div class="chat" id="chat">
    <div class="empty-state" id="emptyState">게임에 대해 물어보세요! 🎮</div>
  </div>
  <div class="input-area">
    <div class="input-wrap">
      <input id="input" placeholder="게임에 대해 물어보세요... (/clear로 컨텍스트 초기화)" autofocus>
      <button class="send-btn" id="btn" onclick="send()">전송</button>
    </div>
  </div>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btn = document.getElementById('btn');
const sessionList = document.getElementById('sessionList');
const emptyState = document.getElementById('emptyState');

let currentSession = null;

// 초기화
loadSessions();

input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

async function loadSessions() {
  const r = await fetch('/api/sessions');
  const sessions = await r.json();
  sessionList.innerHTML = '';
  sessions.forEach(s => {
    const div = document.createElement('div');
    div.className = 'session-item' + (currentSession === s.id ? ' active' : '');
    div.innerHTML = `<span style="flex:1;overflow:hidden;text-overflow:ellipsis">💬 ${esc(s.title)}</span><span class="delete-btn" onclick="event.stopPropagation();deleteSession('${s.id}')">×</span>`;
    div.onclick = () => loadSession(s.id);
    sessionList.appendChild(div);
  });
}

async function newSession() {
  const r = await fetch('/api/sessions', { method: 'POST' });
  const s = await r.json();
  currentSession = s.id;
  chat.innerHTML = '<div class="empty-state">게임에 대해 물어보세요! 🎮</div>';
  await loadSessions();
  input.focus();
}

async function loadSession(id) {
  currentSession = id;
  const r = await fetch(`/api/sessions/${id}/messages`);
  const msgs = await r.json();
  chat.innerHTML = '';
  if (msgs.length === 0) {
    chat.innerHTML = '<div class="empty-state">게임에 대해 물어보세요! 🎮</div>';
  }
  msgs.forEach(m => {
    if (m.role === 'user') {
      chat.innerHTML += `<div class="msg user">${esc(m.content)}</div>`;
    } else if (m.role === 'system') {
      chat.innerHTML += `<div class="system-msg">${esc(m.content)}</div>`;
    } else {
      let html = esc(m.content);
      if (m.sources) {
        const srcs = JSON.parse(m.sources);
        if (srcs.length) html += `<div class="sources">📚 참고: ${srcs.map(s => esc(s)).join(', ')}</div>`;
      }
      chat.innerHTML += `<div class="msg bot">${html}</div>`;
    }
  });
  chat.scrollTop = chat.scrollHeight;
  await loadSessions();
}

async function deleteSession(id) {
  if (!confirm('이 대화를 삭제할까요?')) return;
  await fetch(`/api/sessions/${id}`, { method: 'DELETE' });
  if (currentSession === id) {
    currentSession = null;
    chat.innerHTML = '<div class="empty-state">게임에 대해 물어보세요! 🎮</div>';
  }
  await loadSessions();
}

async function clearSession() {
  if (!currentSession) return;
  await fetch(`/api/sessions/${currentSession}/clear`, { method: 'POST' });
  chat.innerHTML = '<div class="system-msg">🗑️ 컨텍스트가 초기화되었습니다.</div>';
  await loadSessions();
}

async function send() {
  const q = input.value.trim();
  if (!q) return;

  // /clear 명령어
  if (q === '/clear') {
    input.value = '';
    await clearSession();
    return;
  }

  // 세션 없으면 자동 생성
  if (!currentSession) {
    const r = await fetch('/api/sessions', { method: 'POST' });
    const s = await r.json();
    currentSession = s.id;
  }

  input.value = '';
  btn.disabled = true;
  if (document.getElementById('emptyState')) document.getElementById('emptyState').remove();

  chat.innerHTML += `<div class="msg user">${esc(q)}</div>`;
  chat.innerHTML += `<div class="msg bot loading" id="loading">🔍 검색 중...</div>`;
  chat.scrollTop = chat.scrollHeight;

  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query: q, session_id: currentSession })
    });
    const data = await r.json();
    document.getElementById('loading').remove();

    if (data.ask_game && data.games) {
      let html = esc(data.answer);
      html += '<div class="game-btns" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;">';
      data.games.forEach(g => {
        html += `<button onclick="sendWithGame('${esc(g)}','${esc(q)}')" style="padding:8px 16px;background:#4a90d9;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;">${esc(g)}</button>`;
      });
      html += '</div>';
      chat.innerHTML += `<div class="msg bot">${html}</div>`;
    } else {
      let html = esc(data.answer);
      if (data.sources && data.sources.length) {
        html += `<div class="sources">📚 참고: ${data.sources.map(s => esc(s)).join(', ')}</div>`;
      }
      chat.innerHTML += `<div class="msg bot">${html}</div>`;
    }
  } catch(e) {
    document.getElementById('loading').remove();
    chat.innerHTML += `<div class="msg bot">❌ 오류: ${esc(e.message)}</div>`;
  }

  btn.disabled = false;
  chat.scrollTop = chat.scrollHeight;
  input.focus();
  await loadSessions();
}

function sendWithGame(game, originalQ) {
  input.value = game + ' ' + originalQ;
  send();
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>'); }
</script>
</body></html>"""


# ── 벡터 DB + BM25 ──
db = None
bm25_index = None
bm25_docs = None

def tokenize_ko(text):
    """한국어 토크나이저 — 공백 분리 + 슬라이딩 바이그램으로 붙어쓰기 대응"""
    text = text.lower()
    raw_tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text)
    tokens = []
    for t in raw_tokens:
        if len(t) <= 5:
            if len(t) >= 2:
                tokens.append(t)
        else:
            tokens.append(t)
            for i in range(len(t) - 1):
                tokens.append(t[i:i+2])
                if i + 3 <= len(t):
                    tokens.append(t[i:i+3])
    return tokens if tokens else raw_tokens

def get_db():
    global db, bm25_index, bm25_docs
    if db is None:
        embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
        db = FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)
        print("✅ 벡터DB 로드 완료")
        all_docs = db.docstore._dict.values()
        bm25_docs = list(all_docs)
        corpus = [tokenize_ko(doc.page_content) for doc in bm25_docs]
        bm25_index = BM25Okapi(corpus)
        print(f"✅ BM25 인덱스 구축 완료 ({len(bm25_docs)}개 문서)")
    return db


# ── 핸들러 ──
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/sessions':
            conn = get_chat_conn()
            rows = conn.execute("SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC").fetchall()
            conn.close()
            sessions = [{"id": r[0], "title": r[1], "created_at": r[2], "updated_at": r[3]} for r in rows]
            self._json(sessions)
        elif self.path.startswith('/api/sessions/') and self.path.endswith('/messages'):
            sid = self.path.split('/')[3]
            conn = get_chat_conn()
            rows = conn.execute("SELECT role, content, sources FROM messages WHERE session_id=? ORDER BY created_at", (sid,)).fetchall()
            conn.close()
            msgs = [{"role": r[0], "content": r[1], "sources": r[2]} for r in rows]
            self._json(msgs)
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == '/api/sessions':
            # 새 세션 생성
            sid = str(uuid.uuid4())[:8]
            now = time.time()
            conn = get_chat_conn()
            conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                         (sid, "새 대화", now, now))
            conn.commit()
            conn.close()
            self._json({"id": sid, "title": "새 대화"})

        elif self.path.startswith('/api/sessions/') and self.path.endswith('/clear'):
            sid = self.path.split('/')[3]
            conn = get_chat_conn()
            conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
            now = time.time()
            conn.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
                         (sid, "system", "컨텍스트가 초기화되었습니다.", None, now))
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, sid))
            conn.commit()
            conn.close()
            self._json({"ok": True})

        elif self.path == '/api/chat':
            query = body.get("query", "")
            session_id = body.get("session_id")

            # 세션 없으면 자동 생성
            if not session_id:
                session_id = str(uuid.uuid4())[:8]
                now = time.time()
                conn = get_chat_conn()
                conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                             (session_id, query[:30], now, now))
                conn.commit()
                conn.close()

            # 유저 메시지 저장
            now = time.time()
            conn = get_chat_conn()
            conn.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
                         (session_id, "user", query, None, now))

            # 첫 메시지면 제목 업데이트
            msg_count = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id=? AND role='user'", (session_id,)).fetchone()[0]
            if msg_count == 1:
                title = query[:30] + ("..." if len(query) > 30 else "")
                conn.execute("UPDATE sessions SET title=? WHERE id=?", (title, session_id))
            conn.execute("UPDATE sessions SET updated_at=? WHERE id=?", (now, session_id))
            conn.commit()
            conn.close()

            # 게임명 감지
            game_filter = None
            query_lower = query.lower()
            if any(kw in query_lower for kw in ["팰월드", "palworld", "팰"]):
                game_filter = "palworld"
            elif any(kw in query_lower for kw in ["오버워치", "overwatch", "옵치"]):
                game_filter = "overwatch"
            elif any(kw in query_lower for kw in ["마인크래프트", "마크", "minecraft"]):
                game_filter = "minecraft"

            # 하이브리드 검색
            vdb = get_db()
            vec_results = vdb.similarity_search(query, k=8)
            query_tokens = tokenize_ko(query)
            bm25_scores = bm25_index.get_scores(query_tokens)
            top_bm25_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:8]
            bm25_results = [bm25_docs[i] for i in top_bm25_idx if bm25_scores[i] > 0]

            seen = set()
            merged = []
            for doc in vec_results + bm25_results:
                doc_id = doc.page_content[:100]
                if doc_id not in seen:
                    seen.add(doc_id)
                    merged.append(doc)
            results = merged

            if game_filter:
                results = [d for d in results if d.metadata.get("game", "") == game_filter][:5]
            else:
                found_games = set()
                for doc in results:
                    g = doc.metadata.get("game", "")
                    if g:
                        found_games.add(g)
                if len(found_games) >= 2:
                    game_names = {"palworld": "팰월드", "overwatch": "오버워치", "minecraft": "마인크래프트"}
                    game_list = [game_names.get(g, g) for g in sorted(found_games)]
                    ask_msg = f"'{query}'은(는) 여러 게임에 존재합니다. 어떤 게임에 대해 알고 싶으신가요?"
                    # 봇 메시지 저장
                    conn = get_chat_conn()
                    conn.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
                                 (session_id, "assistant", ask_msg, None, time.time()))
                    conn.commit()
                    conn.close()
                    self._json({"answer": ask_msg, "sources": [], "ask_game": True, "games": game_list, "session_id": session_id})
                    return
                results = results[:5]

            context = ""
            sources = []
            for doc in results:
                game = doc.metadata.get("game", "")
                title = doc.metadata.get("title", "")
                chunk = doc.page_content[:800]
                context += f"\n[{game} - {title}]\n{chunk}\n"
                src = f"{game}/{title}"
                if src not in sources:
                    sources.append(src)

            # 이전 대화 컨텍스트 (최근 4개)
            conn = get_chat_conn()
            prev_msgs = conn.execute(
                "SELECT role, content FROM messages WHERE session_id=? AND role IN ('user','assistant') ORDER BY created_at DESC LIMIT 4",
                (session_id,)
            ).fetchall()
            conn.close()
            prev_msgs.reverse()

            history = ""
            for role, content in prev_msgs[:-1]:  # 현재 질문 제외
                if role == "user":
                    history += f"사용자: {content}\n"
                else:
                    history += f"답변: {content}\n"

            # LLM
            system = SYSTEM_PROMPT.format(context=context)
            if history:
                prompt = f"{system}\n\n[이전 대화]\n{history}\n질문: {query}\n\n답변:"
            else:
                prompt = f"{system}\n\n질문: {query}\n\n답변:"

            payload = {
                "prompt": prompt,
                "n_predict": 256,
                "temperature": 0.1,
                "repeat_penalty": 1.5,
                "stop": ["\n\n질문:", "\n질문:", "질문:", "\n\n---", "참고 자료:"],
            }
            try:
                resp = requests.post(LLAMA_URL, json=payload, timeout=60)
                resp.raise_for_status()
                result = resp.json()
                answer = result.get("content", "").strip() or "응답을 생성할 수 없습니다."
            except Exception as e:
                answer = f"LLM 오류: {e}"

            # 봇 메시지 저장
            conn = get_chat_conn()
            conn.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
                         (session_id, "assistant", answer, json.dumps(sources, ensure_ascii=False), time.time()))
            conn.commit()
            conn.close()

            self._json({"answer": answer, "sources": sources, "session_id": session_id})
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith('/api/sessions/'):
            sid = self.path.split('/')[3]
            conn = get_chat_conn()
            conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
            conn.commit()
            conn.close()
            self._json({"ok": True})
        else:
            self.send_response(404)
            self.end_headers()

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass


def main():
    print(f"🎮 게임위키 AI 서버 시작: http://localhost:{PORT}")
    get_db()
    HTTPServer(("", PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()
