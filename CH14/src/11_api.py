# -*- coding: utf-8 -*-
"""
11_api.py
=========
FastAPI 기반 Order Agent 서비스 (확장 실습)

콘솔 Agent를 HTTP API로 확장한다.

    Client → FastAPI → Order Agent / LangGraph → ERP Tools → ERP DB

실행
    cd src
    LLM_BACKEND=mock uvicorn 11_api:app --reload --port 8000
    (모듈명이 숫자로 시작하므로 파일명을 그대로 uvicorn 대상에 지정)

    문서(Swagger): http://localhost:8000/docs

엔드포인트
    POST /orders          주문 처리 (Agent)
    POST /orders/workflow 주문 처리 (LangGraph)
    GET  /inventory/{pid} 재고 조회
    POST /seed            DB 초기화(시드)
    GET  /health          상태 확인
"""

from __future__ import annotations

from importlib import import_module

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

seed = import_module("02_seed_data")
tools = import_module("05_erp_tools")
agent = import_module("07_order_agent")
workflow = import_module("08_workflow")


app = FastAPI(
    title="제조 주문 처리 Agent API",
    description="제14장 종합 실습 — LLM Agent + ERP + LangGraph",
    version="1.0.0",
)


# ===========================================================================
# 요청/응답 스키마
# ===========================================================================
class OrderIn(BaseModel):
    product: str = Field(..., description="제품 코드 또는 제품명", examples=["RC700"])
    quantity: int = Field(..., gt=0, examples=[500])
    customer_id: str = Field(default="C001")


class NLOrderIn(BaseModel):
    """자연어 주문 입력."""
    text: str = Field(..., examples=["신제품 로봇청소기 500개 주문해줘."])
    customer_id: str = Field(default="C001")


# ===========================================================================
# 엔드포인트
# ===========================================================================
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/seed")
def do_seed():
    """DB를 시드 데이터로 초기화한다."""
    seed.seed()
    return {"result": "seeded"}


@app.get("/inventory/{product_id}")
def read_inventory(product_id: str, required: int = 0):
    inv = tools.get_inventory(product_id, required_qty=required)
    if inv is None:
        raise HTTPException(status_code=404, detail=f"'{product_id}' 재고 없음")
    return inv


@app.post("/orders")
def create_order_api(body: OrderIn):
    """
    구조화된 주문 처리 (Agent 모드).
    예: {"product": "RC700", "quantity": 500}
    """
    text = f"{body.product} {body.quantity}개 주문"
    result = agent.process_order(text, customer_id=body.customer_id, verbose=False)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason", "처리 실패"))
    return result


@app.post("/orders/nl")
def create_order_nl(body: NLOrderIn):
    """자연어 주문 처리 (Agent 모드)."""
    result = agent.process_order(body.text, customer_id=body.customer_id, verbose=False)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("reason", "처리 실패"))
    return result


@app.post("/orders/workflow")
def create_order_workflow(body: NLOrderIn):
    """자연어 주문 처리 (LangGraph Workflow 모드)."""
    final = workflow.run_workflow(body.text, customer_id=body.customer_id)
    if final.get("error"):
        raise HTTPException(status_code=400, detail=final["error"])
    # 로그는 응답에서 제외하고 요약만 반환
    return {
        "order_id": final.get("order_id"),
        "action": final.get("action"),
        "ship_qty": final.get("ship_qty"),
        "produce_qty": final.get("produce_qty"),
        "purchases": final.get("purchases", []),
        "production_id": final.get("production_id"),
    }


# ===========================================================================
# 단독 실행 (python 11_api.py 로도 기동 가능)
# ===========================================================================
if __name__ == "__main__":
    import uvicorn
    # 파일명이 숫자로 시작해 import 문자열 대신 app 객체를 직접 전달
    uvicorn.run(app, host="0.0.0.0", port=8000)
