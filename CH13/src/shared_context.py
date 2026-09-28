"""
1. Shared Manufacturing Context
   - 주문 목록, 자재 재고, BOM, 조달 Lead Time을 보관하는 '진실의 원천(SSOT)'.
   - 생산 계획 Agent / 자재 조달 Agent가 동시에 조회(Read)한다.
   - 실제 상태 변경(재고 선점 등)은 tools.py 를 통해서만 이루어진다.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional
import copy


@dataclass
class Order:
    order_id: str
    product: str
    quantity: int
    due_date: date
    priority: int  # 1(최우선) ~ 5(낮음)
    status: str = "pending"  # pending / scheduled / partial / delayed / rejected


@dataclass
class Material:
    material_id: str
    name: str
    unit: str
    current_stock: float
    reserved: float = 0.0

    @property
    def available(self) -> float:
        return round(self.current_stock - self.reserved, 3)


@dataclass
class Supplier:
    supplier_id: str
    material_id: str
    lead_time_days: int
    max_supply_per_order: float
    unit_cost: float


@dataclass
class ProductionLine:
    product: str
    daily_capacity: int  # 1일 생산 가능 수량


class SharedManufacturingContext:
    """공유 제조 환경. 두 에이전트가 동일 인스턴스(또는 snapshot)를 참조한다."""

    def __init__(self, today: Optional[date] = None):
        self.today: date = today or date.today()
        self.orders: List[Order] = []
        self.materials: Dict[str, Material] = {}
        self.bom: Dict[str, Dict[str, float]] = {}  # product -> {material_id: qty_per_unit}
        self.suppliers: List[Supplier] = []
        self.production_lines: Dict[str, ProductionLine] = {}
        # 재고 선점(Commit) 기록 - tools.reserve_materials 가 기록
        self.reservation_log: List[dict] = []

    # ------------------------------------------------------------------
    # 실습용 샘플 시나리오: 생산계획 vs 자재조달이 반드시 충돌하도록 설계
    # ------------------------------------------------------------------
    def build_sample_scenario(self) -> "SharedManufacturingContext":
        t = self.today

        # 제품 3종, 공통 자재를 나눠 쓰도록 하여 경쟁(충돌) 유발
        self.bom = {
            "WidgetA": {"STEEL": 2.0, "CHIP": 1.0, "CASE": 1.0},
            "WidgetB": {"STEEL": 1.0, "CHIP": 2.0, "CASE": 1.0},
            "WidgetC": {"STEEL": 3.0, "CHIP": 1.0, "CASE": 2.0},
        }

        # 자재 재고: 전체 주문을 동시에 만족시키기엔 의도적으로 부족하게 설정
        self.materials = {
            "STEEL": Material("STEEL", "철강 원자재", "kg", current_stock=400),
            "CHIP": Material("CHIP", "제어 칩", "ea", current_stock=250),
            "CASE": Material("CASE", "외장 케이스", "ea", current_stock=180),
        }

        # 공급업체: 부족분을 리드타임을 두고 보충 가능 (완전 해결은 안 되도록 제한)
        self.suppliers = [
            Supplier("SUP-STEEL-1", "STEEL", lead_time_days=5, max_supply_per_order=150, unit_cost=3.2),
            Supplier("SUP-STEEL-2", "STEEL", lead_time_days=2, max_supply_per_order=60, unit_cost=4.5),  # 긴급/고가
            Supplier("SUP-CHIP-1", "CHIP", lead_time_days=7, max_supply_per_order=100, unit_cost=12.0),
            Supplier("SUP-CASE-1", "CASE", lead_time_days=4, max_supply_per_order=120, unit_cost=2.1),
        ]

        # 생산 라인 능력 (일일 생산 가능 수량)
        self.production_lines = {
            "WidgetA": ProductionLine("WidgetA", daily_capacity=40),
            "WidgetB": ProductionLine("WidgetB", daily_capacity=30),
            "WidgetC": ProductionLine("WidgetC", daily_capacity=20),
        }

        # 주문: 납기가 촉박하고 총 소요 자재가 재고를 초과하도록 설계
        self.orders = [
            Order("ORD-001", "WidgetA", quantity=120, due_date=t + timedelta(days=6), priority=1),
            Order("ORD-002", "WidgetB", quantity=100, due_date=t + timedelta(days=5), priority=2),
            Order("ORD-003", "WidgetC", quantity=60, due_date=t + timedelta(days=10), priority=3),
            Order("ORD-004", "WidgetA", quantity=80, due_date=t + timedelta(days=8), priority=4),
            Order("ORD-005", "WidgetB", quantity=50, due_date=t + timedelta(days=4), priority=1),
        ]
        return self

    # ------------------------------------------------------------------
    def snapshot(self) -> dict:
        """LLM 프롬프트에 주입할 수 있는 읽기 전용 JSON 스냅샷."""
        return {
            "today": self.today.isoformat(),
            "orders": [
                {
                    "order_id": o.order_id,
                    "product": o.product,
                    "quantity": o.quantity,
                    "due_date": o.due_date.isoformat(),
                    "priority": o.priority,
                    "status": o.status,
                }
                for o in self.orders
            ],
            "materials": {
                m.material_id: {
                    "name": m.name,
                    "unit": m.unit,
                    "current_stock": m.current_stock,
                    "reserved": m.reserved,
                    "available": m.available,
                }
                for m in self.materials.values()
            },
            "bom": self.bom,
            "suppliers": [s.__dict__ for s in self.suppliers],
            "production_lines": {
                p: {"daily_capacity": pl.daily_capacity} for p, pl in self.production_lines.items()
            },
        }

    def clone(self) -> "SharedManufacturingContext":
        return copy.deepcopy(self)
