"""
6. Evaluation & Display
   - 최종 생산 스케줄을 표/간트차트로 표시하고, 자재 활용 현황을 요약한다.
"""

from __future__ import annotations
from datetime import date
from typing import List, Dict

from shared_context import SharedManufacturingContext
import tools as tools


def print_schedule_table(schedule: List[dict], orders_by_id: Dict[str, "Order"]):
    print("\n[최종 생산 스케줄]")
    header = f"{'주문ID':<10}{'제품':<10}{'수량':>8}{'시작일':>12}{'종료일':>12}{'우선순위':>8}{'상태':>10}"
    print(header)
    print("-" * len(header))
    for item in schedule:
        o = orders_by_id.get(item["order_id"])
        original_qty = o.quantity if o else "-"
        status = "전량충족" if o and item["quantity"] >= o.quantity else "부분/조정"
        print(
            f"{item['order_id']:<10}{item['product']:<10}{item['quantity']:>8}"
            f"{item['start_date']:>12}{item['end_date']:>12}"
            f"{(o.priority if o else '-'):>8}{status:>10}  (원주문수량: {original_qty})"
        )


def print_ascii_gantt(schedule: List[dict], today: date):
    print("\n[간트 차트 (일 단위, 텍스트)]")
    if not schedule:
        print("(스케줄 없음)")
        return
    max_end = max(date.fromisoformat(it["end_date"]) for it in schedule)
    horizon = (max_end - today).days + 1
    for item in schedule:
        start = date.fromisoformat(item["start_date"])
        end = date.fromisoformat(item["end_date"])
        offset = max((start - today).days, 0)
        duration = max((end - start).days, 1)
        bar = " " * offset + "█" * duration
        label = f"{item['order_id']}({item['product']},{item['quantity']})"
        print(f"{label:<28}|{bar}")
    print(f"{'':<28}|" + "-" * horizon + f"  (총 {horizon}일)")


def print_material_summary(ctx: SharedManufacturingContext, schedule: List[dict]):
    print("\n[자재 활용 요약]")
    required = tools.calculate_required_materials(ctx, schedule)
    for material_id, mat in ctx.materials.items():
        need = required.get(material_id, 0)
        print(
            f"- {mat.name:<10} 필요:{need:>8.1f}{mat.unit}  "
            f"보유:{mat.current_stock:>8.1f}{mat.unit}  선점:{mat.reserved:>8.1f}{mat.unit}  "
            f"잔여가용:{mat.available:>8.1f}{mat.unit}"
        )


def print_summary(ctx: SharedManufacturingContext, schedule: List[dict], outcome: str):
    orders_by_id = {o.order_id: o for o in ctx.orders}
    print("\n" + "=" * 70)
    print(f" 협상 결과: {outcome}")
    print("=" * 70)
    print_schedule_table(schedule, orders_by_id)
    print_ascii_gantt(schedule, ctx.today)
    print_material_summary(ctx, schedule)

    # 미충족/삭감된 주문 하이라이트
    print("\n[주문별 충족 현황]")
    scheduled_ids = {it["order_id"]: it["quantity"] for it in schedule}
    for o in ctx.orders:
        got = scheduled_ids.get(o.order_id, 0)
        if got >= o.quantity:
            print(f"- {o.order_id}: 100% 충족 ({got}/{o.quantity})")
        elif got > 0:
            print(f"- {o.order_id}: 부분 충족 ({got}/{o.quantity}, {got/o.quantity:.0%})")
        else:
            print(f"- {o.order_id}: 미충족 (0/{o.quantity}) - 이번 스케줄에서 제외됨")
