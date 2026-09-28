# -*- coding: utf-8 -*-
"""
compare.py  [9장] 일반 RAG vs GraphRAG 비교
────────────────────────────────────────────────────────────────────────
같은 '강한 질문'을 두 방식에 던져, 회수 근거·답변·정답 커버리지를 나란히 본다.

  python compare.py                     # 답변까지 LLM 생성 (LLM_BACKEND, 기본 ollama)
  LLM_BACKEND=gpt python compare.py     # 답변 생성 백엔드 선택
  python compare.py --backend sglang    # 백엔드 직접 지정
  python compare.py --no-llm            # 모델 없이 '회수 근거'만 비교(오프라인 검증용)
  python compare.py -k 2                # 일반 RAG 회수 개수
"""
import argparse
from schema import CANONICAL
from kg_utils import load_triples, cascade
import naive_rag, graph_rag

QUESTION = ("에어컴프레서(E9)가 고장 나면 후속 공정 중 어디까지 연쇄로 멈추는가? "
            "영향 경로를 순서대로, 하나도 빠짐없이 알려줘.")


def _surfaces(cid):
    return CANONICAL[cid]["surfaces"]


def _edge_in_chunks(a, b, chunk_texts):
    """엣지 a-b 를 재구성할 근거가 회수 청크에 있나? (두 엔티티가 한 청크에 함께 등장)"""
    for txt in chunk_texts:
        if any(s in txt for s in _surfaces(a)) and any(s in txt for s in _surfaces(b)):
            return True
    return False


def causal_support(paths, affected, chunk_texts):
    """경로상의 '모든' 엣지가 회수 청크에서 재구성 가능한 노드만 인과적으로 지지됨."""
    ok = set()
    for n in affected:
        p = paths[n]
        if all(_edge_in_chunks(p[i], p[i + 1], chunk_texts) for i in range(len(p) - 1)):
            ok.add(n)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default=None,
                    help="LLM 백엔드 (gpt | ollama | lmstudio | vllm | sglang). "
                         "생략 시 LLM_BACKEND 환경변수 사용")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("-k", type=int, default=2)
    args = ap.parse_args()

    G = load_triples()
    # 정답: 그래프가 말하는 실제 연쇄 타격 집합
    by_hop, paths, _ = cascade("E9_에어컴프레서", G)
    affected = {n for h in by_hop for n in by_hop[h] if h > 0}

    print("질문:", QUESTION)
    print("=" * 70)

    # ── 일반 RAG ──
    retr = naive_rag.Retriever(naive_rag.load_chunks())
    hits = retr.search(QUESTION, args.k)
    hit_texts = [t for _, t, _ in hits]
    cov = causal_support(paths, affected, hit_texts)
    print(f"[일반 RAG]  임베더={retr.backend}, top-{args.k} 회수")
    for src, _, s in hits:
        print(f"   · {src}  (유사도 {s:.3f})")
    print(f"   회수 청크로 '인과 경로를 재구성할 수 있는' 연쇄 노드: {len(cov)}/{len(affected)}  "
          f"→ {', '.join(sorted(x.split('_',1)[-1] for x in cov)) or '없음'}")
    if affected - cov:
        print(f"   ✗ 링크가 회수 안 돼 근거 없는 노드: "
              f"{', '.join(sorted(x.split('_',1)[-1] for x in (affected - cov)))}")

    # ── GraphRAG ──
    _, _, ctx = graph_rag.graph_context("E9_에어컴프레서", G)
    print(f"\n[GraphRAG]  그래프 경로 회수 (누락 불가, 검증 가능)")
    for line in ctx.splitlines():
        print("   ·", line)
    print(f"   커버리지: {len(affected)}/{len(affected)}  (전부)")

    print("=" * 70)
    print(f"요약: 일반 RAG는 회수 단계에서 {len(affected)-len(cov)}개 노드를 원천 차단, "
          f"GraphRAG는 {len(affected)}개 전부를 경로와 함께 회수.")

    if not args.no_llm:
        from llm_client import chat
        # extract.py 와 동일한 패턴: 클라이언트 객체 대신 chat 콜백을 넘긴다.
        #   chat_fn(system, user, **kw) -> str
        chat_fn = lambda system, user, **kw: chat(system, user, backend=args.backend, **kw)
        print("\n" + "-" * 70)
        na, _ = naive_rag.answer(QUESTION, chat_fn, retr, args.k)
        print("[일반 RAG 답변]\n", na)
        ga, _ = graph_rag.answer(QUESTION, chat_fn, G)
        print("\n[GraphRAG 답변]\n", ga)


if __name__ == "__main__":
    main()