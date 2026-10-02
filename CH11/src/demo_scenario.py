# -*- coding: utf-8 -*-
"""
demo_scenario.py — 11장 실습: 자율 시나리오 데모
====================================================

Function Calling 에이전트의 실전 시나리오를 3개 실행한다.
각 시나리오마다 에이전트가 어떤 도구를 어떤 순서로 호출하는지 관찰한다.

시나리오:
    A) 단일 조회      : "3라인 지금 뭐 만들고 있어?"
    B) 조건부 알림    : "3라인 상태 확인하고 이상 있으면 정비팀에 알려줘"
    C) 자동 발주      : "재고 부족한 부품 자동으로 발주해줘"

실행:
    python3 demo_scenario.py
    python3 demo_scenario.py --scenario A     # 특정 시나리오만
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from agent_toolcall import run_agent


SCENARIOS = {
    "A": {
        "title": "단일 조회 — 3라인 생산 상태",
        "request": "3라인 지금 뭐 만들고 있어?",
    },
    "B": {
        "title": "조건부 알림 — 3라인 이상 시 정비팀 통보",
        "request": "3라인 상태 확인하고 이상 있으면 김정비에게 정비팀 알림 보내줘",
    },
    "C": {
        "title": "자동 발주 — 재고 부족 부품 자동 처리",
        "request": (
            "P-2201 과 P-3105 재고 확인해서, 임계값 이하인 부품은 "
            "임계값의 2배 수량으로 자동 발주해줘."
        ),
    },
}


def run_scenario(key: str) -> None:
    scenario = SCENARIOS[key]
    print("=" * 60)
    print(f"[시나리오 {key}] {scenario['title']}")
    print(f"요청: {scenario['request']}")
    print("=" * 60)

    answer = run_agent(scenario["request"], max_steps=10)

    print(f"\n[최종 답변]\n{answer}")
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", type=str, default=None,
                    choices=list(SCENARIOS.keys()),
                    help="특정 시나리오만 실행 (A/B/C)")
    args = ap.parse_args()

    if args.scenario:
        run_scenario(args.scenario)
    else:
        for key in SCENARIOS.keys():
            run_scenario(key)
            print()


if __name__ == "__main__":
    main()
