# -*- coding: utf-8 -*-
"""
10_exception_handler.py
=======================
예외 처리 (14.6)

정상 주문 외에 실제 업무에서 발생하는 예외 상황을 처리한다.
Agent가 임의로 생산/발주를 실행하지 않고, 규칙과 승인 절차를 따른다.

    8.1 부분 결제
        결제 상태 확인 → 완납이면 진행 / 부분결제·미결제면 보류(승인 요청)

    8.2 긴급 주문
        생산 CAPA 확인 → 납기 충족 가능하면 긴급 생산 / 불가하면 관리자 승인
"""

from __future__ import annotations

from importlib import import_module

tools = import_module("05_erp_tools")
rules = import_module("06_business_rules")


# ===========================================================================
# 8.1 부분 결제 처리
# ===========================================================================
def handle_payment(order_id: int, verbose: bool = True) -> dict:
    """
    결제 상태에 따라 주문 진행 여부를 결정한다.
        paid            → 진행 (confirmed 유지)
        partial/unpaid  → 보류 (on_hold) + 승인 요청
    반환: {order_id, payment_status, decision, approved}
    """
    pay = rules.check_payment(order_id)
    status = pay["status"]

    if pay["can_proceed"]:
        decision = "proceed"
        approved = True
        msg = f"[결제] 주문 #{order_id} 완납 확인 → 진행"
    else:
        # 임의 진행 금지: 주문을 보류로 전환하고 승인 요청
        tools.update_order_status(order_id, "on_hold")
        decision = "hold"
        approved = False
        msg = (f"[결제] 주문 #{order_id} 결제 상태 '{status}' "
               f"→ 보류(on_hold), 승인 요청 필요")

    if verbose:
        print(msg)
    return {
        "order_id": order_id,
        "payment_status": status,
        "decision": decision,
        "approved": approved,
    }


def approve_hold_order(order_id: int, approver: str = "manager",
                       verbose: bool = True) -> dict:
    """관리자가 보류 주문을 승인하여 진행 상태로 되돌린다."""
    tools.update_order_status(order_id, "confirmed")
    if verbose:
        print(f"[승인] 주문 #{order_id} 관리자({approver}) 승인 → confirmed")
    return {"order_id": order_id, "status": "confirmed", "approver": approver}


# ===========================================================================
# 8.2 긴급 주문 처리
# ===========================================================================
def handle_urgent(product_id: str, quantity: int, due_days: int = 3,
                  verbose: bool = True) -> dict:
    """
    긴급 주문의 생산 CAPA/납기를 확인한다.
        납기 충족 가능 → 긴급 생산 진행
        불가           → 관리자 승인 필요
    반환: {feasible, need_days, decision, reason}
    """
    capa = rules.check_urgent_capacity(quantity, due_days=due_days)

    if capa["feasible"]:
        decision = "urgent_production"
        msg = f"[긴급] 납기 {due_days}일 내 생산 가능 → 긴급 생산 진행"
    else:
        decision = "need_approval"
        msg = (f"[긴급] {capa['need_days']}일 소요로 납기 {due_days}일 초과 "
               f"→ 관리자 승인 필요")

    if verbose:
        print(msg)
    return {
        "feasible": capa["feasible"],
        "need_days": capa["need_days"],
        "decision": decision,
        "reason": capa["reason"],
    }


# ===========================================================================
# 통합 예외 처리 (주문 처리 후 호출)
# ===========================================================================
def handle_exceptions(order_id: int, product_id: str, quantity: int,
                      is_urgent: bool = False, due_days: int = 3,
                      verbose: bool = True) -> dict:
    """결제·긴급 예외를 순서대로 점검한다."""
    result = {"order_id": order_id}

    # 1) 결제 예외
    result["payment"] = handle_payment(order_id, verbose=verbose)

    # 2) 긴급 예외
    if is_urgent:
        result["urgent"] = handle_urgent(product_id, quantity,
                                         due_days=due_days, verbose=verbose)
    return result


# ===========================================================================
# 단독 실행 시: 예외 시나리오 시연
# ===========================================================================
if __name__ == "__main__":
    seed = import_module("02_seed_data")
    seed.seed()
    print()

    # --- 시나리오 A: 부분 결제 ---
    print("--- [A] 부분 결제 시나리오 ---")
    o = tools.create_order("RC700", 500, customer_id="C001")
    oid = o["order_id"]
    # 총액의 일부만 납부한 상태로 만든다
    init_db = import_module("01_init_db")
    erp = import_module("03_erp_models")
    with init_db.get_session() as s:
        pay = s.query(erp.Payment).filter_by(order_id=oid).first()
        pay.paid_amount = pay.total_amount * 0.3   # 30%만 납부
        pay.recompute_status()
    r = handle_payment(oid)
    print("  결과:", r)
    approve_hold_order(oid)   # 관리자 승인
    print()

    # --- 시나리오 B: 긴급 주문 (납기 충족) ---
    print("--- [B] 긴급 주문 (500개 / 3일) ---")
    print("  결과:", handle_urgent("RC700", 500, due_days=3))
    print()

    # --- 시나리오 C: 긴급 주문 (납기 초과) ---
    print("--- [C] 긴급 주문 (1000개 / 3일) ---")
    print("  결과:", handle_urgent("RC700", 1000, due_days=3))
