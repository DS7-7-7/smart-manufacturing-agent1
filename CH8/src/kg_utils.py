# -*- coding: utf-8 -*-
"""
kg_utils.py
────────────────────────────────────────────────────────────────────────
트리플(triples.json) 위에서 도는 공용 도구. 8장(시각화)·9장(GraphRAG) 공유.
  - load_triples() : json → NetworkX 방향그래프(노드에 타입/색 부여)
  - build_impact_graph() : 스키마의 전파규칙으로 '고장 전파 그래프' 유도
  - cascade() : 특정 설비 고장 시 홉별 연쇄 타격 + 경로
"""
import json
import networkx as nx
from schema import RELATION_TYPES, entity_type

TYPE_COLOR = {"Process": "#4C72B0", "Equipment": "#DD8452", "Part": "#55A868"}


def load_triples(path: str = "triples.json") -> nx.MultiDiGraph:
    with open(path, encoding="utf-8") as f:
        triples = json.load(f)
    G = nx.MultiDiGraph()
    for s, r, o in triples:
        for n in (s, o):
            if n not in G:
                t = entity_type(n)
                G.add_node(n, ntype=t, color=TYPE_COLOR.get(t, "#999999"))
        G.add_edge(s, o, rel=r)
    return G


def build_impact_graph(G: nx.MultiDiGraph) -> nx.DiGraph:
    """지식 그래프 → 고장 전파 그래프. u→v = 'u 고장 시 v 피해'."""
    I = nx.DiGraph()
    I.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        rule = RELATION_TYPES.get(data["rel"], {}).get("propagate")
        if rule == "forward":
            I.add_edge(u, v, via=data["rel"])
        elif rule == "backward":
            I.add_edge(v, u, via=data["rel"])
    return I


def cascade(node_id: str, G: nx.MultiDiGraph):
    """설비 고장 시 홉별 타격 노드 {hop:[...]}, 최단경로 dict, 전파그래프 반환."""
    I = build_impact_graph(G)
    if node_id not in I:
        raise KeyError(f"'{node_id}' 없음")
    hop = {node_id: 0}
    queue = [node_id]
    while queue:
        cur = queue.pop(0)
        for nxt in I.successors(cur):
            if nxt not in hop:
                hop[nxt] = hop[cur] + 1
                queue.append(nxt)
    by_hop = {}
    for n, h in hop.items():
        by_hop.setdefault(h, []).append(n)
    paths = {n: nx.shortest_path(I, node_id, n) for n in hop if n != node_id}
    return by_hop, paths, I


if __name__ == "__main__":
    import sys
    G = load_triples(sys.argv[1] if len(sys.argv) > 1 else "triples.json")
    print(f"그래프: 노드 {G.number_of_nodes()}, 엣지 {G.number_of_edges()}")
    by_hop, _, _ = cascade("E9_에어컴프레서", G)
    for h in sorted(by_hop):
        if h:
            print(f"  {h}홉: {', '.join(by_hop[h])}")
