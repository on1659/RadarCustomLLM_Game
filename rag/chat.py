"""나무위키 RAG 챗봇 — 로컬 llama-server 연동"""
import os
import requests
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")
LLAMA_URL = "http://localhost:8090/v1/chat/completions"

SYSTEM_PROMPT = """당신은 게임 전문가입니다. 아래 참고 자료를 기반으로 질문에 정확하게 답변하세요.
참고 자료에 없는 내용은 "해당 정보가 없습니다"라고 답하세요.
한국어로 답변하세요.

[참고 자료]
{context}"""


def load_db():
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")
    return FAISS.load_local(DB_DIR, embeddings, allow_dangerous_deserialization=True)


def search(db, query, k=5):
    results = db.similarity_search(query, k=k)
    context = ""
    for doc in results:
        game = doc.metadata.get("game", "?")
        title = doc.metadata.get("title", "?")
        context += f"\n[{game} - {title}]\n{doc.page_content}\n"
    return context, results


def ask_llm(query, context):
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
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"❌ LLM 연결 실패: {e}"


def main():
    print("🎮 게임 나무위키 RAG 챗봇")
    print("   팰월드 / 오버워치 / 마인크래프트")
    print("   종료: quit 또는 Ctrl+C\n")

    db = load_db()
    print("✅ 벡터DB 로드 완료!\n")

    while True:
        try:
            query = input("🎯 질문: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n👋 종료!")
            break

        if not query or query.lower() in ("quit", "exit", "q"):
            print("👋 종료!")
            break

        # 검색
        context, docs = search(db, query)
        print(f"  📚 {len(docs)}개 관련 문서 찾음")

        # LLM 답변
        answer = ask_llm(query, context)
        print(f"\n💬 {answer}\n")
        print("-" * 50)


if __name__ == "__main__":
    main()
