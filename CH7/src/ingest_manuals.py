# -*- coding: utf-8 -*-
"""
ingest_manuals.py — 7.7 실습: PDF 매뉴얼을 벡터 DB 에 적재
=============================================================

data/manuals/ 폴더의 PDF 파일들을 읽어 벡터 DB(FAISS)에 저장한다.
이후 chat_manual.py가 이 벡터 DB를 로드해 매뉴얼 챗봇을 실행한다.

파이프라인 4단계:
    1) PDF 로드      — pypdf가 페이지 단위로 텍스트 추출
    2) 청킹          — 500자 단위, 50자 오버랩
    3) 임베딩        — Ollama BGE-M3 (한국어 우수, 로컬 실행)
    4) FAISS 저장    — data/vector_db/ 폴더에 저장

사전 준비:
    ollama pull bge-m3
    data/manuals/ 폴더에 PDF 파일들을 넣는다

실행:
    python3 ingest_manuals.py
    python3 ingest_manuals.py --chunk-size 800    # 청크 크기 변경
"""

from __future__ import annotations

import argparse
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings


# 경로 설정 (팀 표준: CHx/data/ 아래)
BASE_DIR = Path(__file__).resolve().parent.parent
MANUALS_DIR = BASE_DIR / "data" / "manuals"
VECTOR_DB_DIR = BASE_DIR / "data" / "vector_db"


# ---------------------------------------------------------------------------
# 1단계: PDF 로드
# ---------------------------------------------------------------------------
def load_pdfs(manuals_dir: Path) -> list:
    """manuals 폴더의 모든 PDF를 페이지 단위로 로드."""
    if not manuals_dir.exists():
        raise FileNotFoundError(f"매뉴얼 폴더 없음: {manuals_dir}")

    loader = DirectoryLoader(
        str(manuals_dir),
        glob="**/*.pdf",
        loader_cls=PyPDFLoader,
    )
    documents = loader.load()

    if not documents:
        raise ValueError(
            f"PDF 파일이 없다. {manuals_dir} 폴더에 PDF를 넣어라."
        )
    return documents


# ---------------------------------------------------------------------------
# 2단계: 청킹
# ---------------------------------------------------------------------------
def split_documents(documents: list, chunk_size: int, chunk_overlap: int) -> list:
    """문서를 검색 단위(청크)로 분할."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
    )
    return splitter.split_documents(documents)


# ---------------------------------------------------------------------------
# 3단계 + 4단계: 임베딩 및 FAISS 저장
# ---------------------------------------------------------------------------
def build_and_save(chunks: list, save_dir: Path) -> None:
    """청크를 임베딩하여 FAISS에 저장."""
    embeddings = OllamaEmbeddings(
        model="bge-m3",
        base_url="http://localhost:11434",
    )

    vector_db = FAISS.from_documents(chunks, embeddings)

    save_dir.mkdir(parents=True, exist_ok=True)
    vector_db.save_local(str(save_dir))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunk-size", type=int, default=500, help="청크 최대 길이")
    ap.add_argument("--chunk-overlap", type=int, default=50, help="청크 간 오버랩")
    args = ap.parse_args()

    print(f"[매뉴얼 폴더] {MANUALS_DIR}")
    print(f"[저장 위치]  {VECTOR_DB_DIR}\n")

    print("[1/4] PDF 로드 중...")
    documents = load_pdfs(MANUALS_DIR)
    print(f"  → {len(documents)}개 페이지 로드")

    print(f"[2/4] 청킹 중... (size={args.chunk_size}, overlap={args.chunk_overlap})")
    chunks = split_documents(documents, args.chunk_size, args.chunk_overlap)
    print(f"  → {len(chunks)}개 청크 생성")

    print("[3/4] Ollama BGE-M3 임베딩 생성 중... (수 분 소요)")
    print("[4/4] FAISS 저장 중...")
    build_and_save(chunks, VECTOR_DB_DIR)

    print(f"\n[완료] {VECTOR_DB_DIR} 에 저장됨")
    print("다음: python3 chat_manual.py")


if __name__ == "__main__":
    main()
