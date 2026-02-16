"""나무위키 RAG 웹 UI — localhost:3333 (하이브리드 검색: BM25 + 벡터)"""
import os
import json
import re
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from rank_bm25 import BM25Okapi

DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")
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
}

function sendWithGame(game, originalQ) {
  input.value = game + ' ' + originalQ;
  send();
}

function esc(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>'); }
</script>
</body></html>"""


# 전역 DB + BM25
db = None
bm25_index = None
bm25_docs = None

def tokenize_ko(text):
    """간단한 한국어 토크나이저 (공백 + 2글자 이상)"""
    tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if len(t) >= 2]

def get_db():
    global db, bm25_index, bm25_docs
    if db is None:
        embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
        db = FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)
        print("✅ 벡터DB 로드 완료")
        
        # BM25 인덱스 구축
        all_docs = db.docstore._dict.values()
        bm25_docs = list(all_docs)
        corpus = [tokenize_ko(doc.page_content) for doc in bm25_docs]
        bm25_index = BM25Okapi(corpus)
        print(f"✅ BM25 인덱스 구축 완료 ({len(bm25_docs)}개 문서)")
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

            # 하이브리드 검색: 벡터 유사도 + BM25 키워드 매칭
            vdb = get_db()
            
            # 1) 벡터 검색
            vec_results = vdb.similarity_search(query, k=8)
            
            # 2) BM25 키워드 검색
            query_tokens = tokenize_ko(query)
            bm25_scores = bm25_index.get_scores(query_tokens)
            top_bm25_idx = sorted(range(len(bm25_scores)), key=lambda i: bm25_scores[i], reverse=True)[:8]
            bm25_results = [bm25_docs[i] for i in top_bm25_idx if bm25_scores[i] > 0]
            
            # 3) 합치기 (중복 제거, 벡터 우선 + BM25 보충)
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
                # 게임 필터 없을 때: 여러 게임이 섞여있으면 역질문
                found_games = set()
                for doc in results:
                    g = doc.metadata.get("game", "")
                    if g:
                        found_games.add(g)
                
                if len(found_games) >= 2:
                    # 역질문 반환
                    game_names = {
                        "palworld": "팰월드",
                        "overwatch": "오버워치",
                        "minecraft": "마인크래프트",
                    }
                    game_list = [game_names.get(g, g) for g in sorted(found_games)]
                    ask_msg = f"'{query}'은(는) 여러 게임에 존재합니다. 어떤 게임에 대해 알고 싶으신가요?"
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "answer": ask_msg,
                        "sources": [],
                        "ask_game": True,
                        "games": game_list,
                    }, ensure_ascii=False).encode())
                    return
                
                results = results[:5]

            context = ""
            sources = []
            max_chunk_len = 800  # 청크당 최대 800자
            for doc in results:
                game = doc.metadata.get("game", "")
                title = doc.metadata.get("title", "")
                chunk = doc.page_content[:max_chunk_len]
                context += f"\n[{game} - {title}]\n{chunk}\n"
                src = f"{game}/{title}"
                if src not in sources:
                    sources.append(src)

            # LLM
            system = SYSTEM_PROMPT.format(context=context)
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
                if "content" in result:
                    answer = result["content"].strip()
                else:
                    answer = f"LLM 응답 형식 오류: {list(result.keys())}"
            except requests.exceptions.RequestException as e:
                answer = f"LLM 연결 실패: {e}"
            except (KeyError, ValueError) as e:
                answer = f"LLM 응답 파싱 실패: {e}"
            except Exception as e:
                answer = f"예상치 못한 오류: {e}"

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
