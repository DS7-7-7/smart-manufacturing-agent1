# -*- coding: utf-8 -*-
"""
extract.py
────────────────────────────────────────────────────────────────────────
문서(corpus/*.md) → LLM 관계 추출 → 정규화 → 스키마 검증 → triples.json

파이프라인 (교재 6단계)
  1) 로드/청킹  : 문서를 읽어 조각으로. doc3(유틸리티)만 문장 단위(의존관계 누락 방지)
  2) LLM 추출   : 조각별로 스키마를 주입해 (주어,관계,목적어) 표면형 트리플 요청
  3) 엔티티 정규화: 표면형 → 표준 id (컴프레서=공기압축기=E9)
  4) 스키마 검증 : domain/range 위반·미해결·중복 제거
  5) 채점       : 정답(ground_truth)과 비교해 정밀도/재현율
  6) 저장       : triples.json

실행
  python extract.py                    # LLM_BACKEND(기본 ollama)로 실제 추출
  LLM_BACKEND=gpt python extract.py    # GPT API 로 추출
  python extract.py --backend sglang   # 백엔드 직접 지정
  python extract.py --mock             # 모델 없이 내장 가짜 클라이언트로 전 과정 시연
"""
import os
import re
import glob
import json
import argparse

from schema import (schema_prompt_block, normalize, validate_triple)
from ground_truth import score

_HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(_HERE, "..", "corpus")       # CH8/corpus
OUT_PATH = os.path.join(_HERE, "..", "triples.json")   # CH8/triples.json

# doc3만 문장 단위. 나머지는 통짜.
def chunk_strategy(filename: str) -> str:
    return "sentence" if "유틸리티" in filename else "whole"


def split_sentences(text: str) -> list[str]:
    # '~다.' 종결 + 줄바꿈 기준의 가벼운 문장 분리
    parts = re.split(r"(?<=다\.)\s+|\n{2,}", text)
    return [p.strip() for p in parts if p.strip()]


def load_chunks(corpus_dir: str = CORPUS_DIR):
    chunks = []  # (source, text)
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.md"))):
        fname = os.path.basename(path)
        text = open(path, encoding="utf-8").read()
        if chunk_strategy(fname) == "sentence":
            for i, sent in enumerate(split_sentences(text)):
                chunks.append((f"{fname}#s{i}", sent))
        else:
            chunks.append((fname, text))
    return chunks


# ── LLM 추출 프롬프트 ────────────────────────────────────────────────
SYSTEM_PROMPT = f"""너는 제조 라인 문서에서 지식그래프 트리플을 뽑는 정보추출기다.
아래 스키마 안에서만 관계를 추출하라.

{schema_prompt_block()}

규칙:
- 문장에 명시되었거나 명백히 함의된 관계만 추출한다(추측 금지).
- 엔티티는 문서에 나온 표기 그대로 쓰되, 코드가 있으면 함께 적어라(예: "도장로봇(E3)").
- 반드시 아래 JSON 형식으로만 답하라. 설명 문장 금지.

{{"triples": [{{"subject": "...", "relation": "...", "object": "..."}}]}}"""


def extract_chunk(extract_fn, text: str) -> list[dict]:
    """extract_fn(system, user) -> dict 를 호출해 트리플 리스트를 얻는다."""
    user = f"다음 문서 조각에서 트리플을 추출하라:\n---\n{text}\n---"
    data = extract_fn(SYSTEM_PROMPT, user)
    return data.get("triples", []) if isinstance(data, dict) else []


# ── 파이프라인 본체 ──────────────────────────────────────────────────
def run(extract_fn, corpus_dir: str = CORPUS_DIR, out_path: str = OUT_PATH, verbose=True):
    chunks = load_chunks(corpus_dir)
    raw = []                 # (source, subj_surface, rel, obj_surface)
    for src, text in chunks:
        for t in extract_chunk(extract_fn, text):
            raw.append((src, t.get("subject"), t.get("relation"), t.get("object")))

    kept, dropped, unresolved = [], [], []
    for src, ss, rel, os_ in raw:
        si, oi = normalize(ss or ""), normalize(os_ or "")
        if si is None or oi is None:
            unresolved.append((src, ss, rel, os_))
            continue
        ok, why = validate_triple(si, rel, oi)
        if not ok:
            dropped.append((src, (si, rel, oi), why))
            continue
        kept.append((si, rel, oi))

    # 중복 제거(순서 보존)
    seen, triples = set(), []
    for t in kept:
        if t not in seen:
            seen.add(t); triples.append(list(t))

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(triples, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"[1] 청크 {len(chunks)}개 → [2] 원시 트리플 {len(raw)}개")
        print(f"[3-4] 정규화·검증 후 {len(triples)}개  "
              f"(미해결 {len(unresolved)}, 규칙위반 {len(dropped)}, 중복 {len(kept)-len(triples)})")
        if dropped:
            print("    · 규칙위반으로 버린 예:")
            for src, t, why in dropped[:3]:
                print(f"        {t}  ← {why}  [{src}]")
        if unresolved:
            print("    · 정규화 실패(표면형 미등록) 예:")
            for src, ss, rel, os_ in unresolved[:3]:
                print(f"        ({ss} -{rel}- {os_})  [{src}]")
        rep = score(triples)
        print(f"[5] 채점  정밀도 {rep['정밀도']} · 재현율 {rep['재현율']} · F1 {rep['F1']} "
              f"(정답 {rep['정답수']}개 중 {rep['맞음']}개 일치)")
        if rep["누락"]:
            print("    · 정답 대비 누락:", ", ".join(f"{s}-{r}->{o}" for s, r, o in rep["누락"][:5]))
        print(f"[6] 저장 → {out_path}")
    return triples


# ── 모델 없이 시연하기 위한 가짜 클라이언트 ─────────────────────────
class MockClient:
    """실제 LLM 대신, 문서 조각의 키워드를 보고 '지저분한 표면형' 트리플을 반환.
    - 동의어(컴프레서/공기압축기)로 정규화 단계를 자극
    - 일부러 틀린 트리플 1개로 검증 단계를 자극
    extract_json(system, user) 시그니처는 llm_client.extract_json 과 동일하게 맞춘다."""
    def extract_json(self, system, user):
        c = user
        T = lambda s, r, o: {"subject": s, "relation": r, "object": o}
        out = []
        if "5개 공정" in c or "공정 흐름" in c:  # doc1
            out += [T("프레스 공정", "PRECEDES", "차체 용접 공정"),
                    T("차체 용접 공정", "PRECEDES", "도장 공정"),
                    T("도장 공정", "PRECEDES", "의장 조립 공정"),
                    T("의장 조립 공정", "PRECEDES", "최종 검사 공정"),
                    T("프레스기(E1)", "RUNS_ON", "프레스 공정"),
                    T("용접로봇(E2)", "RUNS_ON", "차체 용접 공정"),
                    T("컨베이어A(E5)", "RUNS_ON", "차체 용접 공정"),
                    T("도장로봇(E3)", "RUNS_ON", "도장 공정"),
                    T("건조오븐(E4)", "RUNS_ON", "도장 공정"),
                    T("조립로봇(E6)", "RUNS_ON", "의장 조립 공정"),
                    T("토크건(E7)", "RUNS_ON", "의장 조립 공정"),
                    T("비전검사기(E8)", "RUNS_ON", "최종 검사 공정")]
        if "사양" in c or "소재로 소비" in c:   # doc2
            out += [T("프레스기(E1)", "FEEDS", "용접로봇(E2)"),
                    T("용접로봇(E2)", "FEEDS", "컨베이어A(E5)"),
                    T("컨베이어A(E5)", "FEEDS", "도장로봇(E3)"),
                    T("도장로봇(E3)", "FEEDS", "건조오븐(E4)"),
                    T("건조오븐(E4)", "FEEDS", "조립로봇(E6)"),
                    T("조립로봇(E6)", "FEEDS", "토크건(E7)"),
                    T("토크건(E7)", "FEEDS", "비전검사기(E8)"),
                    T("프레스기", "CONSUMES", "강판"),
                    T("도장로봇", "CONSUMES", "도료"),
                    T("토크건", "CONSUMES", "볼트너트"),
                    T("조립로봇", "CONSUMES", "엔진모듈"),
                    T("용접로봇", "PRODUCES", "차체(BIW)")]
        if "압축공기" in c or "컴프레서" in c:   # doc3 문장(공압)
            out += [T("도장로봇(E3)", "DEPENDS_ON", "컴프레서"),        # 동의어
                    T("토크건", "DEPENDS_ON", "공기압축기"),            # 동의어
                    T("도장 공정", "DEPENDS_ON", "컴프레서")]           # ★일부러 틀림(공정→)
        if "배기설비" in c or "환기" in c:        # doc3 문장(환기)
            out += [T("도장로봇(E3)", "DEPENDS_ON", "배기설비(E10)")]
        if "고장" in c or "정비" in c:           # doc4 (중복 유발)
            out += [T("토크건(E7)", "DEPENDS_ON", "에어컴프레서(E9)")]  # doc3와 중복
        return {"triples": out}


def get_extractor(mock: bool, backend: str | None = None):
    """추출 함수 extract_fn(system, user) -> dict 를 돌려준다.
    - mock=True  : 내장 MockClient
    - mock=False : llm_client.chat 기반 실제 추출 (LLM_BACKEND / --backend)
    """
    if mock:
        return MockClient().extract_json
    from llm_client import extract_json
    return lambda system, user: extract_json(system, user, backend=backend)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="모델 없이 가짜 클라이언트로 시연")
    ap.add_argument("--backend", default=None,
                    help="LLM 백엔드 (gpt | ollama | lmstudio | vllm | sglang). "
                         "생략 시 LLM_BACKEND 환경변수 사용")
    args = ap.parse_args()
    run(get_extractor(args.mock, args.backend))