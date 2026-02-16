"""나무위키 크롤링 데이터를 FAISS 벡터DB에 저장"""
import os
import glob
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "crawler", "data")
DB_DIR = os.path.join(os.path.dirname(__file__), "faiss_db")


def collect_files():
    files = []
    for root, dirs, filenames in os.walk(DATA_DIR):
        for f in filenames:
            if f.endswith(".txt") and not f.startswith("_"):
                filepath = os.path.join(root, f)
                if os.path.getsize(filepath) > 100:
                    files.append(filepath)
    return files


def main():
    print("📂 나무위키 데이터 수집 중...")
    files = collect_files()
    print(f"  → {len(files)}개 파일 발견")

    docs = []
    for f in files:
        try:
            loader = TextLoader(f, encoding="utf-8")
            file_docs = loader.load()
            # 메타데이터: 게임명 + 문서 제목
            rel = os.path.relpath(f, DATA_DIR)
            game = rel.split(os.sep)[0]
            title = os.path.splitext(os.path.basename(f))[0]
            for doc in file_docs:
                doc.metadata["game"] = game
                doc.metadata["title"] = title
                doc.metadata["source"] = rel
            docs.extend(file_docs)
        except Exception as e:
            print(f"  ⚠️ 스킵: {f} ({e})")

    print(f"  → {len(docs)}개 문서 로드")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " "]
    )
    chunks = splitter.split_documents(docs)
    print(f"  → {len(chunks)}개 청크로 분할")

    print("🧠 임베딩 생성 중... (첫 실행 시 모델 다운로드)")
    embeddings = HuggingFaceEmbeddings(model_name="jhgan/ko-sroberta-multitask")

    db = FAISS.from_documents(chunks, embeddings)
    db.save_local(DB_DIR)
    print(f"✅ FAISS DB 저장 완료! ({DB_DIR})")
    print(f"   총 {len(chunks)}개 청크 인덱싱")


if __name__ == "__main__":
    main()
