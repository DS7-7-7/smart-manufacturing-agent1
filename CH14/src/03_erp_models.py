"""
03_erp_models.py
================
가상 ERP 시스템의 데이터 모델 정의 (SQLAlchemy 2.0 Declarative)

이 파일은 DB에 "실제로 저장되는 업무 데이터"의 구조를 정의한다.
LLM Agent가 주고받는 데이터 스키마(04_llm_models.py, Pydantic)와는 역할이 다르다.

    03_erp_models.py  →  DB에 저장되는 업무 데이터 구조 (SQLAlchemy)
    04_llm_models.py  →  LLM이 처리/전달하는 데이터 구조 (Pydantic)

정의 테이블 (총 11개):
    customers            고객
    products             품목 (완제품 + 원자재 통합)
    inventory            재고
    orders               주문
    order_items          주문 상세
    bom                  자재명세서 (완제품 → 원자재 구성)
    suppliers            공급업체
    supplier_products    공급업체별 공급 가능 원자재
    production_orders     생산계획
    purchase_orders      구매발주
    payments             결제
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    ForeignKey,
    String,
    Integer,
    Float,
    DateTime,
    Enum as SAEnum,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    """모든 ERP 모델의 공통 부모 클래스."""
    pass


def _now() -> datetime:
    """생성 시각 기본값 (UTC)."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enum 정의 (상태값을 문자열로 고정하여 오타/임의값을 방지)
# ---------------------------------------------------------------------------
class ProductType(str, PyEnum):
    """품목 구분: 완제품 / 원자재."""
    FINISHED = "finished"   # 완제품 (예: P300)
    MATERIAL = "material"   # 원자재 (예: Motor, PCB, Case)


class OrderStatus(str, PyEnum):
    """주문 상태."""
    PENDING = "pending"        # 접수
    CONFIRMED = "confirmed"    # 검증 완료
    ON_HOLD = "on_hold"        # 보류 (부분 결제 등)
    SHIPPED = "shipped"        # 출고
    CANCELLED = "cancelled"    # 취소


class Priority(str, PyEnum):
    """주문 우선순위."""
    NORMAL = "normal"
    URGENT = "urgent"


class PaymentStatus(str, PyEnum):
    """결제 상태."""
    UNPAID = "unpaid"        # 미결제
    PARTIAL = "partial"      # 부분 결제
    PAID = "paid"            # 완납


class ProductionStatus(str, PyEnum):
    """생산계획 상태."""
    PLANNED = "planned"          # 계획
    IN_PROGRESS = "in_progress"  # 진행
    COMPLETED = "completed"      # 완료


class PurchaseStatus(str, PyEnum):
    """구매발주 상태."""
    REQUESTED = "requested"    # 발주 요청
    ORDERED = "ordered"        # 발주 완료
    RECEIVED = "received"      # 입고 완료


# ---------------------------------------------------------------------------
# 1. Customer — 고객
# ---------------------------------------------------------------------------
class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)   # 예: C001
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # 관계: 한 고객은 여러 주문을 가질 수 있음
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.id} {self.name}>"


# ---------------------------------------------------------------------------
# 2. Product — 품목 (완제품 + 원자재 통합)
# ---------------------------------------------------------------------------
class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)   # 예: P300, Motor
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    product_type: Mapped[ProductType] = mapped_column(
        SAEnum(ProductType), default=ProductType.FINISHED, nullable=False
    )
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    # 관계
    inventory: Mapped["Inventory"] = relationship(
        back_populates="product", uselist=False
    )
    # BOM: 이 제품이 "완제품"으로서 갖는 구성 자재 목록
    bom_items: Mapped[list["BOM"]] = relationship(
        back_populates="product",
        foreign_keys="BOM.product_id",
    )

    def __repr__(self) -> str:
        return f"<Product {self.id} {self.name} ({self.product_type.value})>"


# ---------------------------------------------------------------------------
# 3. Inventory — 재고
# ---------------------------------------------------------------------------
class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id"), unique=True, nullable=False
    )
    current_stock: Mapped[int] = mapped_column(Integer, default=0)   # 현재 재고
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0)  # 예약(할당) 재고
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    product: Mapped["Product"] = relationship(back_populates="inventory")

    @property
    def available_stock(self) -> int:
        """가용 재고 = 현재 재고 - 예약 재고."""
        return self.current_stock - self.reserved_stock

    def __repr__(self) -> str:
        return f"<Inventory {self.product_id} stock={self.current_stock}>"


# ---------------------------------------------------------------------------
# 4. Order — 주문
# ---------------------------------------------------------------------------
class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), default=OrderStatus.PENDING, nullable=False
    )
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority), default=Priority.NORMAL, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payment: Mapped["Payment"] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order #{self.id} {self.status.value} {self.priority.value}>"


# ---------------------------------------------------------------------------
# 5. OrderItem — 주문 상세
# ---------------------------------------------------------------------------
class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<OrderItem order={self.order_id} {self.product_id} x{self.quantity}>"


# ---------------------------------------------------------------------------
# 6. BOM — 자재명세서 (완제품 → 구성 원자재)
# ---------------------------------------------------------------------------
class BOM(Base):
    """
    P300 완제품 1개를 만들 때 필요한 원자재 구성.
        product_id  = 완제품 (P300)
        material_id = 구성 원자재 (Motor, PCB, Case)
        quantity    = 완제품 1개당 소요 수량
    """
    __tablename__ = "bom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)   # 완제품 1개당 소요량

    product: Mapped["Product"] = relationship(
        back_populates="bom_items", foreign_keys=[product_id]
    )
    material: Mapped["Product"] = relationship(foreign_keys=[material_id])

    def __repr__(self) -> str:
        return f"<BOM {self.product_id} -> {self.material_id} x{self.quantity}>"


# ---------------------------------------------------------------------------
# 7. Supplier — 공급업체
# ---------------------------------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)   # 예: S001
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    contact: Mapped[str | None] = mapped_column(String(100))

    supplied_products: Mapped[list["SupplierProduct"]] = relationship(
        back_populates="supplier"
    )

    def __repr__(self) -> str:
        return f"<Supplier {self.id} {self.name}>"


# ---------------------------------------------------------------------------
# 8. SupplierProduct — 공급업체별 공급 가능 원자재
# ---------------------------------------------------------------------------
class SupplierProduct(Base):
    """어떤 공급업체가 어떤 원자재를, 얼마에, 며칠 만에 공급하는지."""
    __tablename__ = "supplier_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, default=0.0)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7)  # 조달 소요일

    supplier: Mapped["Supplier"] = relationship(back_populates="supplied_products")
    material: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<SupplierProduct {self.supplier_id} -> {self.material_id}>"


# ---------------------------------------------------------------------------
# 9. ProductionOrder — 생산계획
# ---------------------------------------------------------------------------
class ProductionOrder(Base):
    __tablename__ = "production_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ProductionStatus] = mapped_column(
        SAEnum(ProductionStatus), default=ProductionStatus.PLANNED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    product: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<ProductionOrder #{self.id} {self.product_id} x{self.quantity}>"


# ---------------------------------------------------------------------------
# 10. PurchaseOrder — 구매발주
# ---------------------------------------------------------------------------
class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PurchaseStatus] = mapped_column(
        SAEnum(PurchaseStatus), default=PurchaseStatus.REQUESTED, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    supplier: Mapped["Supplier"] = relationship()
    material: Mapped["Product"] = relationship()

    def __repr__(self) -> str:
        return f"<PurchaseOrder #{self.id} {self.supplier_id} {self.material_id} x{self.quantity}>"


# ---------------------------------------------------------------------------
# 11. Payment — 결제
# ---------------------------------------------------------------------------
class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"), unique=True, nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)  # 총 결제 금액
    paid_amount: Mapped[float] = mapped_column(Float, default=0.0)   # 실제 납부 금액
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_now, onupdate=_now
    )

    order: Mapped["Order"] = relationship(back_populates="payment")

    def recompute_status(self) -> PaymentStatus:
        """납부 금액에 따라 결제 상태를 재계산한다."""
        if self.paid_amount <= 0:
            self.status = PaymentStatus.UNPAID
        elif self.paid_amount < self.total_amount:
            self.status = PaymentStatus.PARTIAL
        else:
            self.status = PaymentStatus.PAID
        return self.status

    def __repr__(self) -> str:
        return f"<Payment order={self.order_id} {self.status.value} {self.paid_amount}/{self.total_amount}>"


# ---------------------------------------------------------------------------
# 모듈 단독 실행 시: 모델이 정상적으로 정의되는지 확인
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    tables = list(Base.metadata.tables.keys())
    print(f"정의된 테이블 수: {len(tables)}")
    for t in tables:
        print(f"  - {t}")
