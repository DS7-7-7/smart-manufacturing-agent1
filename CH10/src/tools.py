# -*- coding: utf-8 -*-
"""
tools.py — 10장 실습: 에이전트가 사용할 도구 모음
=====================================================

에이전트에게 쥐어줄 도구(Tool) 두 개를 정의한다.

    1) calculator      : 사칙연산 및 수식 계산
    2) inventory_lookup: 재고 데이터베이스에서 부품 정보 조회

각 도구는 다음 세 가지로 구성된다.
    - name        : 도구 이름 (에이전트가 호출할 때 사용)
    - description : 도구 설명 (에이전트가 언제 쓸지 판단하는 근거)
    - run(args)   : 실제 실행 함수

이 파일은 단독 실행 가능. 각 도구가 개별적으로 작동하는지 확인한다.
    python3 tools.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
INVENTORY_FILE = BASE_DIR / "data" / "inventory.json"


# ---------------------------------------------------------------------------
# 도구 1: 계산기
# ---------------------------------------------------------------------------
def calculator_run(expression: str) -> str:
    """사칙연산 수식을 안전하게 계산."""
    # 허용 문자만 통과 (숫자, 연산자, 괄호, 공백, 소수점)
    if not re.match(r"^[\d\s\+\-\*\/\(\)\.]+$", expression):
        return f"오류: 허용되지 않은 문자 포함 ({expression!r})"
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return f"계산 결과: {result}"
    except Exception as e:
        return f"계산 오류: {e}"


CALCULATOR = {
    "name": "calculator",
    "description": (
        "사칙연산을 수행한다. 숫자·연산자(+, -, *, /)·괄호로 구성된 수식을 넘긴다. "
        "예: '12000 * 45' 또는 '(320000 + 45000) * 3'"
    ),
    "run": calculator_run,
}


# ---------------------------------------------------------------------------
# 도구 2: 재고 조회
# ---------------------------------------------------------------------------
def inventory_lookup_run(part_id: str) -> str:
    """부품 ID로 재고 정보를 조회."""
    part_id = part_id.strip().upper()

    if not INVENTORY_FILE.exists():
        return f"오류: 재고 파일 없음 ({INVENTORY_FILE})"

    with open(INVENTORY_FILE, encoding="utf-8") as f:
        inventory = json.load(f)

    if part_id not in inventory:
        available = ", ".join(inventory.keys())
        return f"부품 {part_id} 를 찾을 수 없다. 등록된 부품: {available}"

    item = inventory[part_id]
    status = "부족" if item["stock"] < item["threshold"] else "정상"
    return (
        f"[{part_id}] {item['name']}\n"
        f"  재고: {item['stock']}개 (임계값: {item['threshold']}개, 상태: {status})\n"
        f"  단가: {item['unit_price']:,}원\n"
        f"  공급사: {item['supplier']}"
    )


INVENTORY_LOOKUP = {
    "name": "inventory_lookup",
    "description": (
        "부품 ID 로 재고 정보를 조회한다. 재고 수량, 임계값, 단가, 공급사를 반환한다. "
        "부품 ID 형식은 'P-1234' 이다. 예: 'P-2201'"
    ),
    "run": inventory_lookup_run,
}


# ---------------------------------------------------------------------------
# 도구 레지스트리 (에이전트가 사용할 도구 목록)
# ---------------------------------------------------------------------------
TOOLS = [CALCULATOR, INVENTORY_LOOKUP]


def get_tool(name: str):
    """이름으로 도구를 찾아 반환."""
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


def format_tools_description() -> str:
    """에이전트 프롬프트에 넣을 도구 설명 문자열."""
    lines = []
    for i, tool in enumerate(TOOLS, 1):
        lines.append(f"{i}. {tool['name']}: {tool['description']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 단독 실행: 각 도구 테스트
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("[테스트 1] 계산기")
    print("=" * 60)
    print(calculator_run("12000 * 45"))
    print(calculator_run("(320000 + 45000) * 3"))
    print(calculator_run("import os"))  # 오류 케이스

    print()
    print("=" * 60)
    print("[테스트 2] 재고 조회")
    print("=" * 60)
    print(inventory_lookup_run("P-2201"))
    print()
    print(inventory_lookup_run("P-9999"))  # 없는 부품

    print()
    print("=" * 60)
    print("[도구 목록 (에이전트 프롬프트용)]")
    print("=" * 60)
    print(format_tools_description())
