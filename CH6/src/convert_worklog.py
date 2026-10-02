# -*- coding: utf-8 -*-
"""
convert_worklog.py — 6.8 실습: 야간 근무자 작업일지 표준 보고서 변환
======================================================================

지저분한 야간조 작업일지를 LLM 으로 표준 인수인계 보고서로 자동 변환한다.
프롬프트 개선을 3단계로 나눠, 같은 원본이 프롬프트에 따라 얼마나 달라지는지 확인한다.

    Step 1: 단순 프롬프트 ("정리해줘")
    Step 2: System Prompt + 출력 형식 지정
    Step 3: Few-shot + 우선순위 태그 (HIGH/MEDIUM/LOW)

실행:
    python3 convert_worklog.py                # 3단계 모두 실행
    python3 convert_worklog.py --step 3       # 특정 단계만
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat


DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "work_log.txt"


def load_worklog() -> str:
    """야간조 작업일지 원본 로드."""
    return DATA_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# STEP 1: 단순 프롬프트
# ---------------------------------------------------------------------------
def step1_naive(work_log: str) -> None:
    print("=" * 60)
    print("[STEP 1] 단순 프롬프트 — '정리해줘'")
    print("=" * 60)

    system = "너는 유용한 조수다."
    user = f"이 작업일지를 정리해줘:\n{work_log}"

    answer = chat(system, user, temperature=0.2, max_tokens=800)
    print(f"[답변]\n{answer}\n")


# ---------------------------------------------------------------------------
# STEP 2: System Prompt + 형식 지정
# ---------------------------------------------------------------------------
def step2_structured(work_log: str) -> None:
    print("=" * 60)
    print("[STEP 2] System Prompt + 출력 형식 지정")
    print("=" * 60)

    system = """당신은 제조 현장의 야간조/주간조 인수인계 담당자다.
야간조가 남긴 작업 일지를 주간조가 즉시 이해할 수 있는 표준 보고서 형식으로 변환한다.

다음 형식을 정확히 따라야 한다.

## 긴급 조치 사항 (Action Required)
- [시간] [라인/설비] [내용] → [담당/우선순위]

## 후속 관찰 사항 (Monitoring)
- [라인/설비] [내용]

## 재고 · 자재 이슈 (Inventory)
- [라인/설비] [내용] [조치 필요 여부]

## 정상 확인 사항 (Normal Status)
- [라인/설비] [내용]"""

    user = f"다음 야간조 작업 일지를 변환해줘:\n\n{work_log}"

    answer = chat(system, user, temperature=0.2, max_tokens=1000)
    print(f"[답변]\n{answer}\n")


# ---------------------------------------------------------------------------
# STEP 3: Few-shot + 우선순위 태그
# ---------------------------------------------------------------------------
def step3_fewshot(work_log: str) -> None:
    print("=" * 60)
    print("[STEP 3] Few-shot 예시 + 우선순위 태그")
    print("=" * 60)

    system = """당신은 제조 현장의 인수인계 담당자다.
야간조 작업 일지를 표준 인수인계 보고서 형식으로 변환한다.

각 항목에 우선순위 태그를 붙인다.
[HIGH]   안전 관련, 라인 정지 우려, 품질 영향 큰 이슈
[MEDIUM] 부품 마모 신호, 재고 부족, 이상 신호
[LOW]    정상 범위 관찰 사항, 일상적 확인 사항

예시:
[HIGH]   [03:15] 3라인 로터 - 이상 유발음, 라인 정지 위험 → 즉시 확인
[MEDIUM] [--]    5라인 부품 P-2201 재고 12개 → 오전 중 발주 진행
[LOW]    [04:30] 냉각수 최고 28도, 정상 범위 → 관찰만

다음 형식으로 정리한다.
## 인수인계 요약
### HIGH 우선순위
### MEDIUM 우선순위
### LOW 우선순위"""

    user = f"다음 일지를 변환해줘:\n{work_log}"

    answer = chat(system, user, temperature=0.2, max_tokens=1000)
    print(f"[답변]\n{answer}\n")


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

    work_log = load_worklog()
    print(f"[원본 로드] {DATA_FILE.name} ({len(work_log)}자)\n")

    steps = {1: step1_naive, 2: step2_structured, 3: step3_fewshot}

    if args.step == 0:
        for fn in steps.values():
            fn(work_log)
    else:
        steps[args.step](work_log)


if __name__ == "__main__":
    main()
