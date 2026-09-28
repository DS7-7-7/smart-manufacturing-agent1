# -*- coding: utf-8 -*-
"""
schema.py
────────────────────────────────────────────────────────────────────────
온톨로지 스키마 = "무엇을, 어떤 규칙으로 뽑을지"의 헌법.
두 곳에서 쓰인다.
  ① extract.py : 이 스키마를 LLM 프롬프트에 주입해 "이 안에서만 뽑아라"
  ② extract.py : 뽑힌 트리플을 domain/range 규칙으로 검증
"""
import re

# ── 엔티티 타입 ──────────────────────────────────────────────────────
ENTITY_TYPES = ["Process", "Equipment", "Part"]  # 공정 / 설비 / 부품·자재

# ── 관계 타입 : domain(주어) → range(목적어) 제약 + 고장 전파 방향 ───
#   propagate: "forward"  출발이 죽으면 도착이 피해 (엣지 방향대로)
#              "backward" 도착이 죽으면 출발이 피해 (엣지 뒤집어 전파) ★
#              None       구조적 관계일 뿐, 전파 안 함
RELATION_TYPES = {
    "PRECEDES":   {"domain": "Process",   "range": "Process",   "propagate": "forward",
                   "desc": "선행 공정 → 후속 공정"},
    "RUNS_ON":    {"domain": "Equipment", "range": "Process",   "propagate": "forward",
                   "desc": "설비가 해당 공정에서 가동됨"},
    "FEEDS":      {"domain": "Equipment", "range": "Equipment", "propagate": "forward",
                   "desc": "설비A가 설비B로 자재/반제품 공급"},
    "DEPENDS_ON": {"domain": "Equipment", "range": "Equipment", "propagate": "backward",
                   "desc": "설비가 유틸리티 설비에 의존 (전파는 역방향)"},
    "CONSUMES":   {"domain": "Equipment", "range": "Part",      "propagate": None,
                   "desc": "설비가 부품/자재를 소비"},
    "PRODUCES":   {"domain": "Equipment", "range": "Part",      "propagate": None,
                   "desc": "설비가 부품/반제품을 생산"},
}

# ── 표준 어휘(Controlled Vocabulary) ─────────────────────────────────
#   문서에는 같은 대상이 여러 표기로 등장한다(컴프레서=공기압축기=에어컴프레서).
#   'surfaces'(표면형)를 표준 id 하나로 모으는 게 엔티티 정규화의 근거.
CANONICAL = {
    # 공정
    "P1_프레스":   {"type": "Process", "surfaces": ["프레스 공정", "프레스공정", "P1"]},
    "P2_차체용접": {"type": "Process", "surfaces": ["차체 용접 공정", "차체용접 공정", "차체용접", "용접 공정", "P2"]},
    "P3_도장":     {"type": "Process", "surfaces": ["도장 공정", "도장공정", "P3"]},
    "P4_의장조립": {"type": "Process", "surfaces": ["의장 조립 공정", "의장조립 공정", "의장 조립", "의장조립", "P4"]},
    "P5_최종검사": {"type": "Process", "surfaces": ["최종 검사 공정", "최종검사 공정", "최종 검사", "최종검사", "검사 공정", "P5"]},
    # 설비
    "E1_프레스기":   {"type": "Equipment", "surfaces": ["프레스기", "E1"]},
    "E2_용접로봇":   {"type": "Equipment", "surfaces": ["용접로봇", "용접 로봇", "E2"]},
    "E3_도장로봇":   {"type": "Equipment", "surfaces": ["도장로봇", "도장 로봇", "E3"]},
    "E4_건조오븐":   {"type": "Equipment", "surfaces": ["건조오븐", "건조 오븐", "오븐", "E4"]},
    "E5_컨베이어A":  {"type": "Equipment", "surfaces": ["컨베이어A", "컨베이어 A", "컨베이어", "E5"]},
    "E6_조립로봇":   {"type": "Equipment", "surfaces": ["조립로봇", "조립 로봇", "E6"]},
    "E7_토크건":     {"type": "Equipment", "surfaces": ["토크건", "토크 건", "E7"]},
    "E8_비전검사기": {"type": "Equipment", "surfaces": ["비전검사기", "비전 검사기", "비전검사 장비", "E8"]},
    "E9_에어컴프레서": {"type": "Equipment", "surfaces": ["에어컴프레서", "에어 컴프레서", "컴프레서", "공기압축기", "E9"]},
    "E10_배기설비":  {"type": "Equipment", "surfaces": ["배기설비", "배기 설비", "환기설비", "E10"]},
    # 부품/자재
    "강판":     {"type": "Part", "surfaces": ["강판"]},
    "도료":     {"type": "Part", "surfaces": ["도료", "페인트"]},
    "볼트너트": {"type": "Part", "surfaces": ["볼트너트", "볼트/너트", "볼트", "너트"]},
    "엔진모듈": {"type": "Part", "surfaces": ["엔진모듈", "엔진 모듈", "엔진"]},
    "차체BIW":  {"type": "Part", "surfaces": ["차체BIW", "차체(BIW)", "BIW", "차체"]},
}

# 표면형 → 표준 id 역인덱스 (공백 제거·소문자화 키)
def _key(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()

SURFACE2ID = {}
CODE2ID = {}
for _id, _meta in CANONICAL.items():
    for _sf in _meta["surfaces"]:
        SURFACE2ID[_key(_sf)] = _id
        if re.fullmatch(r"[ep]\d+", _key(_sf)):   # E9, P4 같은 코드
            CODE2ID[_key(_sf)] = _id


def entity_type(node_id: str) -> str | None:
    """표준 id의 엔티티 타입. 미등록이면 id 접두사로 추정."""
    if node_id in CANONICAL:
        return CANONICAL[node_id]["type"]
    if re.match(r"E\d", node_id):
        return "Equipment"
    if re.match(r"P\d", node_id):
        return "Process"
    return "Part"


def normalize(surface: str) -> str | None:
    """
    LLM이 뱉은 표면형 문자열 → 표준 id.  (엔티티 정규화/Entity Resolution)
    1) 괄호 속/독립 코드(E9,P4)가 있으면 그걸로 해석  → '도장로봇(E3)' == 'E3'
    2) 없으면 표면형 사전 조회                        → '컴프레서' == '공기압축기'
    3) 그래도 모르면 None (미해결 → 검증에서 처리)
    """
    if not surface:
        return None
    s = surface.strip()
    m = re.search(r"[EePp]\d+", s)
    if m and _key(m.group()) in CODE2ID:
        return CODE2ID[_key(m.group())]
    # 괄호 제거 후 표면형 조회
    s2 = re.sub(r"\(.*?\)", "", s).strip()
    return SURFACE2ID.get(_key(s2)) or SURFACE2ID.get(_key(s))


def validate_triple(subj_id: str, rel: str, obj_id: str) -> tuple[bool, str]:
    """domain/range 규칙 위반 여부. (통과?, 사유)"""
    if rel not in RELATION_TYPES:
        return False, f"미정의 관계 '{rel}'"
    spec = RELATION_TYPES[rel]
    st, ot = entity_type(subj_id), entity_type(obj_id)
    if st != spec["domain"]:
        return False, f"{rel} 주어는 {spec['domain']}여야 하는데 {subj_id}={st}"
    if ot != spec["range"]:
        return False, f"{rel} 목적어는 {spec['range']}여야 하는데 {obj_id}={ot}"
    return True, "ok"


def schema_prompt_block() -> str:
    """LLM 프롬프트에 넣을 스키마 설명(관계 + 제약)."""
    lines = ["다음 관계 타입만 사용하라. 각 관계의 (주어타입 → 목적어타입) 제약을 반드시 지켜라:"]
    for rel, spec in RELATION_TYPES.items():
        lines.append(f"- {rel}: {spec['domain']} → {spec['range']}  ({spec['desc']})")
    return "\n".join(lines)


if __name__ == "__main__":
    print(schema_prompt_block())
    print()
    for s in ["컴프레서", "공기압축기", "도장로봇(E3)", "E9", "의장 조립 공정", "없는것"]:
        print(f"  normalize('{s}') = {normalize(s)}")
    print("  검증:", validate_triple("E7_토크건", "DEPENDS_ON", "E9_에어컴프레서"))
    print("  검증:", validate_triple("P1_프레스", "DEPENDS_ON", "E9_에어컴프레서"))
