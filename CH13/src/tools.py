"""
4. Agent Tools & State
   - BOM 계산 / 가용성 평가 / 재고 선점(Commit)
   - 두 Agent가 "주장"이 아니라 "계산된 사실"을 근거로 협상하도록 강제하는 계층.
   - Agent(LLM)는 이 모듈의 함수 결과를 프롬프트에 주입받아 판단한다.
"""

from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, List, Tuple

from shared_context import SharedManufacturingContext


ScheduleItem = Dict  # {"order_id","product","quantity","start_date","end_date"}


def calculate_required_materials(ctx: SharedManufacturingContext, schedule: List[ScheduleItem]) -> Dict[str, float]:
    """스케줄(생산 계획안)에 필요한 총 자재량을 BOM 기준으로 합산."""
    required: Dict[str, float] = {}
    for item in schedule:
        product = item["product"]
        qty = item["quantity"]
        bom = ctx.bom.get(product, {})
        for material_id, per_unit in bom.items():
            required[material_id] = required.get(material_id, 0) + per_unit * qty
    return {k: round(v, 3) for k, v in required.items()}


def check_material_shortages(ctx: SharedManufacturingContext, required: Dict[str, float]) -> Dict[str, float]:
    """가용 재고(available) 대비 부족한 자재량. 부족이 없으면 빈 dict."""
    shortages = {}
    for material_id, need in required.items():
        mat = ctx.materials.get(material_id)
        available = mat.available if mat else 0
        if need > available:
            shortages[material_id] = round(need - available, 3)
    return shortages


def check_capacity_violations(ctx: SharedManufacturingContext, schedule: List[ScheduleItem]) -> List[dict]:
    """생산 라인의 일일 능력을 초과하는지 확인 (간이 모델: 총수량/기간 평균으로 체크)."""
    violations = []
    for item in schedule:
        product = item["product"]
        line = ctx.production_lines.get(product)
        if not line:
            continue
        start = date.fromisoformat(item["start_date"])
        end = date.fromisoformat(item["end_date"])
        days = max((end - start).days, 1)
        required_daily = item["quantity"] / days
        if required_daily > line.daily_capacity:
            violations.append(
                {
                    "order_id": item["order_id"],
                    "product": product,
                    "required_daily": round(required_daily, 1),
                    "max_daily_capacity": line.daily_capacity,
                }
            )
    return violations


def estimate_procurement_options(ctx: SharedManufacturingContext, shortages: Dict[str, float]) -> List[dict]:
    """부족 자재에 대해 공급업체별 조달 가능량/리드타임/비용 후보를 제시."""
    options = []
    for material_id, shortage_qty in shortages.items():
        candidates = [s for s in ctx.suppliers if s.material_id == material_id]
        for s in candidates:
            obtainable = min(shortage_qty, s.max_supply_per_order)
            arrival_date = ctx.today + timedelta(days=s.lead_time_days)
            options.append(
                {
                    "material_id": material_id,
                    "supplier_id": s.supplier_id,
                    "shortage_qty": shortage_qty,
                    "obtainable_qty": obtainable,
                    "remaining_after": round(shortage_qty - obtainable, 3),
                    "lead_time_days": s.lead_time_days,
                    "expected_arrival": arrival_date.isoformat(),
                    "unit_cost": s.unit_cost,
                }
            )
    # 리드타임이 짧은 순으로 정렬 (긴급 대응 우선 검토)
    options.sort(key=lambda o: (o["material_id"], o["lead_time_days"]))
    return options


def reserve_materials(ctx: SharedManufacturingContext, order_id: str, required: Dict[str, float]) -> Tuple[bool, Dict[str, float]]:
    """
    재고 선점(Commit). 모든 자재가 충분할 때만 실제로 reserved를 증가시키고 True 반환.
    하나라도 부족하면 아무 것도 변경하지 않고 False + 부족량 반환 (원자적 처리).
    """
    shortages = check_material_shortages(ctx, required)
    if shortages:
        return False, shortages

    for material_id, qty in required.items():
        ctx.materials[material_id].reserved += qty

    ctx.reservation_log.append({"order_id": order_id, "reserved": required})
    return True, {}


def release_materials(ctx: SharedManufacturingContext, order_id: str) -> bool:
    """이미 선점된 자재를 반환 (스케줄 취소/축소 시 사용)."""
    for i, log in enumerate(ctx.reservation_log):
        if log["order_id"] == order_id:
            for material_id, qty in log["reserved"].items():
                ctx.materials[material_id].reserved = max(0, ctx.materials[material_id].reserved - qty)
            ctx.reservation_log.pop(i)
            return True
    return False


def evaluate_schedule(ctx: SharedManufacturingContext, schedule: List[ScheduleItem]) -> dict:
    """생산계획안 하나를 종합 평가 (조달 Agent가 호출하는 핵심 함수)."""
    required = calculate_required_materials(ctx, schedule)
    shortages = check_material_shortages(ctx, required)
    procurement_options = estimate_procurement_options(ctx, shortages) if shortages else []
    capacity_violations = check_capacity_violations(ctx, schedule)
    return {
        "required_materials": required,
        "shortages": shortages,
        "procurement_options": procurement_options,
        "capacity_violations": capacity_violations,
        "feasible": (not shortages) and (not capacity_violations),
    }
