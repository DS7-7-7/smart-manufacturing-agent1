# -*- coding: utf-8 -*-
"""
06_business_rules.py
====================
비즈니스 로직 (핵심 업무 규칙)

LLM은 자연어 이해와 작업 계획만 담당하고, 재고·생산·결제·발주 같은
"돈과 직결되는 판단"은 이 파일의 규칙이 결정한다.

    LLM            → 자연어 이해 및 작업 계획
    Business Rules → 업무 규칙 및 의사결정   ← 이 파일
    ERP Tools      → DB 조회 및 데이터 변경

주요 규칙
    check_stock            재고 충분 여부 / 부족량 계산
    can_produce            BOM 기준 생산 가능 여부 (자재 충분?)
    plan_purchase          부족 자재별 구매발주 계획
    check_payment          결제 상태 확인 (진행 가능?)
    decide_order           위 규칙을 종합한 최종 처리 방향 결정
    check_urgent_capacity  긴급 주문의 생산 CAPA/납기 판단
"""

from __future__ import annotations

from importlib import import_module

tools = import_module("05_erp_tools")

# 생산 능력(CAPA) 관련 상수 — 실습용 임의값
DAILY_PRODUCTION_CAPA = 200      # 하루 생산 가능 수량
URGENT_DUE_DAYS = 3              # 긴급 주문 기본 납기(일)


# ===========================================================================
# 1. 재고 규칙
# ===========================================================================
def check_stock(product_id: str, quantity: int) -> dict:
    """
    재고 충분 여부와 부족량을 판단한다.
    반환: {enough: bool, available: int, shortage: int}
    """
    inv = tools.get_inventory(product_id, required_qty=quantity)
    if inv is None:
        return {"enough": False, "available": 0, "shortage": quantity,
                "error": "재고 정보 없음"}
    return {
        "enough": inv["shortage"] <= 0,
        "available": inv["available_stock"],
        "shortage": inv["shortage"],
    }


# ===========================================================================
# 2. 생산 가능 여부 (BOM 기준)
# ===========================================================================
def can_produce(product_id: str, quantity: int) -> dict:
    """
    완제품 quantity 개를 생산할 때, BOM상의 각 원자재 재고가 충분한지 확인한다.
    반환: {
        producible: bool,           # 자재가 모두 충분한가
        materials: [ {material_id, need, available, shortage}, ... ]
    }
    """
    bom = tools.get_bom(product_id)
    if not bom:
        return {"producible": False, "materials": [], "error": "BOM 없음"}

    materials = []
    all_ok = True
    for item in bom:
        need = item["quantity"] * quantity          # 총 소요량
        inv = tools.get_inventory(item["material_id"], required_qty=need)
        available = inv["available_stock"] if inv else 0
        shortage = max(0, need - available)
        if shortage > 0:
            all_ok = False
        materials.append({
            "material_id": item["material_id"],
            "need": need,
            "available": available,
            "shortage": shortage,
        })

    return {"producible": all_ok, "materials": materials}


# ===========================================================================
# 3. 구매발주 계획 (부족 자재 → 공급업체 매칭)
# ===========================================================================
def plan_purchase(product_id: str, quantity: int) -> list[dict]:
    """
    생산에 부족한 자재를 공급업체와 매칭하여 발주 계획을 세운다.
    반환: [ {material_id, quantity, supplier_id, unit_price, lead_time_days}, ... ]
    """
    prod = can_produce(product_id, quantity)
    plan = []
    for m in prod["materials"]:
        if m["shortage"] <= 0:
            continue
        suppliers = tools.get_supplier(m["material_id"])
        if not suppliers:
            plan.append({
                "material_id": m["material_id"],
                "quantity": m["shortage"],
                "supplier_id": None,
                "error": "공급업체 없음",
            })
            continue
        # 단가가 가장 낮은 공급업체 선택
        best = min(suppliers, key=lambda x: x["unit_price"])
        plan.append({
            "material_id": m["material_id"],
            "quantity": m["shortage"],
            "supplier_id": best["supplier_id"],
            "unit_price": best["unit_price"],
            "lead_time_days": best["lead_time_days"],
        })
    return plan


# ===========================================================================
# 4. 결제 규칙
# ===========================================================================
def check_payment(order_id: int) -> dict:
    """
    결제 상태로 주문 진행 가능 여부를 판단한다.
        paid    → 진행 가능
        partial → 승인 요청/보류
        unpaid  → 보류
    반환: {status, can_proceed: bool}
    """
    pay = tools.get_payment_status(order_id)
    if pay is None:
        return {"status": "unknown", "can_proceed": False}
    status = pay["status"]
    return {"status": status, "can_proceed": status == "paid"}


# ===========================================================================
# 5. 종합 의사결정
# ===========================================================================
def decide_order(product_id: str, quantity: int) -> dict:
    """
    재고 → 생산 → 구매 순으로 규칙을 적용해 최종 처리 방향을 결정한다.
    반환: {
        action: "ship" | "produce" | "purchase",
        ship_qty, produce_qty,
        purchase_plan: [...],
        reason: str
    }
    """
    stock = check_stock(product_id, quantity)

    # (1) 재고로 전량 충당 가능 → 출고
    if stock["enough"]:
        return {
            "action": "ship",
            "ship_qty": quantity,
            "produce_qty": 0,
            "purchase_plan": [],
            "reason": f"재고 {stock['available']}개로 충분하여 전량 출고",
        }

    # (2) 재고 부족 → 부족분 생산 필요
    ship_qty = stock["available"]
    produce_qty = stock["shortage"]
    prod = can_produce(product_id, produce_qty)

    if prod["producible"]:
        return {
            "action": "produce",
            "ship_qty": ship_qty,
            "produce_qty": produce_qty,
            "purchase_plan": [],
            "reason": f"재고 {ship_qty}개 출고 후 {produce_qty}개 생산 (자재 충분)",
        }

    # (3) 생산에 필요한 자재도 부족 → 구매발주 필요
    purchase_plan = plan_purchase(product_id, produce_qty)
    return {
        "action": "purchase",
        "ship_qty": ship_qty,
        "produce_qty": produce_qty,
        "purchase_plan": purchase_plan,
        "reason": f"{produce_qty}개 생산 필요하나 자재 부족 → 구매발주 후 생산",
    }


# ===========================================================================
# 6. 긴급 주문 규칙 (14.6 예외 처리에서 사용)
# ===========================================================================
def check_urgent_capacity(quantity: int, due_days: int = URGENT_DUE_DAYS) -> dict:
    """
    긴급 주문이 생산 CAPA로 납기 내 충족 가능한지 판단한다.
    반환: {feasible: bool, need_days: int, reason}
    """
    need_days = -(-quantity // DAILY_PRODUCTION_CAPA)  # 올림 나눗셈
    feasible = need_days <= due_days
    return {
        "feasible": feasible,
        "need_days": need_days,
        "reason": (f"일 생산능력 {DAILY_PRODUCTION_CAPA}개 기준 {need_days}일 소요, "
                   f"납기 {due_days}일 {'충족' if feasible else '초과 → 관리자 승인 필요'}"),
    }


# ===========================================================================
# 단독 실행 시: 규칙 동작 확인 (시드 데이터 기준)
# ===========================================================================
if __name__ == "__main__":
    print("[check_stock] P300 x500 :", check_stock("P300", 500))
    print("[can_produce] P300 x400 :", can_produce("P300", 400))
    print("[plan_purchase] P300 x400:", plan_purchase("P300", 400))
    print("[decide_order] P300 x500:")
    d = decide_order("P300", 500)
    for k, v in d.items():
        print(f"    {k}: {v}")
    print("[check_urgent_capacity] 500 / 3일:", check_urgent_capacity(500))
