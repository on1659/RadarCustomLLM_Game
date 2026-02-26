"""게임위키 AI — localhost:3333 (하이브리드 검색 + 대화 세션)"""
import os
import sys
import json
import re
import sqlite3
import time
import uuid
import threading
import atexit
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi
from typo_fix import fix_typo
from multi_step import detect_complex_query, merge_results, build_multi_step_prompt
from reranker import calculate_search_quality, should_retry_search, expand_query_for_retry, contextual_boost
from validator import validate_answer

DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")
CHAT_DB = os.path.join(os.path.dirname(__file__), "chat.db")
LLAMA_URL = "http://localhost:8090/completion"
PORT = 3334
API_KEY = os.getenv("GAME_WIKI_API_KEY")  # 환경변수에서 API 키 읽기 (없으면 None)

SYSTEM_PROMPT = """너는 게임 위키 도우미야. **참고 자료의 정보를 EXACTLY 그대로 전달**해야 해.

# 절대 규칙 (최우선 - 반드시 지킬 것!)

1. **숫자, 이름, 능력치, 목록은 참고 자료에서 정확히 복사해서 답해** (예: "체력 70", "공격력 100", "초당 170 피해")
2. **참고 자료에 없는 정보는 절대 답하지 마** - "참고 자료에 해당 정보가 없습니다"라고만 해
3. **추측하거나 일반 상식으로 답하지 마** - 오직 참고 자료만 사용
4. **참고 자료를 바탕으로 자연스러운 문장으로 설명** (복사-붙여넣기 X, 자연스러운 요약 O)

# 답변 가이드

1. **완전한 답변**: 질문에 대한 답을 최대한 상세히 제공하세요.
   - 캐릭터/아이템/몬스터라면: 기본 정보, 능력, 특징, 사용법 등을 포함하세요.
   - 시스템/메커니즘이라면: 작동 방식, 조건, 효과를 설명하세요.

2. **구조화된 답변**: 여러 정보가 있다면 단락으로 나누거나 번호를 매기세요.

3. **간결함 유지**: 불필요한 서론이나 맺음말 없이 핵심 정보만 전달하세요.

4. **언어 제약**: 한국어로만 답변하세요. 위키 문법, HTML 태그, 코드는 제거하세요.

# 참고 자료

{context}

# 답변 예시 (참고 자료에서 EXACT 인용!)

질문: "오버워치 리퍼의 능력은?"
답변: "리퍼는 헬파이어 샷건을 무기로 사용하며, 패시브로 영혼 수확(피해를 줄 때마다 체력 회복)을 가집니다. 스킬은 망령화(무적 상태), 그림자 밟기(순간이동)이고, 궁극기는 죽음의 꽃(주변 적에게 초당 170 피해, 3초 지속)입니다."

질문: "마인크래프트 위더 소환 방법은?"
답변: "소울샌드 4개를 T자 모양으로 쌓고, 그 위에 위더 스켈레톤 해골 3개를 올리면 위더가 소환됩니다. 네더에서만 소환 가능합니다."

질문: "팰월드 람볼 특성은?"
답변: "람볼(Lamball)은 중립 타입 팰이며, 작업 적성은 목장 Lv1입니다. 체력 70, 공격력 5로 초반 팰입니다."

질문: "다이아몬드는 어디서 나와?"
답변: "참고 자료에 다이아몬드 획득 위치 정보가 없습니다."

이제 답변하세요:"""

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

# ── 인메모리 세션 캐시 + 지연 저장 ──
FLUSH_DELAY = 30  # 30초 무응답 시 DB 저장

class SessionCache:
    """채팅 중에는 메모리만 사용, 일정 시간 후 DB에 배치 저장"""
    SESSION_TIMEOUT = 1800  # 30분 (초)
    MAX_MESSAGES = 50       # 세션당 최대 메시지 수
    
    def __init__(self):
        self._lock = threading.Lock()
        self._sessions = {}  # {sid: {"game": str, "last_query": str, "messages": [...], "dirty": bool, "last_active": float, "title": str}}
        self._timers = {}    # {sid: Timer}

    def get(self, sid):
        with self._lock:
            return self._sessions.get(sid)

    def ensure(self, sid, title=""):
        with self._lock:
            # 기존 세션 확인
            if sid in self._sessions:
                sess = self._sessions[sid]
                # 만료 체크 (30분 경과)
                if time.time() - sess["last_active"] > self.SESSION_TIMEOUT:
                    print(f"[세션 만료] {sid} - {int((time.time() - sess['last_active']) / 60)}분 경과, 초기화", file=sys.stderr, flush=True)
                    sess["messages"] = []
                    sess["game"] = None
                    sess["last_query"] = ""
                    sess["last_active"] = time.time()
                return sess
            
            # 새 세션 생성
            self._sessions[sid] = {
                "game": None,
                "last_query": "",
                "messages": [],
                "dirty": False,
                "last_active": time.time(),
                "title": title or sid,
            }
            return self._sessions[sid]

    def add_message(self, sid, role, content, sources=None):
        with self._lock:
            sess = self._sessions.get(sid)
            if not sess:
                return
            
            # 메시지 추가
            sess["messages"].append({"role": role, "content": content, "sources": sources, "ts": time.time()})
            
            # 최대 메시지 수 제한
            if len(sess["messages"]) > self.MAX_MESSAGES:
                removed_count = len(sess["messages"]) - self.MAX_MESSAGES
                sess["messages"] = sess["messages"][-self.MAX_MESSAGES:]
                print(f"[메시지 제한] {sid} - 오래된 {removed_count}개 메시지 제거", file=sys.stderr, flush=True)
            
            # 활동 시간 업데이트
            sess["last_active"] = time.time()
            sess["dirty"] = True
            sess["last_active"] = time.time()
            # 타이머 리셋
            if sid in self._timers:
                self._timers[sid].cancel()
            self._timers[sid] = threading.Timer(FLUSH_DELAY, self._flush_session, args=[sid])
            self._timers[sid].daemon = True
            self._timers[sid].start()

    def set_game(self, sid, game):
        with self._lock:
            sess = self._sessions.get(sid)
            if sess:
                sess["game"] = game

    def set_last_query(self, sid, query):
        with self._lock:
            sess = self._sessions.get(sid)
            if sess:
                sess["last_query"] = query

    def get_history(self, sid, limit=4):
        """최근 N개 메시지 반환 (메모리에서)"""
        with self._lock:
            sess = self._sessions.get(sid)
            if not sess:
                return []
            return sess["messages"][-limit:]

    def _flush_session(self, sid):
        """세션 데이터를 DB에 저장"""
        with self._lock:
            sess = self._sessions.get(sid)
            if not sess or not sess["dirty"]:
                return
            try:
                conn = get_chat_conn()
                # 세션 존재 확인, 없으면 생성
                exists = conn.execute("SELECT id FROM sessions WHERE id=?", (sid,)).fetchone()
                now = time.time()
                if not exists:
                    conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                                 (sid, sess["title"], sess["messages"][0]["ts"] if sess["messages"] else now, now))
                else:
                    conn.execute("UPDATE sessions SET updated_at=?, title=? WHERE id=?", (now, sess["title"], sid))
                # 기존 메시지 삭제 후 재삽입 (간단)
                conn.execute("DELETE FROM messages WHERE session_id=?", (sid,))
                for msg in sess["messages"]:
                    conn.execute("INSERT INTO messages (session_id, role, content, sources, created_at) VALUES (?,?,?,?,?)",
                                 (sid, msg["role"], msg["content"], json.dumps(msg["sources"]) if msg["sources"] else None, msg["ts"]))
                conn.commit()
                conn.close()
                sess["dirty"] = False
                print(f"[CACHE] 세션 {sid} DB 저장 완료 ({len(sess['messages'])}건)")
            except Exception as e:
                print(f"[CACHE] 세션 {sid} DB 저장 실패: {e}")

    def flush_all(self):
        """모든 dirty 세션 즉시 저장 (종료 시)"""
        sids = list(self._sessions.keys())
        for sid in sids:
            self._flush_session(sid)
        print(f"[CACHE] 전체 flush 완료 ({len(sids)}개 세션)")

    def load_from_db(self, sid):
        """DB에서 기존 세션 로드 (서버 재시작 후 복원)"""
        conn = get_chat_conn()
        rows = conn.execute(
            "SELECT role, content, sources, created_at FROM messages WHERE session_id=? ORDER BY created_at",
            (sid,)
        ).fetchall()
        sess_row = conn.execute("SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
        conn.close()
        if rows:
            sess = self.ensure(sid, title=sess_row[0] if sess_row else sid)
            with self._lock:
                sess["messages"] = [{"role": r, "content": c, "sources": json.loads(s) if s else None, "ts": t} for r, c, s, t in rows]
                # 이전 게임 추출
                for msg in reversed(sess["messages"]):
                    if msg["sources"]:
                        src_str = str(msg["sources"]).lower()
                        if "palworld" in src_str: sess["game"] = "palworld"; break
                        elif "overwatch" in src_str: sess["game"] = "overwatch"; break
                        elif "minecraft" in src_str: sess["game"] = "minecraft"; break
            return sess
        return None

cache = SessionCache()
atexit.register(cache.flush_all)

# ── HTML ──
HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>🎮 게임위키 AI</title>
<style>
  /* ── 🎨 테마 (여기만 바꾸면 전체 적용) ── */
  :root {
    --c-dark:     #9CAFAA;   /* 민트그레이 — 액센트, 버튼 */
    --c-mid:      #D6DAC8;   /* 연올리브 — 사이드바, 호버 */
    --c-light:    #FBF3D5;   /* 크림 — 유저 메시지, 배경 */
    --c-pale:     #D6A99D;   /* 핑크베이지 — 포인트 */

    --bg-body:    #faf8f4;
    --bg-sidebar: #f2efe8;
    --bg-header:  #eeebe4;
    --bg-input:   #ffffff;
    --bg-chat:    #faf8f4;
    --bg-user:    var(--c-dark);
    --bg-bot:     #ffffff;
    --bg-system:  #f5f3e8;

    --border:     #ddd9d0;
    --border-light: #e8e4dc;

    --text:       #3a3530;
    --text-light: #7a7570;
    --text-pale:  #9a9590;
    --text-user:  #ffffff;
    --text-bot:   #3a3530;

    --accent:     var(--c-dark);
    --accent-hover: #889e98;
    --danger:     var(--c-pale);
    --danger-hover: #c4948a;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, 'Pretendard', sans-serif; background: var(--bg-body); color: var(--text); height: 100vh; display: flex; }

  /* 사이드바 */
  .sidebar { width: 260px; background: var(--bg-sidebar); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; }
  .sidebar-header { padding: 16px; border-bottom: 1px solid var(--border); }
  .sidebar-header button { width: 100%; padding: 10px; background: var(--c-pale); color: #fff; border: none; border-radius: 8px; font-size: 14px; cursor: pointer; font-weight: 500; }
  .sidebar-header button:hover { background: var(--danger-hover); }
  .session-list { flex: 1; overflow-y: auto; padding: 8px; }
  .session-item { padding: 10px 12px; border-radius: 8px; cursor: pointer; font-size: 13px; color: var(--text-light); margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 8px; transition: background 0.15s; }
  .session-item:hover { background: var(--c-light); }
  .session-item.active { background: var(--c-mid); color: var(--text); font-weight: 500; border-left: 3px solid var(--c-pale); }
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
  .bot .sources { font-size: 12px; color: var(--text-pale); margin-top: 8px; border-top: 1px solid var(--c-pale); padding-top: 8px; opacity: 0.8; }
  .system-msg { max-width: 700px; margin: 12px auto; padding: 10px 16px; border-radius: 8px; background: var(--bg-system); border: 1px solid var(--c-light); color: var(--c-dark); font-size: 13px; text-align: center; }
  .input-area { padding: 16px 24px; background: var(--bg-header); border-top: 1px solid var(--border); }
  .input-wrap { max-width: 700px; margin: 0 auto; display: flex; gap: 10px; }
  input { flex: 1; padding: 12px 16px; background: var(--bg-input); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 15px; outline: none; transition: border 0.15s; }
  input:focus { border-color: var(--c-pale); }
  input::placeholder { color: var(--text-pale); }
  button.send-btn { padding: 12px 24px; background: var(--c-pale); color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; font-weight: 500; transition: background 0.15s; }
  button.send-btn:hover { background: var(--danger-hover); }
  button.send-btn:disabled { background: var(--border); cursor: not-allowed; }
  .loading { color: var(--text-pale); font-style: italic; }
  .empty-state { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--text-pale); font-size: 18px; }

  /* 게임 선택 버튼 */
  .game-btns button { background: var(--c-pale) !important; transition: background 0.15s; }
  .game-btns button:hover { background: var(--danger-hover) !important; }

  /* 테마 패널 */
  .theme-panel { display: none; position: absolute; top: 56px; right: 24px; background: #fff; border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); z-index: 100; width: 280px; }
  .theme-panel.open { display: block; }
  .theme-panel h3 { font-size: 14px; margin-bottom: 14px; color: var(--text); }
  .theme-row { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .theme-row label { font-size: 12px; color: var(--text-light); width: 80px; flex-shrink: 0; }
  .theme-row input[type="color"] { width: 36px; height: 36px; border: 2px solid var(--border); border-radius: 8px; cursor: pointer; padding: 2px; background: #fff; }
  .theme-row .hex { font-size: 11px; color: var(--text-pale); font-family: monospace; }
  .theme-presets { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border-light); }
  .theme-presets button { padding: 5px 10px; font-size: 11px; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; background: var(--bg-input); color: var(--text-light); transition: all 0.15s; }
  .theme-presets button:hover { background: var(--c-light); color: var(--text); }

  /* 햄버거 메뉴 */
  .menu-btn { display: none; padding: 6px 10px; background: none; border: 1px solid var(--border); border-radius: 6px; font-size: 18px; cursor: pointer; color: var(--text); }
  .sidebar .close-btn { display: none; position: absolute; top: 12px; right: 12px; background: none; border: none; font-size: 20px; cursor: pointer; color: var(--text-pale); }
  .overlay { display: none; }

  /* 모바일 */
  @media (max-width: 768px) {
    .sidebar { position: fixed; left: -280px; top: 0; bottom: 0; width: 260px; z-index: 200; transition: left 0.25s ease; box-shadow: none; }
    .sidebar.open { left: 0; box-shadow: 4px 0 20px rgba(0,0,0,0.15); }
    .sidebar .close-btn { display: block; }
    .overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 199; }
    .overlay.open { display: block; }
    .menu-btn { display: block; }
    .header h1 { font-size: 15px; }
    .header p { font-size: 11px; }
    .msg { padding: 8px 12px; font-size: 13px; line-height: 1.5; margin: 6px 8px; max-width: 85%; border-radius: 10px; }
    .user { max-width: 75%; margin-left: auto; margin-right: 8px; }
    .bot { max-width: 85%; margin-left: 8px; }
    .system-msg { margin: 6px 8px; padding: 6px 10px; font-size: 11px; }
    .bot .sources { font-size: 10px; }
    .input-wrap { gap: 6px; }
    input { font-size: 14px; padding: 10px 12px; }
    button.send-btn { padding: 10px 14px; font-size: 13px; }
    .theme-panel { right: 8px; width: 240px; top: 46px; padding: 14px; }
    .chat { padding: 8px 4px; }
    .header { padding: 10px 14px; }
    .header .clear-btn { padding: 4px 10px; font-size: 11px; }
    .input-area { padding: 10px 12px; }
    .empty-state { font-size: 15px; }
  }
</style>
</head><body>
<div class="sidebar" id="sidebar">
  <button class="close-btn" onclick="closeSidebar()">✕</button>
  <div class="sidebar-header">
    <button onclick="newSession()">+ 새 대화</button>
  </div>
  <div class="session-list" id="sessionList"></div>
</div>
<div class="main">
  <div class="overlay" id="overlay" onclick="closeSidebar()"></div>
  <div class="header">
    <button class="menu-btn" onclick="openSidebar()">☰</button>
    <div>
      <h1>🎮 게임위키 AI</h1>
      <p>팰월드 · 오버워치 · 마인크래프트 — RAG</p>
    </div>
    <button class="clear-btn" onclick="clearSession()" title="대화 컨텍스트 초기화">/clear</button>
    <button class="clear-btn" onclick="toggleThemePanel()" title="테마 설정" style="margin-left:6px">🎨</button>
  </div>
  <div class="theme-panel" id="themePanel">
    <h3>🎨 테마 색상</h3>
    <div class="theme-row">
      <label>액센트</label>
      <input type="color" id="tc-dark" value="#9CAFAA" onchange="updateTheme()">
      <span class="hex" id="hex-dark">#9CAFAA</span>
    </div>
    <div class="theme-row">
      <label>사이드바</label>
      <input type="color" id="tc-mid" value="#D6DAC8" onchange="updateTheme()">
      <span class="hex" id="hex-mid">#D6DAC8</span>
    </div>
    <div class="theme-row">
      <label>밝은 배경</label>
      <input type="color" id="tc-light" value="#FBF3D5" onchange="updateTheme()">
      <span class="hex" id="hex-light">#FBF3D5</span>
    </div>
    <div class="theme-row">
      <label>포인트</label>
      <input type="color" id="tc-pale" value="#D6A99D" onchange="updateTheme()">
      <span class="hex" id="hex-pale">#D6A99D</span>
    </div>
    <div class="theme-presets">
      <button onclick="applyPreset('#9CAFAA','#D6DAC8','#FBF3D5','#D6A99D')">🍑 웜톤</button>
      <button onclick="applyPreset('#96A78D','#B6CEB4','#D9E9CF','#F0F0F0')">🌿 세이지</button>
      <button onclick="applyPreset('#4a90d9','#2a5a8f','#1a3a5c','#111111')">🌙 다크</button>
      <button onclick="applyPreset('#A0937D','#C7BCA1','#E1D7C6','#F5EFE6')">☕ 베이지</button>
      <button onclick="applyPreset('#7895B2','#AEBDCA','#D4E2F1','#F5EFE6')">🧊 블루</button>
    </div>
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
  closeSidebar();
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

// 모바일 사이드바
function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('overlay').classList.add('open');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('overlay').classList.remove('open');
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>'); }

// ── 테마 ──
function toggleThemePanel() {
  document.getElementById('themePanel').classList.toggle('open');
}

function updateTheme() {
  const d = document.getElementById('tc-dark').value;
  const m = document.getElementById('tc-mid').value;
  const l = document.getElementById('tc-light').value;
  const p = document.getElementById('tc-pale').value;
  applyColors(d, m, l, p);
  document.getElementById('hex-dark').textContent = d.toUpperCase();
  document.getElementById('hex-mid').textContent = m.toUpperCase();
  document.getElementById('hex-light').textContent = l.toUpperCase();
  document.getElementById('hex-pale').textContent = p.toUpperCase();
}

function applyPreset(d, m, l, p) {
  document.getElementById('tc-dark').value = d;
  document.getElementById('tc-mid').value = m;
  document.getElementById('tc-light').value = l;
  document.getElementById('tc-pale').value = p;
  applyColors(d, m, l, p);
  document.getElementById('hex-dark').textContent = d.toUpperCase();
  document.getElementById('hex-mid').textContent = m.toUpperCase();
  document.getElementById('hex-light').textContent = l.toUpperCase();
  document.getElementById('hex-pale').textContent = p.toUpperCase();
}

function applyColors(d, m, l, p) {
  const r = document.documentElement.style;
  r.setProperty('--c-dark', d);
  r.setProperty('--c-mid', m);
  r.setProperty('--c-light', l);
  r.setProperty('--c-pale', p);
  // 파생 색상 자동 계산
  r.setProperty('--bg-user', d);
  r.setProperty('--accent', d);
  r.setProperty('--danger', p);
  // 다크 프리셋 감지
  const brightness = hexBrightness(d);
  if (brightness < 100) {
    // 다크 모드
    r.setProperty('--bg-body', '#0a0a0a');
    r.setProperty('--bg-sidebar', '#111');
    r.setProperty('--bg-header', '#111');
    r.setProperty('--bg-chat', '#0a0a0a');
    r.setProperty('--bg-bot', '#1a1a2e');
    r.setProperty('--bg-input', '#1a1a1a');
    r.setProperty('--bg-system', '#1a2a1a');
    r.setProperty('--border', '#333');
    r.setProperty('--border-light', '#222');
    r.setProperty('--text', '#e0e0e0');
    r.setProperty('--text-light', '#bbb');
    r.setProperty('--text-pale', '#888');
    r.setProperty('--text-bot', '#e0e0e0');
  } else {
    // 라이트 모드
    r.setProperty('--bg-body', mixColor(l, '#ffffff', 0.5));
    r.setProperty('--bg-sidebar', mixColor(m, '#f5f5f0', 0.3));
    r.setProperty('--bg-header', mixColor(m, '#f0f0ea', 0.3));
    r.setProperty('--bg-chat', mixColor(l, '#ffffff', 0.5));
    r.setProperty('--bg-bot', '#ffffff');
    r.setProperty('--bg-input', '#ffffff');
    r.setProperty('--bg-system', mixColor(l, '#f5f5f0', 0.4));
    r.setProperty('--border', mixColor(m, '#cccccc', 0.4));
    r.setProperty('--border-light', mixColor(l, '#dddddd', 0.4));
    r.setProperty('--text', '#3a3530');
    r.setProperty('--text-light', '#7a7570');
    r.setProperty('--text-pale', '#9a9590');
    r.setProperty('--text-bot', '#3a3530');
  }
  localStorage.setItem('theme', JSON.stringify([d, m, l, p]));
}

function hexBrightness(hex) {
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return (r * 299 + g * 587 + b * 114) / 1000;
}

function mixColor(c1, c2, ratio) {
  const h = s => parseInt(s.slice(1),16);
  const a = h(c1), b = h(c2);
  const mix = (a,b,r) => Math.round(a + (b-a) * r);
  const r1 = (a>>16)&0xff, g1 = (a>>8)&0xff, b1 = a&0xff;
  const r2 = (b>>16)&0xff, g2 = (b>>8)&0xff, b2 = b&0xff;
  const rr = mix(r1,r2,ratio), gg = mix(g1,g2,ratio), bb = mix(b1,b2,ratio);
  return '#' + ((1<<24)+(rr<<16)+(gg<<8)+bb).toString(16).slice(1);
}

// 저장된 테마 복원
(function() {
  const saved = localStorage.getItem('theme');
  if (saved) {
    try {
      const [d,m,l,p] = JSON.parse(saved);
      document.getElementById('tc-dark').value = d;
      document.getElementById('tc-mid').value = m;
      document.getElementById('tc-light').value = l;
      document.getElementById('tc-pale').value = p;
      applyColors(d, m, l, p);
      document.getElementById('hex-dark').textContent = d.toUpperCase();
      document.getElementById('hex-mid').textContent = m.toUpperCase();
      document.getElementById('hex-light').textContent = l.toUpperCase();
      document.getElementById('hex-pale').textContent = p.toUpperCase();
    } catch(e) {}
  }
})();
</script>
</body></html>"""


# ── 검색 상수 (모듈 레벨 — 매 요청마다 재생성 방지) ──
RRF_K = 60  # Reciprocal Rank Fusion 파라미터

INTENT_WEIGHTS = {
    "stat":    (0.4, 0.6),  # 수치 질문 → BM25 우세 (키워드 정확도)
    "howto":   (0.6, 0.4),  # 방법 질문 → Vector 우세 (의미론적)
    "list":    (0.6, 0.4),  # 목록 질문 → Vector 우세
    "compare": (0.6, 0.4),  # 비교 질문 → Vector 우세
    "general": (0.6, 0.4),  # 일반 → Vector 우세 (의미론적 유사도 중시)
}

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

def clean_answer(text):
    """답변 후처리: 중국어 제거, 반복 제거, 태그 제거"""
    # 1) 중국어/일본어 나오면 그 앞까지만
    for i, ch in enumerate(text):
        if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff':
            text = text[:i].rstrip('。，, ')
            break
    # 2) 내부 태그 제거
    text = re.sub(r'\[[\w\s\-/_.]+\]', '', text)
    text = re.sub(r'```[\s\S]*', '', text)
    text = re.sub(r'#[\w]+', '', text)
    # 3) 반복 문장 제거
    sentences = re.split(r'(?<=[.다요함임])\s+', text)
    seen = set()
    result = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        key = re.sub(r'\s+', '', s)[:50]
        if key not in seen:
            seen.add(key)
            result.append(s)
    text = ' '.join(result)
    # 4) 고유명사 교정 (3B 모델 오생성 대응)
    NOUN_FIXES = {
        "팜월드": "팰월드", "팅크 월드": "팰월드", "팅크월드": "팰월드",
        "아누bis": "아누비스", "아누비s": "아누비스",
        "겐지i": "겐지", "한조o": "한조",
        "엔더 드래gon": "엔더 드래곤",
        "마인크래프트t": "마인크래프트",
    }
    for wrong, right in NOUN_FIXES.items():
        if wrong in text:
            text = text.replace(wrong, right)
    # 5) 끝 정리
    text = text.strip()
    if text and text[-1] not in '.다요함임':
        # 마지막 마침표/문장끝까지만
        last = max(text.rfind('.'), text.rfind('다'), text.rfind('요'), text.rfind('함'), text.rfind('임'))
        if last > len(text) // 2:
            text = text[:last+1]
    return text.strip() or "잘 모르겠어요."

def classify_intent(query):
    """질문 의도 분류 — 검색 가중치 조절에 사용"""
    stat_words = ["체력", "HP", "hp", "공격력", "방어력", "데미지", "스탯", "수치", "몇", "얼마"]
    howto_words = ["어떻게", "방법", "하는법", "만드는법", "잡는법", "가는법", "공략", "팁", "가이드", "만들어"]
    list_words = ["종류", "목록", "리스트", "뭐가있", "알려줘", "적성", "스킬", "드롭"]
    compare_words = ["차이", "비교", "vs", "VS", "좋은", "강한", "약한", "추천"]

    if any(w in query for w in stat_words):
        return "stat"
    if any(w in query for w in compare_words):
        return "compare"
    if any(w in query for w in howto_words):
        return "howto"
    if any(w in query for w in list_words):
        return "list"
    return "general"


def rewrite_query(query, search_query):
    """쿼리 리라이트 — 검색에 최적화된 형태로 변환
    gamewiki 레퍼런스: 사용자 질문을 검색 키워드로 재구성"""
    # 불용어 제거
    stopwords = ["좀", "에 대해", "에대해", "알려줘", "설명해줘", "가르쳐줘", "뭔지", "뭐야", "뭐임", "뭐에요", "해줘"]
    rewritten = search_query
    for sw in stopwords:
        rewritten = rewritten.replace(sw, "")
    # 게임명 약어 확장
    GAME_EXPAND = {
        "마크": "마인크래프트",
        "오버워치": "오버워치",
        "옵치": "오버워치",
        "팰": "팰월드",
    }
    for short, full in GAME_EXPAND.items():
        if rewritten.startswith(short + " ") or rewritten.startswith(short + "의"):
            rewritten = rewritten.replace(short, full, 1)
            break
    return rewritten.strip()


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
    def check_api_key(self):
        """API 키 검증 (설정되어 있을 때만)"""
        if API_KEY:  # API_KEY가 설정되어 있으면 검증
            request_key = self.headers.get("X-API-Key", "")
            if request_key != API_KEY:
                self.send_response(403)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": "Invalid or missing API key",
                    "message": "Set X-API-Key header with valid key"
                }).encode())
                return False
        return True

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
            # 새 세션 생성 (최대 10개 제한, FIFO queue)
            conn = get_chat_conn()
            
            # 현재 세션 개수 확인
            count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            
            # 10개 이상이면 가장 오래된 것 삭제
            if count >= 10:
                oldest = conn.execute("SELECT id FROM sessions ORDER BY created_at ASC LIMIT 1").fetchone()
                if oldest:
                    old_id = oldest[0]
                    conn.execute("DELETE FROM messages WHERE session_id=?", (old_id,))
                    conn.execute("DELETE FROM sessions WHERE id=?", (old_id,))
                    # 캐시에서도 제거
                    with cache._lock:
                        cache._sessions.pop(old_id, None)
            
            # 새 세션 생성
            sid = str(uuid.uuid4())[:8]
            now = time.time()
            conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?,?,?,?)",
                         (sid, "새 대화", now, now))
            conn.commit()
            conn.close()
            self._json({"id": sid, "title": "새 대화"})

        elif self.path.startswith('/api/sessions/') and self.path.endswith('/clear'):
            sid = self.path.split('/')[3]
            # 캐시 초기화
            sess = cache.get(sid)
            if sess:
                with cache._lock:
                    sess["messages"] = [{"role": "system", "content": "컨텍스트가 초기화되었습니다.", "sources": None, "ts": time.time()}]
                    sess["game"] = None
                    sess["last_query"] = ""
                    sess["dirty"] = True
            # DB도 즉시 정리
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
            # API 키 검증 (외부 API 호출용)
            if not self.check_api_key():
                return
            
            query = body.get("query", "")
            session_id = body.get("session_id")
            
            # 오타 감지 (자동 보정하지 않고 제안)
            fixed_query, typo_fixed = fix_typo(query, threshold=0.5)  # 한글 유사도 낮춤
            typo_suggestion = None
            if typo_fixed:
                print(f"[오타 감지] '{query}' (추천: '{fixed_query}')")
                typo_suggestion = fixed_query

            # 세션 없으면 자동 생성
            if not session_id:
                session_id = str(uuid.uuid4())[:8]

            # 캐시에 세션 확보 (없으면 DB에서 로드 시도)
            sess = cache.get(session_id)
            if not sess:
                sess = cache.load_from_db(session_id)
            if not sess:
                sess = cache.ensure(session_id, title=query[:30])

            # 유저 메시지를 캐시에 저장 (DB는 나중에 자동 flush)
            cache.add_message(session_id, "user", query)

            # 첫 메시지면 제목 업데이트
            user_msgs = [m for m in sess["messages"] if m["role"] == "user"]
            if len(user_msgs) == 1:
                sess["title"] = query[:30] + ("..." if len(query) > 30 else "")

            # 쿼리 정규화 (붙여쓰기 → 띄어쓰기 동의어)
            QUERY_SYNONYMS = {
                "엔더드래곤": "엔더 드래곤",
                "엔더진주": "엔더 진주",
                "엔더맨": "엔더맨",
                "위더스켈레톤": "위더 스켈레톤",
                "네더라이트": "네더라이트",
                "레드스톤": "레드스톤",
                "솔저76": "솔저: 76",
                "정크랫": "정크랫",
                # 동의어 확장 (검색 정확도 향상)
                "체력": "생명력",
                "공격력": "공격력",
                "피통": "생명력",
                "HP": "생명력",
                "hp": "생명력",
            }
            search_query = query
            for old, new in QUERY_SYNONYMS.items():
                if old in search_query and old != new:
                    search_query = search_query.replace(old, new)
            # 쿼리 리라이트 (불용어 제거 + 게임명 확장)
            search_query = rewrite_query(query, search_query)

            # 게임명 감지
            game_filter = None
            query_lower = query.lower()
            if any(kw in query_lower for kw in ["팰월드", "palworld", "팰"]):
                game_filter = "palworld"
            elif any(kw in query_lower for kw in ["오버워치", "overwatch", "옵치"]):
                game_filter = "overwatch"
            elif any(kw in query_lower for kw in ["마인크래프트", "마크", "minecraft"]):
                game_filter = "minecraft"

            # 게임 필터 없으면 캐시에서 이전 게임 컨텍스트 사용
            if not game_filter and sess.get("game"):
                game_filter = sess["game"]

            # 후속 질문이면 이전 질문을 검색 쿼리에 합침 (캐시에서)
            follow_up_markers = ["자세", "더", "그거", "그것", "알려", "뭐야", "어때"]
            if session_id and len(query) < 20 and any(m in query for m in follow_up_markers):
                if sess.get("last_query"):
                    search_query = sess["last_query"] + " " + search_query

            # ── DB 초기화 (lazy load) ──
            # 주의: vdb는 멀티스텝 블록 이전에 초기화해야 함 (스코프 버그 방지)
            # bm25_index / bm25_docs 도 get_db() 내부에서 global로 초기화됨
            vdb = get_db()

            # ── 멀티스텝 추론: 복합 질문 감지 (원본 query 사용) ──
            is_complex, query_type, subqueries = detect_complex_query(query)
            
            if is_complex and len(subqueries) >= 2:
                print(f"[멀티스텝] type={query_type}, subqueries={subqueries}", file=sys.stderr, flush=True)
                
                # 각 서브쿼리별 검색
                subquery_results = []
                for sq in subqueries[:3]:  # 최대 3개까지
                    sq_intent = classify_intent(sq)
                    sq_vec_w, sq_bm25_w = INTENT_WEIGHTS.get(sq_intent, (0.6, 0.4))

                    # 서브쿼리별 게임 필터: 원본 쿼리에서 엔티티 직전에 등장한 가장 가까운 게임명 탐색
                    # (다중 게임 쿼리 대응: "팰월드 람볼이랑 오버워치 리퍼" → 각각 분리)
                    q_lower = query.lower()
                    sq_pos = q_lower.find(sq.lower())
                    sq_game_filter = None
                    if sq_pos != -1:
                        before = q_lower[:sq_pos]  # 엔티티 이전 텍스트
                        _gmap = {
                            "palworld":   ["팰월드", "palworld"],
                            "overwatch":  ["오버워치", "overwatch", "옵치"],
                            "minecraft":  ["마인크래프트", "마크", "minecraft"],
                        }
                        best_pos, best_game = -1, None
                        for gname, kws in _gmap.items():
                            for kw in kws:
                                p = before.rfind(kw)  # 엔티티 앞에서 가장 가까운(오른쪽) 게임명
                                if p > best_pos:
                                    best_pos, best_game = p, gname
                        sq_game_filter = best_game
                    if not sq_game_filter:
                        sq_game_filter = game_filter  # 감지 실패 시 전체 쿼리 필터 사용

                    # 벡터 검색
                    sq_vec = vdb.similarity_search(sq, k=10)
                    if sq_game_filter:
                        sq_vec = [d for d in sq_vec if d.metadata.get("game", "") == sq_game_filter]

                    # BM25 검색
                    sq_tokens = tokenize_ko(sq)
                    sq_bm25_scores = bm25_index.get_scores(sq_tokens)
                    sq_bm25_idx = sorted(range(len(sq_bm25_scores)), key=lambda i: sq_bm25_scores[i], reverse=True)[:10]
                    sq_bm25_results = [bm25_docs[i] for i in sq_bm25_idx if sq_bm25_scores[i] > 0]
                    if sq_game_filter:
                        sq_bm25_results = [d for d in sq_bm25_results if d.metadata.get("game", "") == sq_game_filter]
                    
                    # RRF 통합
                    sq_scores = {}
                    for rank, doc in enumerate(sq_vec):
                        doc_id = doc.page_content[:100]
                        rrf = sq_vec_w / (RRF_K + rank + 1)
                        sq_scores[doc_id] = (sq_scores.get(doc_id, (0, doc))[0] + rrf, doc)
                    for rank, doc in enumerate(sq_bm25_results):
                        doc_id = doc.page_content[:100]
                        rrf = sq_bm25_w / (RRF_K + rank + 1)
                        sq_scores[doc_id] = (sq_scores.get(doc_id, (0, doc))[0] + rrf, doc)
                    
                    # 제목 부스트
                    for doc_id, (score, doc) in list(sq_scores.items()):
                        title = doc.metadata.get("title", "").lower()
                        title_clean = title.replace(" ", "").replace(":", "").replace("_", "").replace("/", "").replace("-", "")
                        sq_clean = sq.lower().replace(" ", "")
                        if sq_clean in title_clean or title_clean in sq_clean:
                            sq_scores[doc_id] = (score + 10.0, doc)
                    
                    sq_ranked = sorted(sq_scores.values(), key=lambda x: x[0], reverse=True)
                    sq_docs = [doc for _, doc in sq_ranked][:3]  # 서브쿼리당 3개
                    
                    # sources 수집
                    sq_sources = []
                    for doc in sq_docs:
                        game = doc.metadata.get("game", "")
                        title = doc.metadata.get("title", "")
                        src = f"{game}/{title}"
                        if src not in sq_sources:
                            sq_sources.append(src)
                    
                    subquery_results.append((sq, sq_docs, sq_sources))
                    print(f"  - {sq}: {len(sq_docs)}개 문서, sources={sq_sources}", file=sys.stderr, flush=True)
                
                # 결과 통합
                context, sources = merge_results(subquery_results, query_type)
                
                # 멀티스텝 프롬프트
                prompt = build_multi_step_prompt(query, context, query_type)
                
                payload = {
                    "prompt": prompt,
                    "n_predict": 300,  # 복합 질문이라 더 긴 답변
                    "temperature": 0.01,
                    "repeat_penalty": 1.2,
                    "top_p": 0.9,
                    "top_k": 30,
                    # 멀티스텝: "[" 제거 (LLM이 [리퍼], [겐지] 헤더로 답변 시작 허용)
                    # "\n\n\n" 사용 (비교 답변의 \n\n 단락 구분 허용)
                    "stop": ["\n\n\n", "질문:", "참고:", "---", "```", "根据", "抱歉", "Sorry"],
                }
                try:
                    resp = requests.post(LLAMA_URL, json=payload, timeout=90)
                    resp.raise_for_status()
                    result = resp.json()
                    answer = result.get("content", "").strip() or "응답을 생성할 수 없습니다."
                    answer = clean_answer(answer)
                    
                    # 멀티스텝 답변 검증
                    is_valid, confidence, issues = validate_answer(answer, query, sources)
                    print(f"🔍 [멀티스텝] 답변 검증: valid={is_valid}, confidence={confidence:.2f}, issues={issues}", file=sys.stderr, flush=True)
                    
                    if not is_valid and confidence < 0.3:
                        answer = f"⚠️ 답변 신뢰도가 낮습니다 ({int(confidence*100)}%).\n\n{answer}"
                except Exception as e:
                    answer = f"LLM 오류: {e}"
                
                # 캐시에 저장
                cache.add_message(session_id, "assistant", answer, sources=sources)
                if game_filter:
                    cache.set_game(session_id, game_filter)
                cache.set_last_query(session_id, query)
                
                self._json({"answer": answer, "sources": sources, "session_id": session_id})
                return
            
            # ── 의도 분류 ──
            intent = classify_intent(search_query)

            # ── 하이브리드 검색 + RRF (Reciprocal Rank Fusion) ──
            vec_results = vdb.similarity_search(search_query, k=20)
            # game_filter가 있으면 벡터 결과도 필터
            if game_filter:
                vec_filtered = [d for d in vec_results if d.metadata.get("game", "") == game_filter]
                if vec_filtered:
                    vec_results = vec_filtered
            query_tokens = tokenize_ko(search_query)
            bm25_scores = bm25_index.get_scores(query_tokens)
            top_bm25_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:20]
            bm25_results = [bm25_docs[i] for i in top_bm25_idx if bm25_scores[i] > 0]
            # game_filter가 있으면 BM25 결과도 필터
            if game_filter:
                bm25_results = [d for d in bm25_results if d.metadata.get("game", "") == game_filter]

            # 의도별 가중치 적용
            vec_w, bm25_w = INTENT_WEIGHTS.get(intent, (0.5, 0.5))

            # RRF 점수 계산
            doc_scores = {}  # doc_id → (score, doc)
            for rank, doc in enumerate(vec_results):
                doc_id = doc.page_content[:100]
                rrf = vec_w / (RRF_K + rank + 1)
                if doc_id in doc_scores:
                    doc_scores[doc_id] = (doc_scores[doc_id][0] + rrf, doc)
                else:
                    doc_scores[doc_id] = (rrf, doc)
            for rank, doc in enumerate(bm25_results):
                doc_id = doc.page_content[:100]
                rrf = bm25_w / (RRF_K + rank + 1)
                if doc_id in doc_scores:
                    doc_scores[doc_id] = (doc_scores[doc_id][0] + rrf, doc)
                else:
                    doc_scores[doc_id] = (rrf, doc)

            # 제목 매칭 부스트 (검색어가 제목에 포함되면 대폭 증가)
            for doc_id, (score, doc) in list(doc_scores.items()):
                title = doc.metadata.get("title", "").lower()
                # 공백/특수문자 제거 버전
                title_clean = title.replace(" ", "").replace(":", "").replace("_", "").replace("/", "").replace("-", "")
                query_clean = search_query.lower().replace(" ", "")
                
                # 키워드 분리
                query_words = [w for w in search_query.split() if len(w) > 1]
                
                # 정확 매칭: 최고 점수
                if query_clean in title_clean or title_clean in query_clean:
                    doc_scores[doc_id] = (score + 15.0, doc)  # 강력한 부스트 (10→15)
                # 다중 키워드 매칭 (2개 이상)
                elif sum(1 for word in query_words if word in title_clean) >= 2:
                    doc_scores[doc_id] = (score + 5.0, doc)  # 중간 부스트
                # 부분 매칭: 보너스
                elif any(word in title for word in query_words):
                    doc_scores[doc_id] = (score + 2.0, doc)  # 작은 부스트
            
            # ── 검색 품질 평가 + 재검색 ──
            ranked_initial = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)
            quality_score = calculate_search_quality(ranked_initial[:10], search_query, {k: v[0] for k, v in doc_scores.items()})
            print(f"📊 검색 품질: {quality_score:.3f}", file=sys.stderr, flush=True)
            
            # 품질이 낮으면 쿼리 확장 후 재검색
            if should_retry_search(quality_score, threshold=0.15):
                print(f"[재검색] 품질 낮음 ({quality_score:.3f}), 쿼리 확장", file=sys.stderr, flush=True)
                expanded_query = expand_query_for_retry(search_query)
                print(f"  확장: '{search_query}' → '{expanded_query}'", file=sys.stderr, flush=True)
                
                # 재검색
                retry_vec = vdb.similarity_search(expanded_query, k=20)
                if game_filter:
                    retry_vec = [d for d in retry_vec if d.metadata.get("game", "") == game_filter]
                retry_tokens = tokenize_ko(expanded_query)
                retry_bm25_scores = bm25_index.get_scores(retry_tokens)
                retry_bm25_idx = sorted(range(len(retry_bm25_scores)), key=lambda i: retry_bm25_scores[i], reverse=True)[:20]
                retry_bm25_results = [bm25_docs[i] for i in retry_bm25_idx if retry_bm25_scores[i] > 0]
                if game_filter:
                    retry_bm25_results = [d for d in retry_bm25_results if d.metadata.get("game", "") == game_filter]
                
                # 재검색 RRF
                retry_scores = {}
                for rank, doc in enumerate(retry_vec):
                    doc_id = doc.page_content[:100]
                    rrf = vec_w / (RRF_K + rank + 1)
                    retry_scores[doc_id] = (retry_scores.get(doc_id, (0, doc))[0] + rrf, doc)
                for rank, doc in enumerate(retry_bm25_results):
                    doc_id = doc.page_content[:100]
                    rrf = bm25_w / (RRF_K + rank + 1)
                    retry_scores[doc_id] = (retry_scores.get(doc_id, (0, doc))[0] + rrf, doc)
                
                # 재검색 품질 체크
                retry_ranked = sorted(retry_scores.values(), key=lambda x: x[0], reverse=True)
                retry_quality = calculate_search_quality(retry_ranked[:10], expanded_query, {k: v[0] for k, v in retry_scores.items()})
                print(f"  재검색 품질: {retry_quality:.3f}", file=sys.stderr, flush=True)
                
                # 재검색이 더 좋으면 교체
                if retry_quality > quality_score:
                    doc_scores = retry_scores
                    ranked_initial = retry_ranked
                    print(f"  ✅ 재검색 채택 (품질 향상: {quality_score:.3f} → {retry_quality:.3f})", file=sys.stderr, flush=True)
                else:
                    print(f"  ⏭️ 원본 유지 (재검색 효과 없음)", file=sys.stderr, flush=True)
            
            # ── 제목 부스트 + 문맥 부스트 ──
            for doc_id, (score, doc) in list(doc_scores.items()):
                # 제목 부스트
                title = doc.metadata.get("title", "").lower()
                title_clean = title.replace(" ", "").replace(":", "").replace("_", "").replace("/", "").replace("-", "")
                query_clean = search_query.lower().replace(" ", "")
                query_words = [w for w in search_query.split() if len(w) > 1]
                
                if query_clean in title_clean or title_clean in query_clean:
                    score += 15.0
                elif sum(1 for word in query_words if word in title_clean) >= 2:
                    score += 5.0
                elif any(word in title for word in query_words):
                    score += 2.0
                
                # 문맥 부스트
                score = contextual_boost(doc, search_query, score)
                
                doc_scores[doc_id] = (score, doc)
            
            # RRF + 부스트 점수 기준 정렬
            ranked = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)
            results = [doc for _, doc in ranked]
            print(f"🔍 intent={intent} vec_w={vec_w} bm25_w={bm25_w} | search_query='{search_query}' | top3: {[d.metadata.get('title','?')[:30] for d in results[:3]]}", file=sys.stderr, flush=True)

            # 의도별 chunk 수 조절 (컨텍스트 압축)
            # 너무 많은 문서를 넣으면 지연/품질 저하가 발생하므로 축소
            if intent == "stat":
                n_chunks = 3
            elif intent in ("howto", "list", "compare"):
                n_chunks = 4
            else:
                n_chunks = 4
            if game_filter:
                results = [d for d in results if d.metadata.get("game", "") == game_filter][:n_chunks]
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
                    cache.add_message(session_id, "assistant", ask_msg)
                    cache.set_last_query(session_id, query)
                    self._json({"answer": ask_msg, "sources": [], "ask_game": True, "games": game_list, "session_id": session_id})
                    return
                results = results[:n_chunks]

            context = ""
            sources = []
            for doc in results:
                game = doc.metadata.get("game", "")
                title = doc.metadata.get("title", "")
                chunk = doc.page_content[:450]  # 컨텍스트 압축 (속도/정확도 균형)
                context += f"\n[{title}]\n{chunk}\n"
                src = f"{game}/{title}"
                if src not in sources:
                    sources.append(src)
            ctx_preview = context.replace('\n', ' ')[:300]
            print(f"📄 context ({len(context)}자): {ctx_preview}", file=sys.stderr, flush=True)

            # 이전 대화 컨텍스트 (캐시에서, 현재 질문 제외)
            recent = cache.get_history(session_id, limit=5)
            history = ""
            for msg in recent[:-1]:  # 현재 질문 제외
                if msg["role"] == "user":
                    history += f"사용자: {msg['content']}\n"
                elif msg["role"] == "assistant":
                    history += f"답변: {msg['content']}\n"

            # LLM - 질문 형태 보정
            llm_query = query
            question_markers = ["?", "？", "뭐", "어떻게", "알려", "설명", "가르쳐", "어디", "언제", "누가", "왜"]
            if not any(m in query for m in question_markers):
                llm_query = f"{query}에 대해 알려줘"

            system = SYSTEM_PROMPT.format(context=context)
            if history:
                prompt = f"{system}\n\n[이전 대화]\n{history}\n질문: {llm_query}\n\n답변:"
            else:
                prompt = f"{system}\n\n질문: {llm_query}\n\n답변:"

            payload = {
                "prompt": prompt,
                "n_predict": 200,
                "temperature": 0.01,
                "repeat_penalty": 1.2,
                "top_p": 0.9,
                "top_k": 30,
                "stop": ["\n\n", "질문:", "참고:", "---", "```", "[", "根据", "抱歉", "Sorry"],
            }
            try:
                resp = requests.post(LLAMA_URL, json=payload, timeout=60)
                resp.raise_for_status()
                result = resp.json()
                answer = result.get("content", "").strip() or "응답을 생성할 수 없습니다."
                # 후처리: 중국어 제거, 반복 제거, 태그 제거
                answer = clean_answer(answer)
                
                # ── 답변 검증 ──
                is_valid, confidence, issues = validate_answer(answer, query, sources)
                print(f"🔍 답변 검증: valid={is_valid}, confidence={confidence:.2f}, issues={issues}", file=sys.stderr, flush=True)
                
                if not is_valid and confidence < 0.3:
                    # 신뢰도 매우 낮음 → 경고 추가
                    answer = f"⚠️ 답변 신뢰도가 낮습니다 ({int(confidence*100)}%).\n\n{answer}"
            except Exception as e:
                answer = f"LLM 오류: {e}"

            # 오타 제안 + 재검색 (검색 실패 시)
            needs_retry = False
            if typo_suggestion:
                if not sources or len(sources) == 0:
                    needs_retry = True
                elif "참고자료에" in answer and ("없습니다" in answer or "찾을 수 없습니다" in answer):
                    needs_retry = True
            
            if needs_retry:
                print(f"[오타 재검색] '{query}' → '{typo_suggestion}'", file=sys.stderr, flush=True)
                
                # 보정된 쿼리로 재검색
                retry_intent = classify_intent(typo_suggestion)
                retry_vec = vdb.similarity_search(typo_suggestion, k=15)
                retry_tokens = tokenize_ko(typo_suggestion)
                retry_bm25_scores = bm25_index.get_scores(retry_tokens)
                retry_bm25_idx = sorted(range(len(retry_bm25_scores)), key=lambda i: retry_bm25_scores[i], reverse=True)[:15]
                retry_bm25_results = [bm25_docs[i] for i in retry_bm25_idx if retry_bm25_scores[i] > 0]
                
                # 재검색 RRF
                retry_vec_w, retry_bm25_w = INTENT_WEIGHTS.get(retry_intent, (0.6, 0.4))
                retry_scores = {}
                for rank, doc in enumerate(retry_vec):
                    doc_id = doc.page_content[:100]
                    rrf = retry_vec_w / (RRF_K + rank + 1)
                    retry_scores[doc_id] = retry_scores.get(doc_id, (0, doc))[0] + rrf, doc
                for rank, doc in enumerate(retry_bm25_results):
                    doc_id = doc.page_content[:100]
                    rrf = retry_bm25_w / (RRF_K + rank + 1)
                    retry_scores[doc_id] = retry_scores.get(doc_id, (0, doc))[0] + rrf, doc
                
                retry_ranked = sorted(retry_scores.values(), key=lambda x: x[0], reverse=True)
                retry_results = [doc for _, doc in retry_ranked][:3]
                
                # 재검색 결과가 있으면
                if retry_results and len(retry_results) > 0:
                    retry_context = ""
                    retry_sources = []
                    for doc in retry_results:
                        game = doc.metadata.get("game", "")
                        title = doc.metadata.get("title", "")
                        chunk = doc.page_content[:350]
                        retry_context += f"\n[{title}]\n{chunk}\n"
                        src = f"{game}/{title}"
                        if src not in retry_sources:
                            retry_sources.append(src)
                    
                    # 재검색 LLM 질의
                    retry_system = SYSTEM_PROMPT.format(context=retry_context)
                    retry_llm_query = f"{typo_suggestion}에 대해 알려줘"
                    retry_prompt = f"{retry_system}\n\n질문: {retry_llm_query}\n\n답변:"
                    retry_payload = {
                        "prompt": retry_prompt,
                        "n_predict": 200,
                        "temperature": 0.01,
                        "repeat_penalty": 1.2,
                        "top_p": 0.9,
                        "top_k": 30,
                "stop": ["\n\n", "질문:", "참고:", "---", "```", "[", "根据", "抱歉", "Sorry"],
                    }
                    try:
                        retry_resp = requests.post(LLAMA_URL, json=retry_payload, timeout=60)
                        retry_resp.raise_for_status()
                        retry_result = retry_resp.json()
                        retry_answer = retry_result.get("content", "").strip() or "응답을 생성할 수 없습니다."
                        retry_answer = clean_answer(retry_answer)
                        print(f"[재검색 답변] '{retry_answer[:100]}'", file=sys.stderr, flush=True)
                        
                        # 재검색 성공 → 제안 메시지 + 재검색 결과
                        answer = f"🔍 혹시 '**{typo_suggestion}**'를 찾으시나요?\n\n{retry_answer}"
                        sources = retry_sources
                        print(f"[재검색 성공] sources: {retry_sources}", file=sys.stderr, flush=True)
                    except Exception as e:
                        print(f"[재검색 LLM 오류] {e}", file=sys.stderr, flush=True)
                        answer = f"🔍 혹시 '**{typo_suggestion}**'를 찾으시나요?\n\n" + answer
                else:
                    # 재검색도 실패
                    answer = f"🔍 혹시 '**{typo_suggestion}**'를 찾으시나요?\n\n" + answer
            
            # 봇 메시지를 캐시에 저장 + 게임/쿼리 컨텍스트 업데이트
            cache.add_message(session_id, "assistant", answer, sources=sources)
            if game_filter:
                cache.set_game(session_id, game_filter)
            # last_query는 의미있는 질문만 저장 (후속 질문이면 유지)
            if not (len(query) < 20 and any(m in query for m in follow_up_markers)):
                cache.set_last_query(session_id, query)

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
