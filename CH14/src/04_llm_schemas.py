"""
04_llm_models.py
================
LLM Agent 입·출력 데이터 스키마 (Pydantic 2.x)

03_erp_models.py 와의 차이
    03_erp_models.py  →  DB에 "저장되는" 업무 데이터 구조 (SQLAlchemy)
    04_llm_models.py  →  LLM Agent가 "처리/전달하는" 데이터 구조 (Pydantic)

데이터 흐름
    사용자 자연어
        ↓
    OrderRequest        (자연어 → 구조화된 주문 요청)
        ↓
    OrderAnalysis       (주문 분석 결과)
        ↓
    InventoryResult     (재고 조회 결과)
        ↓
    OrderDecision       (출고 / 생산 / 구매 판단)
        ↓
    PurchaseOrderResult (구매발주 결과)
        ↓
    ERP DB

* 이 스키마들은 특정 LLM(Qwen, GPT 등)에 종속되지 않는다.
  어떤 모델을 쓰든 결과를 이 구조로 맞춰서 주고받는다.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 공용 Enum (문자열 값 — LLM이 생성하기 쉽고, ERP 모델과 의미가 일치)
# ---------------------------------------------------------------------------
class Priority(str, Enum):
    NORMAL = "normal"
    URGENT = "urgent"


class PaymentStatus(str, Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"


class DecisionAction(str, Enum):
    """주문 처리 판단 결과."""
    SHIP = "ship"                 # 재고 충분 → 출고
    PRODUCE = "produce"           # 재고 부족, 자재 충분 → 생산
    PURCHASE = "purchase"         # 자재 부족 → 구매발주
    HOLD = "hold"                 # 보류 (부분 결제 등)
    NEED_APPROVAL = "need_approval"  # 관리자 승인 필요 (긴급 등)


# ---------------------------------------------------------------------------
# 1. OrderRequest — 자연어에서 추출한 주문 요청
# ---------------------------------------------------------------------------
class OrderRequest(BaseModel):
    """예: "신제품 P300 500개 주문해줘" → 이 구조로 변환."""
    product_name: str = Field(..., description="제품명 또는 제품 코드 (예: P300)")
    quantity: int = Field(..., gt=0, description="주문 수량 (1 이상)")
    priority: Priority = Field(default=Priority.NORMAL, description="주문 우선순위")

    @field_validator("product_name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("product_name 은 비어 있을 수 없습니다.")
        return v


# ---------------------------------------------------------------------------
# 2. OrderAnalysis — 주문 분석 결과
# ---------------------------------------------------------------------------
class OrderAnalysis(BaseModel):
    """LLM이 주문을 분석해 제품ID/수량/긴급여부/결제상태로 정리한 결과."""
    product_id: str = Field(..., description="확정된 제품 코드 (예: P300)")
    quantity: int = Field(..., gt=0)
    is_urgent: bool = Field(default=False, description="긴급 주문 여부")
    payment_status: PaymentStatus = Field(default=PaymentStatus.UNPAID)


# ---------------------------------------------------------------------------
# 3. InventoryResult — 재고 조회 결과
# ---------------------------------------------------------------------------
class InventoryResult(BaseModel):
    """
    재고 조회 및 부족량 계산 결과.
        shortage = max(0, quantity - available_stock)
    """
    product_id: str
    current_stock: int = Field(..., ge=0, description="현재 재고")
    available_stock: int = Field(..., ge=0, description="가용 재고(예약분 제외)")
    shortage: int = Field(default=0, ge=0, description="부족 수량")

    @property
    def is_enough(self) -> bool:
        """부족분이 없으면 재고 충분."""
        return self.shortage <= 0


# ---------------------------------------------------------------------------
# 4. OrderDecision — 출고 / 생산 / 구매 판단
# ---------------------------------------------------------------------------
class OrderDecision(BaseModel):
    """비즈니스 규칙에 따른 처리 방향 결정."""
    action: DecisionAction = Field(..., description="ship/produce/purchase/hold/need_approval")
    quantity: int = Field(..., ge=0, description="해당 액션의 대상 수량")
    reason: str = Field(..., description="판단 근거 설명")


# ---------------------------------------------------------------------------
# 5. PurchaseOrderItem — 구매발주 항목
# ---------------------------------------------------------------------------
class PurchaseOrderItem(BaseModel):
    material_id: str = Field(..., description="구매할 원자재 코드 (예: Motor)")
    quantity: int = Field(..., gt=0)
    supplier_id: str = Field(..., description="공급업체 코드 (예: S001)")


# ---------------------------------------------------------------------------
# 6. PurchaseOrderResult — 구매발주 결과
# ---------------------------------------------------------------------------
class PurchaseOrderResult(BaseModel):
    supplier_id: str
    items: list[PurchaseOrderItem] = Field(default_factory=list)
    status: Literal["requested", "ordered", "received"] = "requested"


# ---------------------------------------------------------------------------
# 단독 실행 시: 스키마 동작을 예시 데이터로 확인
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 자연어에서 추출된 주문 요청
    req = OrderRequest(product_name="P300", quantity=500, priority="normal")
    print("OrderRequest :", req.model_dump())

    # 재고 결과 (500 요청, 가용 100 → 400 부족)
    inv = InventoryResult(product_id="P300", current_stock=100,
                          available_stock=100, shortage=400)
    print("InventoryResult:", inv.model_dump(), "| 충분?", inv.is_enough)

    # 판단 결과
    dec = OrderDecision(action="produce", quantity=400, reason="재고 부족 400개 생산")
    print("OrderDecision :", dec.model_dump())

    # 구매발주 결과
    po = PurchaseOrderResult(
        supplier_id="S001",
        items=[PurchaseOrderItem(material_id="Motor", quantity=100, supplier_id="S001")],
        status="requested",
    )
    print("PurchaseOrder :", po.model_dump())

    # 검증 실패 예시 (수량 0)
    try:
        OrderRequest(product_name="P300", quantity=0)
    except Exception as e:
        print("검증 동작 확인 (quantity=0 거부):", type(e).__name__)
