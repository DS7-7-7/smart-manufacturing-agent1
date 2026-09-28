# -*- coding: utf-8 -*-
"""
ground_truth.py
────────────────────────────────────────────────────────────────────────
사람이 손으로 확정한 '정답 그래프'.
용도 2가지:
  ① 추출 품질 채점: LLM이 뽑은 triples 를 정답과 비교(정밀도/재현율)
  ② 참조 트리플 생성: 모델이 없어도 8·9장을 돌려보게 triples.json 시드 제공
"""
from schema import CANONICAL, validate_triple

# 정답 트리플 (주어 id, 관계, 목적어 id) — 표준 id로 기술
TRIPLES = [
    # PRECEDES (공정 흐름)
    ("P1_프레스", "PRECEDES", "P2_차체용접"),
    ("P2_차체용접", "PRECEDES", "P3_도장"),
    ("P3_도장", "PRECEDES", "P4_의장조립"),
    ("P4_의장조립", "PRECEDES", "P5_최종검사"),
    # RUNS_ON (설비→공정)
    ("E1_프레스기", "RUNS_ON", "P1_프레스"),
    ("E2_용접로봇", "RUNS_ON", "P2_차체용접"),
    ("E5_컨베이어A", "RUNS_ON", "P2_차체용접"),
    ("E3_도장로봇", "RUNS_ON", "P3_도장"),
    ("E4_건조오븐", "RUNS_ON", "P3_도장"),
    ("E6_조립로봇", "RUNS_ON", "P4_의장조립"),
    ("E7_토크건", "RUNS_ON", "P4_의장조립"),
    ("E8_비전검사기", "RUNS_ON", "P5_최종검사"),
    # FEEDS (설비 간 공급)
    ("E1_프레스기", "FEEDS", "E2_용접로봇"),
    ("E2_용접로봇", "FEEDS", "E5_컨베이어A"),
    ("E5_컨베이어A", "FEEDS", "E3_도장로봇"),
    ("E3_도장로봇", "FEEDS", "E4_건조오븐"),
    ("E4_건조오븐", "FEEDS", "E6_조립로봇"),
    ("E6_조립로봇", "FEEDS", "E7_토크건"),
    ("E7_토크건", "FEEDS", "E8_비전검사기"),
    # DEPENDS_ON (유틸리티 의존) ★도미노의 숨은 링크
    ("E3_도장로봇", "DEPENDS_ON", "E9_에어컴프레서"),
    ("E7_토크건", "DEPENDS_ON", "E9_에어컴프레서"),
    ("E3_도장로봇", "DEPENDS_ON", "E10_배기설비"),
    # CONSUMES / PRODUCES
    ("E1_프레스기", "CONSUMES", "강판"),
    ("E3_도장로봇", "CONSUMES", "도료"),
    ("E7_토크건", "CONSUMES", "볼트너트"),
    ("E6_조립로봇", "CONSUMES", "엔진모듈"),
    ("E2_용접로봇", "PRODUCES", "차체BIW"),
]


def sanity_check():
    """정답 자체가 스키마를 지키는지 자가 점검."""
    for s, r, o in TRIPLES:
        assert s in CANONICAL, f"미등록 주어 {s}"
        assert o in CANONICAL, f"미등록 목적어 {o}"
        ok, why = validate_triple(s, r, o)
        assert ok, f"정답 위반: {(s,r,o)} → {why}"
    return True


def score(extracted: list[tuple]) -> dict:
    """추출 결과를 정답과 비교해 정밀도/재현율/F1 반환."""
    gt = set(TRIPLES)
    ex = set(tuple(t) for t in extracted)
    tp = len(ex & gt)
    precision = tp / len(ex) if ex else 0.0
    recall = tp / len(gt) if gt else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "정밀도": round(precision, 3),
        "재현율": round(recall, 3),
        "F1": round(f1, 3),
        "맞음": tp, "정답수": len(gt), "추출수": len(ex),
        "누락": sorted(gt - ex), "오탐": sorted(ex - gt),
    }


if __name__ == "__main__":
    sanity_check()
    print(f"정답 트리플 {len(TRIPLES)}개, 스키마 자가점검 통과 ✓")
