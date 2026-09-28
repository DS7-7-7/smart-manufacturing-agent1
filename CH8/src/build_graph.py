# -*- coding: utf-8 -*-
"""
build_graph.py  [8장]
────────────────────────────────────────────────────────────────────────
triples.json → 지식 그래프 구축 → ① 정적 PNG 시각화  ② Neo4j Cypher 익스포트

실행
  python build_graph.py                 # graph_full.png + factory.cypher 생성
  python build_graph.py --push \\
      --uri bolt://localhost:7687 --user neo4j --password <pw>   # 실 DB 적재(선택)
"""
import re
import argparse
import networkx as nx

from kg_utils import load_triples, build_impact_graph, TYPE_COLOR

# 관계별 엣지 색 (per-edge 텍스트 대신 색+범례로 가독성 확보)
REL_COLOR = {
    "PRECEDES":   "#3b6fb0",
    "RUNS_ON":    "#8a8a8a",
    "FEEDS":      "#e07b39",
    "DEPENDS_ON": "#d62728",   # 빨강 = 도미노의 숨은 링크
    "CONSUMES":   "#59a14f",
    "PRODUCES":   "#7b57c2",
}


# ── ① 정적 PNG ───────────────────────────────────────────────────────
def _set_korean_font() -> str:
    """한글 폰트를 등록하고 'family 이름'을 반환(라벨에도 넘겨 깨짐 방지)."""
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import font_manager, rcParams
    fam = "sans-serif"
    for path in [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    ]:
        try:
            font_manager.fontManager.addfont(path)
            fam = font_manager.FontProperties(fname=path).get_name()
            rcParams["font.family"] = fam
            break
        except Exception:
            continue
    rcParams["axes.unicode_minus"] = False
    return fam


def _line_layout(G):
    """조립 라인용 3단 레이아웃: 공정=바닥, 설비=중간, 부품=상단, 유틸리티=양옆."""
    from collections import defaultdict
    is_proc = lambda n: bool(re.match(r"P\d", n))
    is_equip = lambda n: bool(re.match(r"E\d", n))

    procs = sorted([n for n in G if is_proc(n)],
                   key=lambda n: int(re.search(r"P(\d+)", n).group(1)))
    pos = {p: (i * 2.0, 0.0) for i, p in enumerate(procs)}   # 공정 가로 간격 3.0→2.0

    runson = {u: v for u, v, d in G.edges(data=True) if d["rel"] == "RUNS_ON"}
    byproc = defaultdict(list)
    for e, p in runson.items():
        byproc[p].append(e)
    for p, es in byproc.items():
        px = pos[p][0]
        n = len(es)
        for j, e in enumerate(sorted(es)):
            pos[e] = (px + (j - (n - 1) / 2) * 1.1, 1.6)     # 설비: 간격1.6→1.1, 높이2.3→1.6

    xs = [pos[p][0] for p in procs] or [0]
    # 유틸리티(RUNS_ON 없는 설비): 여러 개여도 안 겹치게 세로로 쌓아 배치
    util = sorted([n for n in G if is_equip(n) and n not in runson])
    right_i, left_i = 0, 0
    for u in util:
        if "E10" in u:                      # 배기설비: 왼쪽
            pos[u] = (min(xs) - 1.6, 2.2 + left_i * 0.9)     # 더 안쪽으로
            left_i += 1
        else:                               # E9 등: 오른쪽에 세로로 쌓기
            pos[u] = (max(xs) + 1.8, 0.9 + right_i * 1.0)
            right_i += 1

    # 부품: 연결된 설비 위쪽에. 같은 설비에 여러 부품이면 좌우로 벌림
    part_by_base = defaultdict(list)
    parts = [n for n in G if not is_proc(n) and not is_equip(n)]
    for n in parts:
        nbrs = [m for m in set(G.predecessors(n)) | set(G.successors(n)) if m in pos]
        base = nbrs[0] if nbrs else None
        part_by_base[base].append(n)
    for base, ns in part_by_base.items():
        bx, by = pos[base] if base in pos else (0.0, 3.0)
        n = len(ns)
        for j, name in enumerate(sorted(ns)):
            pos[name] = (bx + (j - (n - 1) / 2) * 1.0, by + 1.4)  # 간격1.4→1.0, 높이2.0→1.4

    # ── 라벨 겹침 최종 방지: 너무 가까운 노드끼리 강제로 벌린다 ──
    MIN_DX, MIN_DY = 1.1, 0.7        # 최소거리 축소(1.6,0.9 → 1.1,0.7)
    nodes = list(pos.keys())
    for _ in range(300):
        moved = False
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                a, b = nodes[i], nodes[j]
                (ax, ay), (bx, by) = pos[a], pos[b]
                dx, dy = bx - ax, by - ay
                if abs(dx) < MIN_DX and abs(dy) < MIN_DY:
                    push = (MIN_DX - abs(dx)) / 2 + 0.03
                    sign = 1 if dx >= 0 else -1
                    pos[a] = (ax - sign * push, ay)
                    pos[b] = (bx + sign * push, by)
                    moved = True
        if not moved:
            break

    # ── 전체를 중앙(원점 기준)으로 모으고 살짝 압축 ──
    if pos:
        cx = sum(x for x, _ in pos.values()) / len(pos)
        cy = sum(y for _, y in pos.values()) / len(pos)
        SCALE = 0.6                 # 1.0=그대로, 작을수록 더 모임
        pos = {n: ((x - cx) * SCALE, (y - cy) * SCALE) for n, (x, y) in pos.items()}
    return pos


def draw_png(G, out="graph_full.png", highlight=None):
    """
    지식 그래프를 PNG로. highlight=[노드리스트]면 그 노드/경로를 강조(캐스케이드용).
    """
    fam = _set_korean_font()
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    simple = nx.DiGraph(G)
    pos = _line_layout(simple)
    fig, ax = plt.subplots(figsize=(16, 10))

    hl = set(highlight or [])
    node_colors = [G.nodes[n]["color"] for n in G.nodes()]
    node_sizes = [1700 if n in hl else 1100 for n in G.nodes()]
    edgecols = ["#000000" if n in hl else "none" for n in G.nodes()]
    nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes,
                           edgecolors=edgecols, linewidths=2.2, ax=ax)

    # 관계 타입별로 색을 달리해 엣지 그리기
    for rel, col in REL_COLOR.items():
        elist = [(u, v) for u, v, d in G.edges(data=True) if d["rel"] == rel]
        if not elist:
            continue
        nx.draw_networkx_edges(
            G, pos, edgelist=elist, edge_color=col, width=2.0,
            arrows=True, arrowsize=16, connectionstyle="arc3,rad=0.06",
            alpha=0.9, ax=ax)

    labels = {n: n.split("_", 1)[-1] if "_" in n else n for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=9, font_family=fam, ax=ax)

    type_legend = [Patch(facecolor=c, label=t) for t, c in TYPE_COLOR.items()]
    rel_legend = [Line2D([0], [0], color=c, lw=2.5, label=r) for r, c in REL_COLOR.items()]
    leg1 = ax.legend(handles=type_legend, title="노드(엔티티)", loc="upper left", fontsize=9)
    ax.add_artist(leg1)
    ax.legend(handles=rel_legend, title="엣지(관계)", loc="upper right", fontsize=9)

    ax.set_title("설비-부품 관계 지식 그래프  (자동차 조립 A라인)", fontsize=15, pad=14)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(out, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f"[PNG] 저장 → {out}")


# ── ② Neo4j Cypher 익스포트 ──────────────────────────────────────────
def _split_id(node_id):
    """'E9_에어컴프레서' → (code='E9', name='에어컴프레서'). 코드 없으면 code=None."""
    m = re.match(r"^([EP]\d+)_(.+)$", node_id)
    return (m.group(1), m.group(2)) if m else (None, node_id)


def export_cypher(G, out="factory.cypher"):
    """
    ontology 관계 + 유도된 IMPACTS(고장전파) 관계를 함께 심는 Cypher 생성.
    Neo4j 브라우저에 붙여넣으면 그래프 적재 + 도미노 조회까지 가능.
    """
    I = build_impact_graph(G)
    lines = ["// === 자동차 조립 A라인 지식 그래프 (auto-generated) ===",
             "// 초기화가 필요하면: MATCH (n) DETACH DELETE n;", ""]

    # 유니크 제약 (라벨별 id)
    for t in ("Process", "Equipment", "Part"):
        lines.append(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{t}) REQUIRE n.id IS UNIQUE;")
    lines.append("")

    # 노드
    lines.append("// --- 노드 ---")
    for n, d in G.nodes(data=True):
        code, name = _split_id(n)
        label = d["ntype"]
        props = f'id:"{n}", name:"{name}"' + (f', code:"{code}"' if code else "")
        lines.append(f"MERGE (:{label} {{{props}}});")
    lines.append("")

    # 온톨로지 관계
    lines.append("// --- 온톨로지 관계 ---")
    for u, v, d in G.edges(data=True):
        lines.append(
            f'MATCH (a {{id:"{u}"}}),(b {{id:"{v}"}}) MERGE (a)-[:{d["rel"]}]->(b);')
    lines.append("")

    # 유도된 고장전파 관계 (도미노 조회를 한 줄로 만들기 위함)
    lines.append("// --- 유도 관계 IMPACTS (고장 전파: u 고장 시 v 피해) ---")
    for u, v, d in I.edges(data=True):
        lines.append(
            f'MATCH (a {{id:"{u}"}}),(b {{id:"{v}"}}) '
            f'MERGE (a)-[:IMPACTS {{via:"{d["via"]}"}}]->(b);')
    lines.append("")

    # 예제 질의 (교재용)
    lines += [
        "// === 예제 질의 ===",
        "// 1) 전체 그래프 보기:",
        "//   MATCH (n)-[r]->(m) RETURN n,r,m;",
        "// 2) ★도미노★ 에어컴프레서(E9) 고장 시 연쇄 타격 전체:",
        "//   MATCH (s {code:'E9'})-[:IMPACTS*1..]->(hit) RETURN DISTINCT hit.id;",
        "// 3) 홉수까지 함께:",
        "//   MATCH p=(s {code:'E9'})-[:IMPACTS*1..]->(hit)",
        "//   RETURN hit.id, min(length(p)) AS hop ORDER BY hop;",
    ]
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Cypher] 저장 → {out}  (노드 {G.number_of_nodes()}, "
          f"온톨로지엣지 {G.number_of_edges()}, IMPACTS {I.number_of_edges()})")


def push_to_neo4j(G, uri=None, user=None, password=None, database=None):
    """실행 중인 Neo4j(Aura 포함)에 직접 적재. 인자 생략 시 환경변수 사용."""
    import os
    from neo4j import GraphDatabase

    uri      = uri      or os.environ["NEO4J_URI"]
    user     = user     or os.environ.get("NEO4J_USERNAME", "neo4j")
    password = password or os.environ["NEO4J_PASSWORD"]
    database = database or os.environ.get("NEO4J_DATABASE", "neo4j")

    export_cypher(G, "factory.cypher")
    stmts = [s.strip() for s in open("factory.cypher", encoding="utf-8").read().split(";")
             if s.strip() and not s.strip().startswith("//")]

    drv = GraphDatabase.driver(uri, auth=(user, password))
    with drv.session(database=database) as sess:   # Aura는 database 지정 권장
        for st in stmts:
            sess.run(st)
    drv.close()
    print(f"[Neo4j] {len(stmts)}개 문 적재 완료 → {uri}")


if __name__ == "__main__":
    import os
    ap = argparse.ArgumentParser()
    _HERE = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--triples", default=os.path.join(_HERE, "..", "triples.json"))
    ap.add_argument("--push", action="store_true", help=".env의 Neo4j로 적재")
    args = ap.parse_args()

    # .env 로드 (python-dotenv 사용)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # 미설치 시, 셸에서 export 한 환경변수를 그대로 사용

    G = load_triples(args.triples)
    draw_png(G)
    export_cypher(G)
    if args.push:
        push_to_neo4j(G)   # 접속정보는 .env에서 자동으로

