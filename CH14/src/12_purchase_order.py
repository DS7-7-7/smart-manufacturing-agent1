# -*- coding: utf-8 -*-
"""
12_purchase_order.py
====================
발주서 작성 (방법 A — 작성까지만, 실제 전송 없음)

create_purchase_order() 로 DB에 기록된 발주 건을 바탕으로,
사람이 읽을 수 있는 발주서(텍스트)를 만들어
    ① 콘솔에 출력하고
    ② data/purchase_orders/ 폴더에 .txt 파일로 저장
한다.

* 실제 이메일/팩스 전송은 하지 않는다. "이런 발주서가 나갑니다"를 보여주는 단계.
* 전송 기능(SMTP 등)은 확장 실습으로 이 파일에 나중에 얹을 수 있는 구조로 둔다.
"""

from __future__ import annotations

import os
from datetime import datetime
from importlib import import_module

tools = import_module("05_erp_tools")
init_db = import_module("01_init_db")

# 발주서 저장 폴더: data/purchase_orders/
PO_DIR = os.path.join(init_db.DATA_DIR, "purchase_orders")
os.makedirs(PO_DIR, exist_ok=True)


# ===========================================================================
# 발주서 텍스트 생성
# ===========================================================================
def build_po_document(purchase: dict, requester: str = "생산관리팀") -> str:
    """
    발주 1건(create_purchase_order 반환값)을 발주서 텍스트로 만든다.
    purchase 예:
        {"purchase_id":1, "supplier_id":"S001",
         "material_id":"MTR01", "quantity":100, "status":"requested"}
    """
    supplier = tools.get_supplier_info(purchase["supplier_id"]) or {}
    material = tools.get_product(purchase["material_id"]) or {}

    # 단가·조달일 (공급업체-자재 매칭 정보에서 조회)
    unit_price, lead_time = None, None
    for sp in tools.get_supplier(purchase["material_id"]):
        if sp["supplier_id"] == purchase["supplier_id"]:
            unit_price = sp["unit_price"]
            lead_time = sp["lead_time_days"]
            break

    qty = purchase["quantity"]
    total = (unit_price * qty) if unit_price is not None else None
    today = datetime.now().strftime("%Y-%m-%d")

    lines = []
    lines.append("=" * 50)
    lines.append(f"{'구  매  발  주  서':^44}")
    lines.append("=" * 50)
    lines.append(f"발주번호   : PO-{purchase['purchase_id']:04d}")
    lines.append(f"발주일자   : {today}")
    lines.append(f"요청부서   : {requester}")
    lines.append("-" * 50)
    lines.append(f"공급업체   : {supplier.get('name', purchase['supplier_id'])} "
                 f"({purchase['supplier_id']})")
    lines.append(f"연락처     : {supplier.get('contact', '-')}")
    lines.append("-" * 50)
    lines.append(f"{'품목':<14}{'수량':>8}{'단가':>12}{'금액':>14}")
    lines.append("-" * 50)
    name = material.get("name", purchase["material_id"])
    up = f"{unit_price:,.0f}" if unit_price is not None else "-"
    tp = f"{total:,.0f}" if total is not None else "-"
    lines.append(f"{name:<14}{qty:>8,}{up:>12}{tp:>14}")
    lines.append("-" * 50)
    if total is not None:
        lines.append(f"{'합계 금액':<14}{'':>8}{'':>12}{tp:>14}")
    if lead_time is not None:
        lines.append(f"납품 요청   : 발주일로부터 {lead_time}일 이내")
    lines.append("=" * 50)
    lines.append("※ 본 발주서는 자동 생성되었습니다. (실습용, 실제 전송 없음)")
    lines.append("=" * 50)
    return "\n".join(lines)


# ===========================================================================
# 발주서 발행 (콘솔 출력 + 파일 저장)
# ===========================================================================
def issue_purchase_order(purchase: dict, save: bool = True,
                         verbose: bool = True) -> dict:
    """
    발주 1건에 대한 발주서를 발행(작성)한다.
    반환: {purchase_id, supplier_id, file_path, document}
    """
    doc = build_po_document(purchase)

    if verbose:
        print(doc)

    file_path = None
    if save:
        fname = f"PO-{purchase['purchase_id']:04d}_{purchase['supplier_id']}.txt"
        file_path = os.path.join(PO_DIR, fname)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(doc)
        if verbose:
            print(f"[저장] 발주서 → {file_path}\n")

    return {
        "purchase_id": purchase["purchase_id"],
        "supplier_id": purchase["supplier_id"],
        "file_path": file_path,
        "document": doc,
    }


def issue_all(purchases: list[dict], save: bool = True,
              verbose: bool = True) -> list[dict]:
    """여러 발주 건에 대해 발주서를 일괄 발행한다."""
    return [issue_purchase_order(p, save=save, verbose=verbose) for p in purchases]


# ===========================================================================
# 단독 실행 시: 발주 → 발주서 작성 시연
# ===========================================================================
if __name__ == "__main__":
    seed = import_module("02_seed_data")
    seed.seed()
    print()

    # 발주 2건 생성 후 발주서 발행
    po1 = tools.create_purchase_order("S001", "MTR01", 100)
    po2 = tools.create_purchase_order("S003", "CSE01", 200)
    issue_all([po1, po2])

    print(f"발주서 저장 위치: {PO_DIR}")
