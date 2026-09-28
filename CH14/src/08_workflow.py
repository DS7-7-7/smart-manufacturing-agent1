# -*- coding: utf-8 -*-
"""
08_workflow.py
==============
LangGraph 기반 주문 처리 Workflow

07_order_agent 의 절차를 LangGraph 노드/엣지로 재구성하여,
분기(재고 충분? / 생산 가능?)가 명시적으로 드러나는 상태 기계로 만든다.

    START → 주문분석 → 주문검증 → 재고확인
                                    │
                          재고 충분? ┴─ YES → 출고 → END
                                    └─ NO  → 부족량계산 → 생산가능?
                                                          ├ YES → 생산계획 → END
                                                          └ NO  → 구매발주 → 생산계획 → END
"""

from __future__ import annotations

import os
from importlib import import_module
from typing import TypedDict, Optional

from langgraph.graph import StateGraph, START, END

agent = import_module("07_order_agent")
tools = import_module("05_erp_tools")
rules = import_module("06_business_rules")


# ===========================================================================
# Workflow 상태 정의
# ===========================================================================
class OrderState(TypedDict, total=False):
    text: str                 # 원본 자연어 주문
    customer_id: str
    product_id: str
    quantity: int
    priority: str
    order_id: int
    available: int
    shortage: int
    action: str               # ship / produce / purchase
    produce_qty: int
    ship_qty: int
    purchase_plan: list
    production_id: Optional[int]
    purchases: list
    log: list
    error: str


def _log(state: OrderState, msg: str) -> None:
    state.setdefault("log", []).append(msg)
    print(msg)


# ===========================================================================
# 노드 정의
# ===========================================================================
def node_analyze(state: OrderState) -> OrderState:
    """주문 분석: 자연어 → 구조화."""
    req = agent.analyze_order(state["text"])
    state["product_id"] = req.product_name
    state["quantity"] = req.quantity
    state["priority"] = req.priority.value
    _log(state, f"[분석] 제품={req.product_name}, 수량={req.quantity}, "
                f"우선순위={req.priority.value}")
    return state


def node_validate(state: OrderState) -> OrderState:
    """주문 검증: 제품 식별(LLM 판단→규칙 폴백) + 주문 생성."""
    ident = agent.identify_product(state["text"], product_hint=state.get("product_id", ""))
    product = ident["product"]
    if product is None:
        names = ", ".join(p["name"] for p in ident["candidates"])
        state["error"] = f"제품 특정 불가 — 후보: {names}"
        _log(state, f"[검증] 실패: {state['error']}")
        return state
    state["product_id"] = product["product_id"]
    order = tools.create_order(
        state["product_id"], state["quantity"],
        customer_id=state.get("customer_id", "C001"),
        priority=state.get("priority", "normal"),
    )
    state["order_id"] = order["order_id"]
    _log(state, f"[검증] 제품 식별({ident['source']}) → "
                f"{product['product_id']} / 주문 #{order['order_id']} 생성")
    return state


def node_check_stock(state: OrderState) -> OrderState:
    """재고 확인."""
    inv = tools.get_inventory(state["product_id"], required_qty=state["quantity"])
    state["available"] = inv["available_stock"]
    state["shortage"] = inv["shortage"]
    _log(state, f"[재고] 가용 {inv['available_stock']}, 부족 {inv['shortage']}")
    return state


def node_ship(state: OrderState) -> OrderState:
    """출고 (재고 충분)."""
    tools.update_order_status(state["order_id"], "shipped")
    state["action"] = "ship"
    state["ship_qty"] = state["quantity"]
    _log(state, f"[출고] {state['quantity']}개 출고 완료 → shipped")
    return state


def node_calc_shortage(state: OrderState) -> OrderState:
    """부족량 계산 + 생산 가능 여부 판단."""
    state["ship_qty"] = state["available"]
    state["produce_qty"] = state["shortage"]
    prod = rules.can_produce(state["product_id"], state["produce_qty"])
    state["purchase_plan"] = rules.plan_purchase(
        state["product_id"], state["produce_qty"]) if not prod["producible"] else []
    state["action"] = "produce" if prod["producible"] else "purchase"
    _log(state, f"[부족량] {state['produce_qty']}개 생산 필요 / "
                f"자재 {'충분' if prod['producible'] else '부족'}")
    return state


def node_purchase(state: OrderState) -> OrderState:
    """구매발주 (자재 부족)."""
    purchases = []
    for p in state.get("purchase_plan", []):
        if p.get("supplier_id"):
            po = tools.create_purchase_order(
                p["supplier_id"], p["material_id"], p["quantity"])
            purchases.append(po)
            _log(state, f"[구매] {p['material_id']} {p['quantity']}개 @ {p['supplier_id']}")
    state["purchases"] = purchases
    return state


def node_production(state: OrderState) -> OrderState:
    """생산계획 생성."""
    prod = tools.create_production_order(
        state["product_id"], state["produce_qty"], state["order_id"])
    state["production_id"] = prod["production_id"]
    tools.update_order_status(state["order_id"], "confirmed")
    _log(state, f"[생산] 생산계획 #{prod['production_id']} "
                f"({state['produce_qty']}개) → confirmed")
    return state


# ===========================================================================
# 조건 분기 함수
# ===========================================================================
def branch_stock(state: OrderState) -> str:
    """재고 충분 여부로 분기."""
    if state.get("error"):
        return "end"
    return "ship" if state["shortage"] <= 0 else "shortage"


def branch_produce(state: OrderState) -> str:
    """생산 가능 여부로 분기 (자재 충분하면 바로 생산, 아니면 구매 먼저)."""
    return "production" if state["action"] == "produce" else "purchase"


# ===========================================================================
# 그래프 구성
# ===========================================================================
def build_workflow():
    g = StateGraph(OrderState)

    g.add_node("analyze", node_analyze)
    g.add_node("validate", node_validate)
    g.add_node("check_stock", node_check_stock)
    g.add_node("ship", node_ship)
    g.add_node("calc_shortage", node_calc_shortage)
    g.add_node("purchase", node_purchase)
    g.add_node("production", node_production)

    g.add_edge(START, "analyze")
    g.add_edge("analyze", "validate")
    g.add_edge("validate", "check_stock")

    # 재고 충분? → 출고 / 부족량계산
    g.add_conditional_edges("check_stock", branch_stock,
                            {"ship": "ship", "shortage": "calc_shortage", "end": END})
    g.add_edge("ship", END)

    # 생산 가능? → 생산 / 구매 후 생산
    g.add_conditional_edges("calc_shortage", branch_produce,
                            {"production": "production", "purchase": "purchase"})
    g.add_edge("purchase", "production")
    g.add_edge("production", END)

    return g.compile()


# 모듈 로드시 1회 컴파일
WORKFLOW = build_workflow()


def run_workflow(text: str, customer_id: str = "C001") -> OrderState:
    """워크플로 실행 진입점."""
    init: OrderState = {"text": text, "customer_id": customer_id, "log": []}
    return WORKFLOW.invoke(init)


# ===========================================================================
# 단독 실행 시: mock 백엔드로 워크플로 시연
# ===========================================================================
if __name__ == "__main__":
    os.environ.setdefault("LLM_BACKEND", "mock")
    print(f"[LLM_BACKEND] {os.environ['LLM_BACKEND']}\n")
    final = run_workflow("신제품 로봇청소기 500개 주문해줘.")
    print("\n=== 최종 상태 ===")
    print(f"주문번호   : #{final.get('order_id')}")
    print(f"처리액션   : {final.get('action')}")
    print(f"출고/생산  : {final.get('ship_qty')} / {final.get('produce_qty')}")
    print(f"구매발주   : {len(final.get('purchases', []))}건")
    print(f"생산계획   : #{final.get('production_id')}")
