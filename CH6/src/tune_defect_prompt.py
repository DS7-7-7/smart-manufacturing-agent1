# -*- coding: utf-8 -*-
"""
tune_defect_prompt.py — 6.9 실습: 결함 보고서 프롬프트 튜닝
===============================================================

같은 결함 보고서 원본을 3가지 프롬프트로 처리하며,
최종적으로 파이썬에서 파싱 가능한 JSON 형식까지 개선한다.

    Step 1: 단순 요약 요청
    Step 2: 구조화 요청 (항목별 정리)
    Step 3: JSON 형식 요청 (as_json=True) → 파이썬에서 활용

실행:
    python3 tune_defect_prompt.py
    python3 tune_defect_prompt.py --step 3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "defect_report.txt"


def load_report() -> str:
    return DATA_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# STEP 1: 단순 요약
# ---------------------------------------------------------------------------
def step1_summarize(report: str) -> None:
    print("=" * 60)
    print("[STEP 1] 단순 요약 요청")
    print("=" * 60)

    system = "너는 유용한 조수다."
    user = f"다음 결함 보고서를 요약해줘:\n{report}"

    answer = chat(system, user, temperature=0.2, max_tokens=400)
    print(f"[답변]\n{answer}\n")


# ---------------------------------------------------------------------------
# STEP 2: 구조화
# ---------------------------------------------------------------------------
def step2_structured(report: str) -> None:
    print("=" * 60)
    print("[STEP 2] 구조화 요청 (항목별 정리)")
    print("=" * 60)

    system = "너는 제조 품질 담당자다. 결함 보고서를 항목별로 정리한다."
    user = f"""다음 결함 보고서를 아래 항목으로 정리해줘.
- 발생 시각:
- 제품 정보:
- 결함 상세:
- 추정 원인:
- 필요 조치:

원본:
{report}"""

    answer = chat(system, user, temperature=0.2, max_tokens=600)
    print(f"[답변]\n{answer}\n")


# ---------------------------------------------------------------------------
# STEP 3: JSON 형식 요청 + 파이썬 활용
# ---------------------------------------------------------------------------
def step3_json(report: str) -> None:
    print("=" * 60)
    print("[STEP 3] JSON 형식 요청 + 파이썬 파싱")
    print("=" * 60)

    system = """너는 제조 품질 데이터 담당자다.
결함 보고서를 아래 JSON 스키마로 변환한다. JSON 만 반환하고 다른 설명은 넣지 않는다.

{
  "timestamp": "발생 시각",
  "lot_id": "LOT 번호",
  "product": "제품 코드",
  "defect_summary": "결함 요약",
  "possible_causes": ["원인1", "원인2"],
  "required_actions": ["조치1", "조치2"],
  "severity": "HIGH | MEDIUM | LOW"
}"""

    user = f"원본:\n{report}"

    # as_json=True 로 호출 → llm_client가 JSON 파싱까지 처리해 dict 반환
    data = chat(system, user, as_json=True, temperature=0.1, max_tokens=600)

    print(f"[파싱 결과 타입] {type(data).__name__}")
    print(f"[파싱 결과]\n{json.dumps(data, ensure_ascii=False, indent=2)}\n")

    # 파이썬에서 곧바로 활용
    if isinstance(data, dict) and data:
        print("=" * 40)
        print("[파이썬에서 활용 예시]")
        print("=" * 40)
        print(f"제품 코드: {data.get('product', 'N/A')}")
        print(f"결함 요약: {data.get('defect_summary', 'N/A')}")
        print(f"심각도:   {data.get('severity', 'N/A')}")
        print(f"조치 목록: {data.get('required_actions', [])}")

        if data.get("severity") == "HIGH":
            print("\n⚠ 긴급 처리 필요 — 품질팀 즉시 알림 대상")
    else:
        print("[경고] JSON 파싱 실패 또는 빈 응답")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--step",
        type=int,
        default=0,
        choices=[0, 1, 2, 3],
        help="0=전체, 1~3=해당 단계만",
    )
    args = ap.parse_args()

    if not DATA_FILE.exists():
        print(f"[오류] 데이터 파일 없음: {DATA_FILE}")
        sys.exit(1)

    report = load_report()
    print(f"[원본 로드] {DATA_FILE.name} ({len(report)}자)\n")

    steps = {1: step1_summarize, 2: step2_structured, 3: step3_json}

    if args.step == 0:
        for fn in steps.values():
            fn(report)
    else:
        steps[args.step](report)


if __name__ == "__main__":
    main()
