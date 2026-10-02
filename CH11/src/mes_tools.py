# -*- coding: utf-8 -*-
"""
mes_tools.py — 11장 실습: MES / ERP 연동 도구 정의
=====================================================

10장에서는 도구를 자체 형식으로 정의했다면,
11장에서는 OpenAI 표준 Function Calling 스키마 형식으로 정의한다.

각 도구는 JSON Schema 로 파라미터를 정의하고,
LLM 이 이 스키마를 보고 함수 호출을 자동으로 결정한다.

포함된 도구 5개:
    1) get_production_status : MES 생산 오더 조회
    2) get_equipment_status  : MES 설비 상태 조회
    3) check_inventory       : ERP 재고 조회
    4) create_purchase_order : ERP 발주서 생성
    5) send_slack_message    : 정비팀 알림 발송 (가상)

단독 실행:
    python3 mes_tools.py
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
MES_FILE = BASE_DIR / "data" / "mes_data.json"
ERP_FILE = BASE_DIR / "data" / "erp_data.json"


# ---------------------------------------------------------------------------
# 유틸: JSON 파일 읽기/쓰기
# ---------------------------------------------------------------------------
def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(path: Path, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 도구 1: MES 생산 오더 조회
# ---------------------------------------------------------------------------
def get_production_status(line: str = None) -> str:
    """MES 에서 생산 오더 상태를 조회."""
    data = _load(MES_FILE)
    orders = data["production_orders"]

    if line:
        orders = [o for o in orders if o["line"] == line]

    if not orders:
        return f"{line} 라인의 생산 오더를 찾을 수 없다."

    lines = [f"[{o['order_id']}] {o['line']} — {o['product']}\n"
             f"  진행: {o['completed_qty']}/{o['target_qty']} ({o['status']})"
             for o in orders]
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# 도구 2: MES 설비 상태 조회
# ---------------------------------------------------------------------------
def get_equipment_status(line: str) -> str:
    """MES 에서 특정 라인의 설비 상태(온도, 진동 등)를 조회."""
    data = _load(MES_FILE)
    equipment = data["equipment_status"]

    if line not in equipment:
        available = ", ".join(equipment.keys())
        return f"{line} 을(를) 찾을 수 없다. 등록된 라인: {available}"

    e = equipment[line]
    return (
        f"[{line}] 상태: {e['state']}\n"
        f"  온도: {e['temperature']}°C\n"
        f"  진동: {e['vibration']}\n"
        f"  마지막 점검: {e['last_check']}"
    )


# ---------------------------------------------------------------------------
# 도구 3: ERP 재고 조회
# ---------------------------------------------------------------------------
def check_inventory(part_id: str) -> str:
    """ERP 에서 부품 재고를 조회."""
    data = _load(ERP_FILE)
    inventory = data["inventory"]

    part_id = part_id.strip().upper()
    if part_id not in inventory:
        available = ", ".join(inventory.keys())
        return f"부품 {part_id} 을 찾을 수 없다. 등록된 부품: {available}"

    item = inventory[part_id]
    status = "부족" if item["stock"] < item["threshold"] else "정상"
    return (
        f"[{part_id}] {item['name']}\n"
        f"  재고: {item['stock']}개 (임계값: {item['threshold']}개, 상태: {status})\n"
        f"  단가: {item['unit_price']:,}원"
    )


# ---------------------------------------------------------------------------
# 도구 4: ERP 발주서 생성
# ---------------------------------------------------------------------------
def create_purchase_order(part_id: str, quantity: int) -> str:
    """ERP 에 발주서를 생성한다 (실제로 파일에 기록)."""
    data = _load(ERP_FILE)
    inventory = data["inventory"]

    part_id = part_id.strip().upper()
    if part_id not in inventory:
        return f"오류: 부품 {part_id} 을 찾을 수 없다."

    if quantity <= 0:
        return f"오류: 수량은 1 이상이어야 한다 (입력값: {quantity})"

    item = inventory[part_id]
    total_price = item["unit_price"] * quantity

    po_id = f"PO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    new_order = {
        "po_id": po_id,
        "part_id": part_id,
        "part_name": item["name"],
        "quantity": quantity,
        "total_price": total_price,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": "created",
    }
    data["purchase_orders"].append(new_order)
    _save(ERP_FILE, data)

    return (
        f"발주서 생성 완료\n"
        f"  PO 번호: {po_id}\n"
        f"  품목: {item['name']} ({part_id})\n"
        f"  수량: {quantity}개\n"
        f"  총액: {total_price:,}원"
    )


# ---------------------------------------------------------------------------
# 도구 5: 정비팀 Slack 알림 (가상)
# ---------------------------------------------------------------------------
def send_slack_message(recipient: str, message: str) -> str:
    """정비팀 담당자에게 Slack 메시지를 발송한다 (가상 시뮬레이션)."""
    return (
        f"[Slack 발송 완료]\n"
        f"  받는 사람: {recipient}\n"
        f"  메시지: {message}"
    )


# ---------------------------------------------------------------------------
# OpenAI Function Calling 표준 스키마
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_production_status",
            "description": "MES 시스템에서 생산 오더의 진행 상황을 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line": {
                        "type": "string",
                        "description": "조회할 라인 이름 (예: '3라인'). 생략 시 전체 라인 조회.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_equipment_status",
            "description": "특정 라인의 설비 상태(온도, 진동, 가동 여부)를 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "line": {"type": "string", "description": "라인 이름 (예: '3라인')"}
                },
                "required": ["line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_inventory",
            "description": "ERP 에서 부품 ID 로 재고와 단가를 조회한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {"type": "string", "description": "부품 ID (예: 'P-2201')"}
                },
                "required": ["part_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_purchase_order",
            "description": "ERP 에 발주서를 생성한다. 재고 부족 시 자동 발주에 사용.",
            "parameters": {
                "type": "object",
                "properties": {
                    "part_id": {"type": "string", "description": "부품 ID"},
                    "quantity": {"type": "integer", "description": "발주 수량"},
                },
                "required": ["part_id", "quantity"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_slack_message",
            "description": "정비팀 담당자에게 Slack 메시지를 발송한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "recipient": {"type": "string", "description": "받는 사람 이름"},
                    "message": {"type": "string", "description": "발송할 메시지 내용"},
                },
                "required": ["recipient", "message"],
            },
        },
    },
]


# 함수 이름 → 실제 함수 매핑
TOOL_FUNCTIONS = {
    "get_production_status": get_production_status,
    "get_equipment_status": get_equipment_status,
    "check_inventory": check_inventory,
    "create_purchase_order": create_purchase_order,
    "send_slack_message": send_slack_message,
}


# ---------------------------------------------------------------------------
# 단독 실행: 각 도구 테스트
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("[1] MES 생산 오더 조회 (전체)")
    print("=" * 60)
    print(get_production_status())

    print("\n" + "=" * 60)
    print("[2] MES 설비 상태 조회 (3라인)")
    print("=" * 60)
    print(get_equipment_status("3라인"))

    print("\n" + "=" * 60)
    print("[3] ERP 재고 조회 (P-2201)")
    print("=" * 60)
    print(check_inventory("P-2201"))

    print("\n" + "=" * 60)
    print("[4] ERP 발주서 생성 (P-3105, 10개)")
    print("=" * 60)
    print(create_purchase_order("P-3105", 10))

    print("\n" + "=" * 60)
    print("[5] Slack 알림 발송")
    print("=" * 60)
    print(send_slack_message("김정비", "3라인 온도 상승 확인 요망"))

    print("\n" + "=" * 60)
    print(f"[등록된 도구 스키마] {len(TOOL_SCHEMAS)}개")
    print("=" * 60)
    for schema in TOOL_SCHEMAS:
        fn = schema["function"]
        print(f"  {fn['name']}: {fn['description']}")
