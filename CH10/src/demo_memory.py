# -*- coding: utf-8 -*-
"""
demo_memory.py — 10장 실습: 메모리 있는 에이전트 데모
========================================================

에이전트의 '메모리' 요소가 왜 중요한지 보여주는 데모.
같은 사용자가 연속으로 여러 질문을 던지고,
에이전트가 앞서 나온 정보를 기억하며 답하는 과정을 확인한다.

시나리오:
    1) 사용자: P-2201 재고 알려줘
    2) 사용자: 그거 3개 사려면 얼마야?    ← "그거" 는 앞서 조회한 부품
    3) 사용자: 임계값 이하면 몇 개 더 필요해?   ← 앞서 조회한 임계값 참조

메모리가 없다면 각 질문마다 처음부터 다시 조회해야 한다.
메모리가 있으면 이전 대화 맥락을 활용해 이어서 답한다.

실행:
    python3 demo_memory.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from agent_skeleton import Memory, run_agent


SCENARIO = [
    "P-2201 재고 상태 알려줘",
    "그거 3개 사려면 얼마야?",
    "임계값 이하면 몇 개 더 발주해야 해?",
]


def main() -> None:
    print("=" * 60)
    print("메모리 데모 — 연속 요청 3개")
    print("=" * 60)

    memory = Memory()

    for i, request in enumerate(SCENARIO, 1):
        print(f"\n{'─' * 60}")
        print(f"[요청 {i}] {request}")
        print("─" * 60)

        answer = run_agent(request, memory, max_steps=5)

        print(f"\n[답변 {i}] {answer}")

    print(f"\n{'=' * 60}")
    print("[메모리 최종 상태]")
    print("=" * 60)
    print(memory.as_prompt())


if __name__ == "__main__":
    main()
