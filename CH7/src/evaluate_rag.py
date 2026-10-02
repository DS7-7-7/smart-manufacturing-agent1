# -*- coding: utf-8 -*-
"""
evaluate_rag.py — 7장 실습(선택): RAG 검색 정확도 확인
========================================================

여러 개의 질문·정답 쌍을 만들어두고, 챗봇이 얼마나 잘 답하는지 자동으로 평가한다.
검색 단계의 품질(제대로 된 페이지를 가져오는지)과
답변 단계의 품질(가져온 문서에서 정확히 답하는지)을 함께 본다.

평가 방식:
    - 각 질문에 대해 벡터 DB 검색 → 상위 k개 청크
    - 정답 키워드가 검색된 청크에 포함되는지 확인 (retrieval hit)
    - 정답 키워드가 LLM 답변에 포함되는지 확인 (answer hit)
    - 최종 정확도(%) 출력

data/evaluations.json 형식 예시:
    [
      {
        "question": "에러코드 E-203 조치 방법은?",
        "keywords": ["냉각수", "압력"]
      },
      ...
    ]

실행:
    python3 evaluate_rag.py
    python3 evaluate_rag.py --k 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_ollama import OllamaEmbeddings

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat


BASE_DIR = Path(__file__).resolve().parent.parent
VECTOR_DB_DIR = BASE_DIR / "data" / "vector_db"
EVAL_FILE = BASE_DIR / "data" / "evaluations.json"


def load_eval_set(path: Path) -> list[dict]:
    """평가용 질문·키워드 셋 로드."""
    if not path.exists():
        # 예시 파일 자동 생성
        sample = [
            {
                "question": "에러코드 E-203 조치 방법은?",
                "keywords": ["냉각수", "압력"],
            },
            {
                "question": "방화복 착용 기준은?",
                "keywords": ["착용"],
            },
        ]
        path.write_text(
            json.dumps(sample, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[예시 생성] {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def keywords_in(text: str, keywords: list[str]) -> bool:
    """키워드 중 하나라도 포함되면 True."""
    return any(kw in text for kw in keywords)


def evaluate_one(question: str, keywords: list[str], vector_db, k: int) -> dict:
    """질문 1개에 대해 검색·답변 정확도를 평가."""
    docs = vector_db.similarity_search(question, k=k)
    retrieved_text = "\n".join(d.page_content for d in docs)
    retrieval_hit = keywords_in(retrieved_text, keywords)

    context = "\n\n".join(d.page_content for d in docs)
    system = (
        "당신은 공장 매뉴얼 상담 AI 다. 참고 문서만 근거로 답한다. "
        "없는 내용은 지어내지 않는다."
    )
    user = f"참고 문서:\n{context}\n\n질문: {question}\n\n답변:"
    answer = chat(system, user, temperature=0.1, max_tokens=400)
    answer_hit = keywords_in(answer, keywords)

    return {
        "question": question,
        "keywords": keywords,
        "retrieval_hit": retrieval_hit,
        "answer_hit": answer_hit,
        "answer": answer,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=3, help="검색할 청크 수")
    args = ap.parse_args()

    if not (VECTOR_DB_DIR / "index.faiss").exists():
        print(f"[오류] 벡터 DB 없음. 먼저 ingest_manuals.py 실행")
        sys.exit(1)

    print("[벡터 DB 로드 중...]")
    embeddings = OllamaEmbeddings(model="bge-m3", base_url="http://localhost:11434")
    vector_db = FAISS.load_local(
        str(VECTOR_DB_DIR), embeddings, allow_dangerous_deserialization=True
    )

    eval_set = load_eval_set(EVAL_FILE)
    print(f"[평가 시작] 총 {len(eval_set)}개 질문\n")

    print(f"{'질문':<40}{'검색':<8}{'답변':<8}")
    print("-" * 60)

    results = []
    for item in eval_set:
        r = evaluate_one(item["question"], item["keywords"], vector_db, args.k)
        results.append(r)
        ret_mark = "O" if r["retrieval_hit"] else "X"
        ans_mark = "O" if r["answer_hit"] else "X"
        print(f"{r['question'][:38]:<40}{ret_mark:<8}{ans_mark:<8}")

    print("-" * 60)
    total = len(results)
    ret_acc = sum(1 for r in results if r["retrieval_hit"]) / total
    ans_acc = sum(1 for r in results if r["answer_hit"]) / total
    print(f"검색 정확도: {ret_acc:.1%}")
    print(f"답변 정확도: {ans_acc:.1%}")


if __name__ == "__main__":
    main()
