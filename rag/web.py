"""나무위키 RAG 웹 UI — localhost:3333"""
import os
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")
LLAMA_URL = "http://localhost:8090/v1/chat/completions"
PORT = 3333

SYSTEM_PROMPT = """당신은 게임 전문가입니다. 아래 참고 자료를 기반으로 질문에 정확하게 답변하세요.
참고 자료에 없는 내용은 "해당 정보가 없습니다"라고 답하세요.
한국어로 답변하세요.

[참고 자료]
{context}"""

HTML = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>🎮 게임위키 AI</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; background: #0a0a0a; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
  .header { padding: 16px 24px; background: #111; border-bottom: 1px solid #222; }
  .header h1 { font-size: 20px; }
  .header p { font-size: 13px; color: #888; margin-top: 4px; }
  .chat { flex: 1; overflow-y: auto; padding: 24px; }
  .msg { max-width: 700px; margin: 12px auto; padding: 14px 18px; border-radius: 12px; line-height: 1.6; }
  .user { background: #1a3a5c; margin-left: auto; max-width: 500px; text-align: right; }
  .bot { background: #1a1a2e; border: 1px solid #333; }
  .bot .sources { font-size: 12px; color: #666; margin-top: 8px; border-top: 1px solid #333; padding-top: 8px; }
  .input-area { padding: 16px 24px; background: #111; border-top: 1px solid #222; }
  .input-wrap { max-width: 700px; margin: 0 auto; display: flex; gap: 10px; }
  input { flex: 1; padding: 12px 16px; background: #1a1a1a; border: 1px solid #333; border-radius: 8px; color: #fff; font-size: 15px; outline: none; }
  input:focus { border-color: #4a90d9; }
  button { padding: 12px 24px; background: #4a90d9; color: #fff; border: none; border-radius: 8px; font-size: 15px; cursor: pointer; }
  button:hover { background: #3a7bc8; }
  button:disabled { background: #333; cursor: not-allowed; }
  .loading { color: #888; font-style: italic; }
</style>
</head><body>
<div class="header">
  <h1>🎮 게임위키 AI</h1>
  <p>팰월드 · 오버워치 · 마인크래프트 — 나무위키 기반 RAG</p>
</div>
<div class="chat" id="chat"></div>
<div class="input-area">
  <div class="input-wrap">
    <input id="input" placeholder="게임에 대해 물어보세요..." autofocus>
    <button id="btn" onclick="send()">전송</button>
  </div>
</div>
<script>
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const btn = document.getElementById('btn');

input.addEventListener('keydown', e => { if (e.key === 'Enter') send(); });

async function send() {
  const q = input.value.trim();
  if (!q) return;
  input.value = '';
  btn.disabled = true;
  
  chat.innerHTML += `<div class="msg user">${esc(q)}</div>`;
  chat.innerHTML += `<div class="msg bot loading" id="loading">🔍 검색 중...</div>`;
  chat.scrollTop = chat.scrollHeight;
  
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q})
    });
    const data = await r.json();
    document.getElementById('loading').remove();
    
    let html = esc(data.answer);
    if (data.sources && data.sources.length) {
      html += `<div class="sources">📚 참고: ${data.sources.map(s => esc(s)).join(', ')}</div>`;
    }
    chat.innerHTML += `<div class="msg bot">${html}</div>`;
  } catch(e) {
    document.getElementById('loading').remove();
    chat.innerHTML += `<div class="msg bot">❌ 오류: ${esc(e.message)}</div>`;
  }
  
  btn.disabled = false;
  chat.scrollTop = chat.scrollHeight;
  input.focus();
}

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>'); }
</script>
</body></html>"""


# 전역 DB
db = None

def get_db():
    global db
    if db is None:
        embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
        db = FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)
        print("✅ 벡터DB 로드 완료")
    return db


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path == "/api/chat":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            query = body.get("query", "")

            # 게임명 감지
            game_filter = None
            query_lower = query.lower()
            if any(kw in query_lower for kw in ["팰월드", "palworld", "팰"]):
                game_filter = "palworld"
            elif any(kw in query_lower for kw in ["오버워치", "overwatch", "옵치"]):
                game_filter = "overwatch"
            elif any(kw in query_lower for kw in ["마인크래프트", "마크", "minecraft"]):
                game_filter = "minecraft"

            # RAG 검색 (필터 있으면 더 많이 가져온 뒤 필터링)
            vdb = get_db()
            k_search = 15 if game_filter else 5
            results = vdb.similarity_search(query, k=k_search)
            
            if game_filter:
                results = [d for d in results if d.metadata.get("game", "") == game_filter][:5]
            else:
                results = results[:5]

            context = ""
            sources = []
            for doc in results:
                game = doc.metadata.get("game", "")
                title = doc.metadata.get("title", "")
                context += f"\n[{game} - {title}]\n{doc.page_content}\n"
                src = f"{game}/{title}"
                if src not in sources:
                    sources.append(src)

            # LLM
            system = SYSTEM_PROMPT.format(context=context)
            payload = {
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": query},
                ],
                "max_tokens": 1024,
                "temperature": 0.3,
                "repeat_penalty": 1.3,
            }
            try:
                resp = requests.post(LLAMA_URL, json=payload, timeout=60)
                answer = resp.json()["choices"][0]["message"]["content"]
            except Exception as e:
                answer = f"LLM 연결 실패: {e}"

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"answer": answer, "sources": sources}, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 로그 숨김


def main():
    print(f"🎮 게임위키 AI 서버 시작: http://localhost:{PORT}")
    get_db()  # 미리 로드
    HTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
