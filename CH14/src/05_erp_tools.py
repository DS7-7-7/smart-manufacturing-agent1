# -*- coding: utf-8 -*-
"""
05_erp_tools.py
===============
Agent가 ERP 시스템과 상호작용하는 Tool 모음

각 Tool은 독립적으로 세션을 열고 닫으며, 결과를 JSON 직렬화 가능한
dict 로 반환한다. (LLM Tool Calling 에서 그대로 주고받기 위함)

조회 Tool (읽기)
    get_product           제품/원자재 정보 조회
    get_inventory         재고 조회 (+ 부족량 계산)
    get_bom               완제품의 자재명세서 조회
    get_supplier          원자재를 공급하는 업체 조회
    get_payment_status    주문의 결제 상태 조회

업무 처리 Tool (쓰기)
    create_order              주문 생성
    create_production_order   생산계획 생성
    create_purchase_order     구매발주 생성
    update_order_status       주문 상태 변경

    Order Agent
        │  Tool Calling
        ▼
    ERP Tools ──▶ ERP DB
"""

from __future__ import annotations

import re
from importlib import import_module
from typing import Optional

erp_models = import_module("03_erp_models")
init_db = import_module("01_init_db")

Product = erp_models.Product
Inventory = erp_models.Inventory
BOM = erp_models.BOM
Supplier = erp_models.Supplier
SupplierProduct = erp_models.SupplierProduct
Order = erp_models.Order
OrderItem = erp_models.OrderItem
Payment = erp_models.Payment
ProductionOrder = erp_models.ProductionOrder
PurchaseOrder = erp_models.PurchaseOrder

OrderStatus = erp_models.OrderStatus
Priority = erp_models.Priority
PaymentStatus = erp_models.PaymentStatus
ProductionStatus = erp_models.ProductionStatus
PurchaseStatus = erp_models.PurchaseStatus


# ===========================================================================
# 조회 Tool (읽기 전용)
# ===========================================================================
def get_product(product_key: str) -> Optional[dict]:
    """
    제품 코드 또는 제품명으로 품목 정보를 조회한다.
    예: get_product("P300"), get_product("신제품 P300")
    """
    with init_db.get_session() as s:
        p = s.get(Product, product_key)
        if p is None:  # 코드로 못 찾으면 이름으로 조회
            p = s.query(Product).filter(Product.name == product_key).first()
        if p is None:
            return None
        return {
            "product_id": p.id,
            "name": p.name,
            "product_type": p.product_type.value,
            "unit_price": p.unit_price,
        }


def _norm(s: str) -> str:
    """비교용 정규화: 소문자 + 공백/하이픈/언더바 제거.
    'RC-700', 'rc 700', 'RC_700' → 'rc700' 으로 통일."""
    return re.sub(r"[\s\-_]", "", s).lower()


def get_all_products(finished_only: bool = True) -> list[dict]:
    """
    제품 목록을 조회한다. Agent가 "사용자가 말한 게 무엇인지" 판단할 때 사용.
    finished_only=True 면 완제품만 반환한다.
    반환: [{product_id, name, product_type}, ...]
    """
    with init_db.get_session() as s:
        q = s.query(Product)
        if finished_only:
            q = q.filter_by(product_type=erp_models.ProductType.FINISHED)
        return [
            {"product_id": p.id, "name": p.name,
             "product_type": p.product_type.value}
            for p in q.all()
        ]


def resolve_product(text: str) -> Optional[dict]:
    """
    코드/이름/부분표현으로 제품을 찾는다. (한글 자연어 주문 대응)
    매칭 단계:
        ① 코드/이름 정확일치 (정규화 후 비교)
        ② 정규화 부분포함: 코드나 이름이 문장 안에 들어있으면 매칭
           - 대소문자 무시:  rc700, RC700, Rc700
           - 구분자 무시:    RC-700, RC 700, RC_700
           - 띄어쓰기 무시:  로봇 청소기 == 로봇청소기
        ③ 부분 코드(숫자) 매칭: 코드 속 숫자(700)가 문장에 있으면 후보로
    * 완제품을 먼저, 이름이 긴 것을 우선하여 오매칭을 줄인다.
    예: resolve_product("청소기 RC700 500개 주문") → RC700
    """
    key = text.strip()
    text_n = _norm(text)   # 정규화된 입력 문장

    with init_db.get_session() as s:
        candidates = s.query(Product).all()
        # 완제품 먼저, 이름 긴 것 먼저 (구체적인 것 우선)
        candidates.sort(
            key=lambda x: (x.product_type.value != "finished", -len(x.name))
        )

        # ① 정확일치 (코드 또는 전체 이름)
        for c in candidates:
            if _norm(c.id) == text_n or _norm(c.name) == text_n:
                return _as_dict(c)

        # ② 정규화 부분포함 (코드 / 전체이름 / 이름의 각 단어)
        for c in candidates:
            code_n = _norm(c.id)
            name_n = _norm(c.name)
            word_ns = [_norm(w) for w in c.name.split() if _norm(w)]
            if (code_n in text_n
                    or name_n in text_n
                    or any(w in text_n for w in word_ns)):
                return _as_dict(c)

        # ③ 부분 코드(숫자) 매칭: 코드에 든 숫자가 문장 숫자와 일치하면 후보
        #    예: 코드 "RC700" 의 700 이 "청소기 700 주문" 에 있으면 매칭
        text_nums = set(re.findall(r"\d+", text))
        for c in candidates:
            code_nums = set(re.findall(r"\d+", c.id))
            if code_nums and code_nums & text_nums:
                return _as_dict(c)

    return None


def _as_dict(p) -> dict:
    """Product 객체 → 표준 dict."""
    return {"product_id": p.id, "name": p.name,
            "product_type": p.product_type.value, "unit_price": p.unit_price}


def get_inventory(product_id: str, required_qty: int = 0) -> Optional[dict]:
    """
    제품의 재고를 조회하고, 요청 수량 대비 부족량을 계산한다.
    required_qty 를 주면 shortage(부족 수량)를 함께 반환한다.
    """
    with init_db.get_session() as s:
        inv = s.query(Inventory).filter_by(product_id=product_id).first()
        if inv is None:
            return None
        shortage = max(0, required_qty - inv.available_stock)
        return {
            "product_id": product_id,
            "current_stock": inv.current_stock,
            "available_stock": inv.available_stock,
            "shortage": shortage,
        }


def get_bom(product_id: str) -> list[dict]:
    """
    완제품의 자재명세서(BOM)를 조회한다.
    예: get_bom("P300") → [{material_id:"Motor", quantity:1}, ...]
    """
    with init_db.get_session() as s:
        rows = s.query(BOM).filter_by(product_id=product_id).all()
        return [
            {"material_id": b.material_id, "quantity": b.quantity}
            for b in rows
        ]


def get_supplier(material_id: str) -> list[dict]:
    """
    특정 원자재를 공급하는 업체 목록을 조회한다 (단가·조달일 포함).
    예: get_supplier("Motor") → [{supplier_id:"S001", unit_price:7500, lead_time_days:5}]
    """
    with init_db.get_session() as s:
        rows = (
            s.query(SupplierProduct)
            .filter_by(material_id=material_id)
            .all()
        )
        return [
            {
                "supplier_id": sp.supplier_id,
                "material_id": sp.material_id,
                "unit_price": sp.unit_price,
                "lead_time_days": sp.lead_time_days,
            }
            for sp in rows
        ]


def get_supplier_info(supplier_id: str) -> Optional[dict]:
    """공급업체 기본 정보(이름·연락처)를 조회한다. 발주서 작성에 사용."""
    with init_db.get_session() as s:
        sup = s.get(Supplier, supplier_id)
        if sup is None:
            return None
        return {"supplier_id": sup.id, "name": sup.name, "contact": sup.contact}


def get_payment_status(order_id: int) -> Optional[dict]:
    """주문의 결제 상태를 조회한다."""
    with init_db.get_session() as s:
        pay = s.query(Payment).filter_by(order_id=order_id).first()
        if pay is None:
            return None
        return {
            "order_id": order_id,
            "total_amount": pay.total_amount,
            "paid_amount": pay.paid_amount,
            "status": pay.status.value,
        }


# ===========================================================================
# 업무 처리 Tool (쓰기)
# ===========================================================================
def create_order(
    product_id: str,
    quantity: int,
    customer_id: Optional[str] = None,
    priority: str = "normal",
) -> dict:
    """
    주문을 생성한다. 주문 + 주문상세 + 결제(미결제) 레코드를 함께 만든다.
    반환: {order_id, status, total_amount}
    """
    with init_db.get_session() as s:
        product = s.get(Product, product_id)
        unit_price = product.unit_price if product else 0.0

        order = Order(
            customer_id=customer_id,
            status=OrderStatus.PENDING,
            priority=Priority(priority),
        )
        s.add(order)
        s.flush()  # order.id 확보

        s.add(OrderItem(order_id=order.id, product_id=product_id, quantity=quantity))

        total = unit_price * quantity
        s.add(Payment(order_id=order.id, total_amount=total,
                      paid_amount=0.0, status=PaymentStatus.UNPAID))

        return {
            "order_id": order.id,
            "status": order.status.value,
            "total_amount": total,
        }


def create_production_order(
    product_id: str,
    quantity: int,
    order_id: Optional[int] = None,
) -> dict:
    """생산계획을 생성한다. 반환: {production_id, product_id, quantity, status}"""
    with init_db.get_session() as s:
        prod = ProductionOrder(
            order_id=order_id,
            product_id=product_id,
            quantity=quantity,
            status=ProductionStatus.PLANNED,
        )
        s.add(prod)
        s.flush()
        return {
            "production_id": prod.id,
            "product_id": product_id,
            "quantity": quantity,
            "status": prod.status.value,
        }


def create_purchase_order(
    supplier_id: str,
    material_id: str,
    quantity: int,
) -> dict:
    """구매발주를 생성한다. 반환: {purchase_id, supplier_id, material_id, quantity, status}"""
    with init_db.get_session() as s:
        po = PurchaseOrder(
            supplier_id=supplier_id,
            material_id=material_id,
            quantity=quantity,
            status=PurchaseStatus.REQUESTED,
        )
        s.add(po)
        s.flush()
        return {
            "purchase_id": po.id,
            "supplier_id": supplier_id,
            "material_id": material_id,
            "quantity": quantity,
            "status": po.status.value,
        }


def update_order_status(order_id: int, status: str) -> Optional[dict]:
    """
    주문 상태를 변경한다.
    status: pending / confirmed / on_hold / shipped / cancelled
    """
    with init_db.get_session() as s:
        order = s.get(Order, order_id)
        if order is None:
            return None
        order.status = OrderStatus(status)
        return {"order_id": order_id, "status": order.status.value}


# ===========================================================================
# Tool 레지스트리 (07_order_agent 에서 Tool Calling 시 참조)
# ===========================================================================
TOOLS = {
    "get_product": get_product,
    "get_all_products": get_all_products,
    "resolve_product": resolve_product,
    "get_inventory": get_inventory,
    "get_bom": get_bom,
    "get_supplier": get_supplier,
    "get_supplier_info": get_supplier_info,
    "get_payment_status": get_payment_status,
    "create_order": create_order,
    "create_production_order": create_production_order,
    "create_purchase_order": create_purchase_order,
    "update_order_status": update_order_status,
}


# ===========================================================================
# 단독 실행 시: 시드 데이터로 각 Tool 동작 확인
# ===========================================================================
if __name__ == "__main__":
    print("[resolve_product] '신제품 로봇청소기 주문':", resolve_product("신제품 로봇청소기 500개 주문"))
    print("[get_product] RC700       :", get_product("RC700"))
    print("[get_inventory] RC700 x500:", get_inventory("RC700", required_qty=500))
    print("[get_bom] RC700           :", get_bom("RC700"))
    print("[get_supplier] MTR01      :", get_supplier("MTR01"))

    print("\n-- 업무 처리 Tool --")
    o = create_order("RC700", 500, customer_id="C001")
    print("[create_order]           :", o)
    print("[get_payment_status]     :", get_payment_status(o["order_id"]))
    print("[create_production_order]:", create_production_order("RC700", 400, o["order_id"]))
    print("[create_purchase_order]  :", create_purchase_order("S001", "MTR01", 100))
    print("[update_order_status]    :", update_order_status(o["order_id"], "confirmed"))
