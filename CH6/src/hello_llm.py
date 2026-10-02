# -*- coding: utf-8 -*-
"""
hello_llm.py — 6.7 실습: LLM API 호출 기본 패턴
=================================================

교재 공용 모듈 llm_client.chat() 을 이용해 LLM 을 처음 호출해본다.

수행 순서:
    1) System Prompt 없이 단순 질문 → 응답 확인
    2) System Prompt (역할 부여) + User Message → 응답 변화 확인
    3) temperature 조정 실험 (0 vs 1.2)

실행:
    python3 hello_llm.py
    python3 hello_llm.py --step 2       # 특정 단계만 실행
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 상위 폴더의 llm_client.py 를 import 하기 위한 경로 추가
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat


# ---------------------------------------------------------------------------
# STEP 1: 단순 질문
# ---------------------------------------------------------------------------
def step1_simple_call() -> None:
    """System Prompt 없이 단순 질문."""
    print("=" * 60)
    print("[STEP 1] 단순 API 호출")
    print("=" * 60)

    system = "너는 한 문장으로만 답한다."
    user = "LLM이 무엇인지 한 줄로 설명해줘."

    print(f"[질문] {user}\n")
    answer = chat(system, user, temperature=0.3, max_tokens=200)
    print(f"[답변] {answer}\n")


# ---------------------------------------------------------------------------
# STEP 2: 역할 부여
# ---------------------------------------------------------------------------
def step2_system_role() -> None:
    """System Prompt 로 역할 부여."""
    print("=" * 60)
    print("[STEP 2] System Prompt로 역할 부여")
    print("=" * 60)

    system = "당신은 25년 경력의 제조 공정 전문가다. 실무 관점에서 답변한다."
    user = "냉각수 온도가 상승할 때 확인해야 할 3가지를 알려줘."

    print(f"[역할] {system}")
    print(f"[질문] {user}\n")
    answer = chat(system, user, temperature=0.3, max_tokens=500)
    print(f"[답변]\n{answer}\n")


# ---------------------------------------------------------------------------
# STEP 3: Temperature 실험
# ---------------------------------------------------------------------------
def step3_temperature_test() -> None:
    """같은 질문을 다른 temperature로 3번씩 실행."""
    print("=" * 60)
    print("[STEP 3] Temperature 값에 따른 응답 변화")
    print("=" * 60)

    system = "너는 제조 현장 엔지니어다. 간결하게 답한다."
    user = "냉각 시스템 이상의 가능한 원인 3가지를 짧게 알려줘."

    for temp in [0.1, 1.2]:
        print(f"\n--- Temperature = {temp} ---")
        for i in range(2):
            answer = chat(system, user, temperature=temp, max_tokens=200)
            preview = answer.replace("\n", " ")[:80]
            print(f"[시도 {i + 1}] {preview}...")


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
        help="0=전체 실행, 1~3=해당 단계만",
    )
    args = ap.parse_args()

    steps = {1: step1_simple_call, 2: step2_system_role, 3: step3_temperature_test}

    if args.step == 0:
        for fn in steps.values():
            fn()
    else:
        steps[args.step]()


if __name__ == "__main__":
    main()
