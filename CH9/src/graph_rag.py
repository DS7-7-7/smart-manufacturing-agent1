# -*- coding: utf-8 -*-
"""
graph_rag.py  [9장] GraphRAG
────────────────────────────────────────────────────────────────────────
질문에서 설비를 찾아 → 지식그래프에서 고장 전파(캐스케이드)를 '걸어가' →
홉/경로를 근거로 답변. 회수 대상이 청크가 아니라 '그래프 경로'라는 점이 핵심.
"""
from schema import CANONICAL
from kg_utils import load_triples, cascade

GRAPH_SYS = ("너는 제조 라인 엔지니어다. 아래 '고장 전파 경로'(지식그래프 추론 결과)를 "
             "근거로 답하라. 경로에 등장하는 설비/공정을 하나도 빠뜨리지 말고, 홉 순서대로 설명하라.")


def link_equipment(question):
    """질문 문자열에서 설비 엔티티(표준 id) 찾기."""
    found = []
    for cid, meta in CANONICAL.items():
        if meta["type"] != "Equipment":
            continue
        if any(sf in question for sf in meta["surfaces"]):
            found.append(cid)
    return found


def graph_context(eq, G):
    """캐스케이드를 홉별 경로 텍스트로."""
    by_hop, paths, _ = cascade(eq, G)
    lines = []
    for h in sorted(by_hop):
        if h == 0:
            continue
        for n in by_hop[h]:
            lines.append(f"{h}홉: " + " → ".join(p.split('_', 1)[-1] for p in paths[n]))
    return by_hop, paths, "\n".join(lines)


def structured_answer(eq, G):
    """LLM 없이 그래프만으로 만드는 결정적 답변(누락 불가)."""
    by_hop, paths, ctx = graph_context(eq, G)
    hit = [n for h in by_hop for n in by_hop[h] if h > 0]
    head = f"{eq.split('_',1)[-1]} 고장 시 연쇄 타격 {len(hit)}건:"
    return head + "\n" + ctx, (by_hop, paths)


def answer(query, chat_fn, G):
    """chat_fn(system, user, **kw) -> str 콜백으로 답변 생성."""
    eqs = link_equipment(query)
    if not eqs:
        return "질문에서 설비를 찾지 못했습니다.", None
    eq = eqs[0]
    by_hop, paths, ctx = graph_context(eq, G)
    resp = chat_fn(GRAPH_SYS, f"고장 전파 경로:\n{ctx}\n\n질문: {query}")
    return resp, (by_hop, paths)


if __name__ == "__main__":
    G = load_triples()
    print(structured_answer("E9_에어컴프레서", G)[0])