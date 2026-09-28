def decide_order(product_id, quantity):
    stock = check_stock(product_id, quantity)

    # (1) 재고로 전량 충당 가능 → 출고
    if stock["enough"]:
        return {"action": "ship", "ship_qty": quantity, "produce_qty": 0,
                "purchase_plan": [], "reason": "재고 충분하여 전량 출고"}

    # (2) 재고 부족 → 있는 만큼 출고하고, 부족분은 생산 시도
    ship_qty    = stock["available"]
    produce_qty = stock["shortage"]
    prod = can_produce(product_id, produce_qty)     # 자재(BOM) 충분한가?

    if prod["producible"]:
        return {"action": "produce", "ship_qty": ship_qty,
                "produce_qty": produce_qty, "purchase_plan": [],
                "reason": f"{produce_qty}개 생산 (자재 충분)"}

    # (3) 생산 자재도 부족 → 구매발주 후 생산
    purchase_plan = plan_purchase(product_id, produce_qty)
    return {"action": "purchase", "ship_qty": ship_qty,
            "produce_qty": produce_qty, "purchase_plan": purchase_plan,
            "reason": f"{produce_qty}개 생산에 자재 부족 → 구매발주 후 생산"}