# -*- coding: utf-8 -*-
"""
chat_manual.py — 7.8 실습: 매뉴얼 챗봇
=========================================

ingest_manuals.py가 만든 벡터 DB를 로드해, 사용자의 질문에 매뉴얼 근거로 답변한다.
답변마다 참고한 매뉴얼 파일명과 페이지 번호를 함께 표시한다.

작동 순서:
    1) 사용자 질문 입력
    2) 벡터 DB에서 유사한 청크 상위 k개 검색
    3) 검색 결과를 프롬프트에 조합해 llm_client.chat() 호출
    4) 자연어 답변 + 참고 페이지 출력

사전 준비:
    먼저 python3 ingest_manuals.py 로 벡터 DB를 만들어둔다.

실행:
    python3 chat_manual.py                     # 대화형 실행
    python3 chat_manual.py --once "E-203?"     # 1회성 질의
    python3 chat_manual.py --k 5               # 검색 청크 수 조정
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

# 상위 폴더의 llm_client.py import
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat


BASE_DIR = Path(__file__).resolve().parent.parent
VECTOR_DB_DIR = BASE_DIR / "data" / "vector_db"


# ---------------------------------------------------------------------------
# 벡터 DB 로드
# ---------------------------------------------------------------------------
def load_vector_db(db_dir: Path):
    """저장된 FAISS 벡터 DB를 로드."""
    if not (db_dir / "index.faiss").exists():
        raise FileNotFoundError(
            f"벡터 DB 없음: {db_dir}\n"
            "먼저 python3 ingest_manuals.py 를 실행해라."
        )

    embeddings = OllamaEmbeddings(
        model="bge-m3",
        base_url="http://localhost:11434",
    )
    return FAISS.load_local(
        str(db_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


# ---------------------------------------------------------------------------
# 검색 결과 → 프롬프트 컨텍스트 조합
# ---------------------------------------------------------------------------
def build_context(docs: list) -> str:
    """검색된 청크들을 프롬프트용 컨텍스트 문자열로 변환."""
    parts = []
    for i, doc in enumerate(docs, 1):
        source = Path(doc.metadata.get("source", "?")).name
        page = doc.metadata.get("page", "?")
        parts.append(f"[문서 {i} — {source} p.{page}]\n{doc.page_content}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 질의 → 답변
# ---------------------------------------------------------------------------
def ask(question: str, vector_db, k: int = 3) -> tuple[str, list]:
    """질문에 대해 벡터 검색 + LLM 생성을 수행."""
    docs = vector_db.similarity_search(question, k=k)
    context = build_context(docs)

    system = (
        "당신은 공장 설비 매뉴얼 전문 상담 AI 다. "
        "아래 참고 문서를 근거로만 정확히 답한다. "
        "문서에 없는 내용은 절대 지어내지 말고 "
        "'매뉴얼에서 확인되지 않습니다' 라고 답한다."
    )
    user = f"참고 문서:\n{context}\n\n질문: {question}\n\n답변:"

    answer = chat(system, user, temperature=0.1, max_tokens=800)
    return answer, docs


def print_answer(answer: str, docs: list) -> None:
    print("\n[답변]")
    print(answer)
    print("\n[참고 페이지]")
    for doc in docs:
        source = Path(doc.metadata.get("source", "?")).name
        page = doc.metadata.get("page", "?")
        print(f"  - {source} p.{page}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", type=str, default=None, help="1회성 질의 실행")
    ap.add_argument("--k", type=int, default=3, help="검색할 청크 수")
    args = ap.parse_args()

    print("[벡터 DB 로드 중...]")
    vector_db = load_vector_db(VECTOR_DB_DIR)
    print("[준비 완료]\n")

    # 1회성 실행 모드
    if args.once:
        answer, docs = ask(args.once, vector_db, k=args.k)
        print(f"질문> {args.once}")
        print_answer(answer, docs)
        return

    # 대화형 모드
    print("=" * 60)
    print("공장 매뉴얼 챗봇")
    print("종료: exit / quit / 종료")
    print("=" * 60)

    while True:
        try:
            question = input("\n질문> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[종료]")
            break

        if question.lower() in ("exit", "quit", "종료"):
            print("[종료]")
            break

        if not question:
            continue

        try:
            answer, docs = ask(question, vector_db, k=args.k)
            print_answer(answer, docs)
        except Exception as e:
            print(f"[오류] {e}")


if __name__ == "__main__":
    main()
