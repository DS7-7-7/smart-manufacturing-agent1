# -*- coding: utf-8 -*-
"""
09_run_agent.py
===============
실제 사용자 주문 입력 → Agent 실행 진입점

실행
    python 09_run_agent.py                        # 대화형 입력
    python 09_run_agent.py --workflow             # LangGraph 워크플로로 실행
    LLM_BACKEND=ollama python 09_run_agent.py     # 로컬 Ollama 로 실습
    LLM_BACKEND=mock  python 09_run_agent.py      # LLM 없이 실습

    (환경변수 LLM_BACKEND: qwen | gpt | ollama | mock)
"""

from __future__ import annotations

import os
import sys
from importlib import import_module

seed = import_module("02_seed_data")
agent = import_module("07_order_agent")
workflow = import_module("08_workflow")


BANNER = """
============================================================
 제14장 종합 실습 — 제조 주문 처리 Agent
------------------------------------------------------------
 예) 신제품 로봇청소기 500개 주문해줘.
 종료: quit / exit / 빈 줄
============================================================
"""


def run_once(text: str, use_workflow: bool) -> None:
    """주문 한 건 처리. 제품을 특정 못하면 후보를 보여주고 다시 입력받는다."""
    print("-" * 60)
    if use_workflow:
        workflow.run_workflow(text)
    else:
        result = agent.process_order(text)
        # 제품을 특정하지 못한 경우 → 후보 제시 후 재입력 (되묻기)
        while result.get("need_clarification"):
            cands = result.get("candidates", [])
            print("\n어떤 제품인지 알려주세요:")
            for i, p in enumerate(cands, 1):
                print(f"  {i}. {p['name']} ({p['product_id']})")
            print("  0. 취소")
            try:
                sel = input("번호 또는 제품명 입력 > ").strip()
            except (EOFError, KeyboardInterrupt):
                print("취소되었습니다.")
                break
            if sel in ("0", "취소", "", "cancel"):
                print("주문을 취소했습니다.")
                break
            # 번호로 선택했으면 해당 제품명으로, 아니면 입력값 그대로 재시도
            if sel.isdigit() and 1 <= int(sel) <= len(cands):
                chosen = cands[int(sel) - 1]
                # 원래 문장의 수량/긴급은 유지하기 위해 제품명을 앞에 붙여 재구성
                new_text = f"{chosen['name']} {text}"
                result = agent.process_order(new_text)
            else:
                result = agent.process_order(sel if sel else text)
    print("-" * 60)


def main() -> None:
    use_workflow = "--workflow" in sys.argv
    reset = "--no-reset" not in sys.argv

    backend = os.environ.get("LLM_BACKEND", "qwen")
    print(BANNER)
    print(f" LLM 백엔드 : {backend}")
    print(f" 실행 모드  : {'LangGraph Workflow' if use_workflow else 'Order Agent'}")

    # 실습 편의를 위해 시작 시 DB를 시드 상태로 초기화 (--no-reset 로 끌 수 있음)
    if reset:
        seed.seed()
        print(" DB 초기화  : 완료 (시드 데이터 재입력)\n")

    while True:
        try:
            text = input("주문을 입력하세요:\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break
        if text.lower() in ("quit", "exit", ""):
            print("종료합니다.")
            break
        run_once(text, use_workflow)


if __name__ == "__main__":
    main()