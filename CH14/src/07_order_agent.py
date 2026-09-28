# -*- coding: utf-8 -*-
"""
07_order_agent.py
=================
LLM 기반 Order Agent + Tool Calling

역할
    ① 자연어 주문을 구조화(OrderRequest)로 변환
    ② 필요한 ERP Tool을 선택·호출
    ③ 비즈니스 규칙(06)으로 판단하여 주문 처리 수행

LLM 백엔드
    실제 LLM 호출은 교재 공용 모듈 llm_client.chat() 에 위임한다.
    백엔드 전환은 환경변수 LLM_BACKEND 로 하며, 설정은 llm_client 한 곳에만 있다.
        ollama : 로컬 Ollama (기본)
        gpt    : OpenAI API
        mock   : LLM 없이 규칙 기반 동작 (이 파일에서 처리, 서버·키 불필요)

    → 다른 파일은 이 Agent 만 호출하면 되고,
      모델·서버 교체는 llm_client 설정 또는 환경변수만 바꾸면 된다.
"""

from __future__ import annotations

import os
import re
from importlib import import_module

llm_models = import_module("04_llm_schemas")
tools = import_module("05_erp_tools")
rules = import_module("06_business_rules")

# 교재 공용 LLM 클라이언트 (gpt | ollama)
from llm_client import chat

OrderRequest = llm_models.OrderRequest


# ===========================================================================
# 백엔드 판별
#   - 실제 LLM 호출은 llm_client 가 LLM_BACKEND 를 보고 처리한다.
#   - 이 파일은 'mock'(LLM 없이 규칙 기반) 여부만 따로 판단하면 된다.
# ===========================================================================
_BACKEND = os.environ.get("LLM_BACKEND", "ollama").lower()
_USE_LLM = _BACKEND != "mock"          # mock 이면 LLM 호출을 건너뛴다


# ===========================================================================
# ① 자연어 → 구조화 (주문 분석)
# ===========================================================================
def _mock_analyze(text: str) -> dict:
    """LLM 없이 주문을 파싱 (mock 백엔드용). 제품은 DB에서 매칭."""
    # 수량: "500개 / 500대 / 500세트" 등 단위 우선, 없으면 문장 내 숫자
    m_qty = re.search(r"(\d+)\s*(?:개|대|세트|ea|EA)", text) or re.search(r"(\d+)", text)
    qty = int(m_qty.group(1)) if m_qty else 1
    # 긴급 여부: 명시적 긴급 키워드가 있을 때만 True
    urgent_words = ["긴급", "급하게", "빨리", "서둘", "urgent", "asap", "ASAP"]
    urgent = any(w in text for w in urgent_words)
    # 제품: DB의 제품 코드/이름을 문장에서 찾아 매칭 (한글 이름 대응)
    matched = tools.resolve_product(text)
    product = matched["product_id"] if matched else text.split()[0]
    return {"product_name": product, "quantity": qty,
            "priority": "urgent" if urgent else "normal"}


def analyze_order(text: str) -> OrderRequest:
    """자연어 주문 문장 → OrderRequest."""
    if not _USE_LLM:
        data = _mock_analyze(text)
    else:
        sys = (
            "제조 주문 문장에서 제품명, 수량, 우선순위를 추출해 JSON으로만 반환하라.\n"
            "형식: {\"product_name\": str, \"quantity\": int, "
            "\"priority\": \"normal\"|\"urgent\"}\n"
            "규칙:\n"
            "1. quantity 는 문장에 적힌 숫자를 절대 바꾸지 말고 그대로 정수로 추출한다. "
            "'개','대','세트' 같은 단위는 무시하고 앞의 숫자만 쓴다. "
            "예: '500개'→500, '5000대'→5000, '50세트'→50.\n"
            "2. priority 는 '긴급','급하게','빨리','asap' 등이 있으면 'urgent', 없으면 'normal'.\n"
            "3. product_name 은 문장에 나온 제품명을 그대로 쓴다.\n"
            '예: 입력 "로봇청소기 500개 주문해줘" '
            '→ {"product_name":"로봇청소기","quantity":500,"priority":"normal"}'
        )
        data = chat(sys, text, as_json=True, max_tokens=200)
        if not data:  # LLM 실패 시 규칙 파싱으로 폴백
            data = _mock_analyze(text)
        else:
            # 수량 교차검증: 문장에 명시된 숫자와 LLM 추출값이 다르면 규칙값으로 보정
            #   (LLM이 500을 50으로 잘못 읽는 등의 오독을 방지)
            m = re.search(r"(\d+)\s*(?:개|대|세트|ea|EA)", text) or re.search(r"(\d+)", text)
            if m and int(m.group(1)) != data.get("quantity"):
                data["quantity"] = int(m.group(1))
    return OrderRequest(**data)


# ===========================================================================
# 제품 식별 (LLM 판단 → 규칙 검증 → 폴백)
# ===========================================================================
def identify_product(text: str, product_hint: str = "") -> dict:
    """
    사용자 문장에서 어떤 제품을 말하는지 식별한다.
    반환: {
        "product": {product_id, name, ...} | None,   # 확정 제품
        "candidates": [...],                          # 못 찾았을 때 후보 목록
        "source": "llm" | "rule" | "none"             # 어떤 방법으로 찾았나
    }

    절차:
        ① (LLM 모드) DB 제품 목록을 LLM에게 주고 무엇인지 고르게 함
        ② LLM이 고른 코드를 DB로 검증 → 실제 존재하면 확정
        ③ 실패하면 규칙(resolve_product) 문자열 매칭으로 폴백
        ④ 그래도 없으면 후보 목록과 함께 '없음' 반환 (되묻기용)
    """
    products = tools.get_all_products(finished_only=True)

    # ① + ② LLM 판단 (mock 모드가 아닐 때만)
    if _USE_LLM:
        catalog = "\n".join(f"- {p['product_id']}: {p['name']}" for p in products)
        sys = (
            "사용자의 주문 문장이 아래 제품 목록 중 무엇을 가리키는지 판단하라.\n"
            f"[제품 목록]\n{catalog}\n\n"
            "규칙:\n"
            "1. 반드시 위 목록에 있는 product_id 중 하나만 고른다.\n"
            "2. 축약어나 띄어쓰기 차이도 이해한다. "
            "예: '청정기'→공기청정기, '로봇 청소기'→로봇청소기.\n"
            "3. 목록에서 확신할 수 없으면 product_id 를 'NONE' 으로 한다.\n"
            'JSON으로만 반환: {"product_id":"AP200","confidence":"high"|"low"}'
        )
        user = text if not product_hint else f"{text}\n(추출된 제품명: {product_hint})"
        out = chat(sys, user, as_json=True, max_tokens=100)
        pid = (out.get("product_id") or "").strip() if isinstance(out, dict) else ""
        if pid and pid.upper() != "NONE":
            confirmed = tools.get_product(pid)   # LLM이 고른 코드를 DB로 검증
            if confirmed:
                return {"product": confirmed, "candidates": [], "source": "llm"}

    # ③ 규칙 폴백 (문자열 매칭) — mock 모드는 항상 이 경로
    matched = tools.resolve_product(product_hint) or tools.resolve_product(text)
    if matched:
        return {"product": matched, "candidates": [], "source": "rule"}

    # ④ 못 찾음 → 후보 목록과 함께 반환 (되묻기용)
    return {"product": None, "candidates": products, "source": "none"}


# ===========================================================================
# ② + ③ Tool 호출 + 비즈니스 규칙 기반 주문 처리
# ===========================================================================
def process_order(text: str, customer_id: str = "C001", verbose: bool = True) -> dict:
    """
    자연어 주문을 받아 전체 처리 흐름을 수행한다.
    반환: 처리 결과 요약 dict
    """
    log = []

    def step(msg):
        log.append(msg)
        if verbose:
            print(msg)

    # 1) 주문 분석
    step(f"[Agent] 주문 분석: {text!r}")
    req = analyze_order(text)
    step(f"[Agent] → 제품={req.product_name}, 수량={req.quantity}, "
         f"우선순위={req.priority.value}")

    # 2) 제품 식별 (LLM 판단 → 규칙 검증 → 폴백)
    ident = identify_product(text, product_hint=req.product_name)
    product = ident["product"]
    if product is None:
        # 못 찾음 → 후보 목록을 담아 되묻기용 결과 반환
        names = ", ".join(f"{p['name']}" for p in ident["candidates"])
        step(f"[Agent] '{req.product_name}' 을(를) 특정할 수 없습니다. "
             f"다음 중 무엇인가요? → {names}")
        return {
            "success": False,
            "reason": "제품 특정 불가",
            "need_clarification": True,      # 되물음이 필요함을 표시
            "candidates": ident["candidates"],
            "log": log,
        }
    pid = product["product_id"]
    step(f"[Tool] 제품 식별({ident['source']}) → {pid} ({product['name']})")

    # 3) 주문 생성
    order = tools.create_order(pid, req.quantity, customer_id=customer_id,
                               priority=req.priority.value)
    oid = order["order_id"]
    step(f"[Tool] create_order() → 주문 #{oid}, 금액 {order['total_amount']:,.0f}원")

    # 4) 재고 조회
    inv = tools.get_inventory(pid, required_qty=req.quantity)
    step(f"[Tool] get_inventory() → 가용 {inv['available_stock']}, 부족 {inv['shortage']}")

    # 5) 비즈니스 규칙으로 처리 방향 결정
    decision = rules.decide_order(pid, req.quantity)
    step(f"[Agent] 판단: {decision['action']} — {decision['reason']}")

    result = {
        "success": True,
        "order_id": oid,
        "product_id": pid,
        "action": decision["action"],
        "ship_qty": decision["ship_qty"],
        "produce_qty": decision["produce_qty"],
        "purchases": [],
        "production_id": None,
        "log": log,
    }

    # 6) 액션 실행
    if decision["action"] == "ship":
        tools.update_order_status(oid, "shipped")
        step(f"[Tool] update_order_status() → shipped ({decision['ship_qty']}개 출고)")

    else:
        # 자재 부족분이 있으면 먼저 구매발주 + 발주서 작성
        po_writer = import_module("12_purchase_order")  # 지연 import (순환 방지)
        for p in decision["purchase_plan"]:
            if p.get("supplier_id"):
                po = tools.create_purchase_order(
                    p["supplier_id"], p["material_id"], p["quantity"])
                result["purchases"].append(po)
                step(f"[Tool] create_purchase_order() → {p['material_id']} "
                     f"{p['quantity']}개 @ {p['supplier_id']}")
                # 발주서 작성 (파일로 저장, 콘솔 출력은 생략)
                issued = po_writer.issue_purchase_order(po, save=True, verbose=False)
                step(f"[Tool] 발주서 작성 → {issued['file_path']}")
        # 생산계획 생성
        prod = tools.create_production_order(pid, decision["produce_qty"], oid)
        result["production_id"] = prod["production_id"]
        step(f"[Tool] create_production_order() → 생산 #{prod['production_id']} "
             f"({decision['produce_qty']}개)")
        tools.update_order_status(oid, "confirmed")
        step("[Tool] update_order_status() → confirmed")

    step("[Agent] 주문 처리가 완료되었습니다.")
    return result


# ===========================================================================
# 단독 실행 시: 전체 흐름 시연
# ===========================================================================
if __name__ == "__main__":
    print(f"[LLM_BACKEND] {_BACKEND}\n")
    process_order("신제품 로봇청소기 500개 주문해줘.")
