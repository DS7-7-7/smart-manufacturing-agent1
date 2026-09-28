# -*- coding: utf-8 -*-
"""
02_seed_data.py
===============
가상 ERP 실습용 초기 데이터 입력

01_init_db.py 로 생성된 빈 테이블에 실습 시나리오 데이터를 채운다.

제품 구성 (스마트 제조 — 소형 가전, 부품 일부 공유)
    RC700  로봇청소기   = 구동모터 + 메인보드 + 본체케이스
    AP200  공기청정기   = 팬모터   + 메인보드 + 필터 + 본체케이스
    HF100  무선선풍기   = BLDC모터 + 제어보드 + 날개 + 배터리팩
    VC500  무선청소기   = 구동모터 + 제어보드 + 배터리팩 + 본체케이스

부품 공유 관계
    구동모터(MTR01) : RC700, VC500
    메인보드(PCB01) : RC700, AP200
    제어보드(PCB02) : HF100, VC500
    본체케이스(CSE01): RC700, AP200, VC500
    배터리팩(BAT01) : HF100, VC500
    → 한 부품이 부족하면 여러 제품 생산에 영향을 준다.

실습 시나리오 예
    "로봇청소기 500개 주문" → 재고 100개뿐 → 400개 생산 필요
    → 구동모터/본체케이스 부족 → 해당 공급업체에 구매발주
"""

from __future__ import annotations

from importlib import import_module

erp_models = import_module("03_erp_models")
init_db = import_module("01_init_db")

Product = erp_models.Product
Inventory = erp_models.Inventory
BOM = erp_models.BOM
Supplier = erp_models.Supplier
SupplierProduct = erp_models.SupplierProduct
Customer = erp_models.Customer
ProductType = erp_models.ProductType

FIN = ProductType.FINISHED
MAT = ProductType.MATERIAL


def seed() -> None:
    """초기 데이터를 입력한다. (실행 전 DB는 항상 초기화한다)"""

    # 실습 반복 실행을 위해 DB를 깨끗이 초기화한 뒤 데이터를 넣는다.
    init_db.reset_database()

    with init_db.get_session() as s:
        # -------------------------------------------------------------------
        # 1. 고객
        # -------------------------------------------------------------------
        s.add(Customer(id="C001", name="한빛전자", contact="02-000-0000"))

        # -------------------------------------------------------------------
        # 2. 완제품 (finished) — 4종
        # -------------------------------------------------------------------
        s.add_all([
            Product(id="RC700", name="로봇청소기 RC700", product_type=FIN,
                    unit_price=250000, description="스마트 로봇청소기"),
            Product(id="AP200", name="공기청정기 AP200", product_type=FIN,
                    unit_price=180000, description="스마트 공기청정기"),
            Product(id="HF100", name="무선선풍기 HF100", product_type=FIN,
                    unit_price=90000,  description="휴대용 무선선풍기"),
            Product(id="VC500", name="무선청소기 VC500", product_type=FIN,
                    unit_price=320000, description="스틱형 무선청소기"),
        ])

        # -------------------------------------------------------------------
        # 3. 원자재 (material) — 9종 (일부는 여러 제품이 공유)
        # -------------------------------------------------------------------
        s.add_all([
            Product(id="MTR01", name="구동모터",   product_type=MAT, unit_price=18000),
            Product(id="MTR02", name="팬모터",     product_type=MAT, unit_price=12000),
            Product(id="MTR03", name="BLDC모터",   product_type=MAT, unit_price=15000),
            Product(id="PCB01", name="메인보드",   product_type=MAT, unit_price=25000),
            Product(id="PCB02", name="제어보드",   product_type=MAT, unit_price=20000),
            Product(id="CSE01", name="본체케이스", product_type=MAT, unit_price=9000),
            Product(id="FLT01", name="필터",       product_type=MAT, unit_price=6000),
            Product(id="BLD01", name="날개",       product_type=MAT, unit_price=4000),
            Product(id="BAT01", name="배터리팩",   product_type=MAT, unit_price=30000),
        ])

        # -------------------------------------------------------------------
        # 4. 재고
        #    완제품: 신제품이라 재고가 적음 (대량 주문 시 생산 유발)
        #    원자재: 부품별로 재고를 달리하여 출고/생산/발주 분기가 골고루 나오게
        # -------------------------------------------------------------------
        s.add_all([
            # 완제품
            Inventory(product_id="RC700", current_stock=100),
            Inventory(product_id="AP200", current_stock=150),
            Inventory(product_id="HF100", current_stock=500),
            Inventory(product_id="VC500", current_stock=50),
            # 원자재
            Inventory(product_id="MTR01", current_stock=300),   # 구동모터 (RC700,VC500 공유)
            Inventory(product_id="MTR02", current_stock=600),   # 팬모터
            Inventory(product_id="MTR03", current_stock=800),   # BLDC모터
            Inventory(product_id="PCB01", current_stock=500),   # 메인보드 (RC700,AP200 공유)
            Inventory(product_id="PCB02", current_stock=250),   # 제어보드 (HF100,VC500 공유)
            Inventory(product_id="CSE01", current_stock=200),   # 본체케이스 (3제품 공유)
            Inventory(product_id="FLT01", current_stock=1000),  # 필터
            Inventory(product_id="BLD01", current_stock=900),   # 날개
            Inventory(product_id="BAT01", current_stock=180),   # 배터리팩 (HF100,VC500 공유)
        ])

        # -------------------------------------------------------------------
        # 5. BOM (완제품 1대당 구성 부품 수량)
        # -------------------------------------------------------------------
        s.add_all([
            # 로봇청소기
            BOM(product_id="RC700", material_id="MTR01", quantity=1),
            BOM(product_id="RC700", material_id="PCB01", quantity=1),
            BOM(product_id="RC700", material_id="CSE01", quantity=1),
            # 공기청정기
            BOM(product_id="AP200", material_id="MTR02", quantity=1),
            BOM(product_id="AP200", material_id="PCB01", quantity=1),
            BOM(product_id="AP200", material_id="FLT01", quantity=2),  # 필터 2개
            BOM(product_id="AP200", material_id="CSE01", quantity=1),
            # 무선선풍기
            BOM(product_id="HF100", material_id="MTR03", quantity=1),
            BOM(product_id="HF100", material_id="PCB02", quantity=1),
            BOM(product_id="HF100", material_id="BLD01", quantity=1),
            BOM(product_id="HF100", material_id="BAT01", quantity=1),
            # 무선청소기
            BOM(product_id="VC500", material_id="MTR01", quantity=1),
            BOM(product_id="VC500", material_id="PCB02", quantity=1),
            BOM(product_id="VC500", material_id="BAT01", quantity=1),
            BOM(product_id="VC500", material_id="CSE01", quantity=1),
        ])

        # -------------------------------------------------------------------
        # 6. 공급업체
        # -------------------------------------------------------------------
        s.add_all([
            Supplier(id="S001", name="대성모터",     contact="031-111-1111"),
            Supplier(id="S002", name="세종전자",     contact="031-222-2222"),
            Supplier(id="S003", name="한국정밀케이스", contact="031-333-3333"),
            Supplier(id="S004", name="다원필터",     contact="031-444-4444"),
            Supplier(id="S005", name="에너지셀",     contact="031-555-5555"),
        ])

        # -------------------------------------------------------------------
        # 7. 공급업체별 공급 원자재 (단가 / 조달 소요일)
        #    일부 부품은 복수 공급업체가 공급 → 최저가 선택 로직이 의미를 가짐
        # -------------------------------------------------------------------
        s.add_all([
            # 모터류 — 대성모터(S001)
            SupplierProduct(supplier_id="S001", material_id="MTR01", unit_price=17000, lead_time_days=5),
            SupplierProduct(supplier_id="S001", material_id="MTR02", unit_price=11500, lead_time_days=5),
            SupplierProduct(supplier_id="S001", material_id="MTR03", unit_price=14500, lead_time_days=6),
            # 보드류 — 세종전자(S002)
            SupplierProduct(supplier_id="S002", material_id="PCB01", unit_price=24000, lead_time_days=7),
            SupplierProduct(supplier_id="S002", material_id="PCB02", unit_price=19000, lead_time_days=7),
            # 케이스 — 한국정밀케이스(S003)
            SupplierProduct(supplier_id="S003", material_id="CSE01", unit_price=8500,  lead_time_days=3),
            SupplierProduct(supplier_id="S003", material_id="BLD01", unit_price=3800,  lead_time_days=4),
            # 필터 — 다원필터(S004)
            SupplierProduct(supplier_id="S004", material_id="FLT01", unit_price=5500,  lead_time_days=2),
            # 배터리 — 에너지셀(S005)
            SupplierProduct(supplier_id="S005", material_id="BAT01", unit_price=28000, lead_time_days=8),
            # 케이스 2차 공급처(세종전자도 케이스 공급) — 최저가 선택 비교용
            SupplierProduct(supplier_id="S002", material_id="CSE01", unit_price=9200,  lead_time_days=5),
        ])

    print("초기 데이터 입력 완료.")


def show_summary() -> None:
    """입력된 데이터를 요약 출력한다 (확인용)."""
    with init_db.get_session() as s:
        print("\n[완제품]")
        for p in s.query(Product).filter_by(product_type=FIN).all():
            print(f"  {p.id:6} {p.name:14} {p.unit_price:>10,.0f}원")

        print("\n[원자재]")
        for p in s.query(Product).filter_by(product_type=MAT).all():
            print(f"  {p.id:6} {p.name}")

        print("\n[BOM]")
        for fp in s.query(Product).filter_by(product_type=FIN).all():
            parts = s.query(BOM).filter_by(product_id=fp.id).all()
            comp = ", ".join(f"{b.material_id}x{b.quantity}" for b in parts)
            print(f"  {fp.id} = {comp}")

        print("\n[재고]")
        for inv in s.query(Inventory).all():
            print(f"  {inv.product_id:6} {inv.current_stock:>5}개")

        print("\n[공급업체 공급 품목]")
        for sp in s.query(SupplierProduct).all():
            print(f"  {sp.supplier_id} -> {sp.material_id} "
                  f"(단가 {sp.unit_price:,.0f}, {sp.lead_time_days}일)")


if __name__ == "__main__":
    seed()
    show_summary()