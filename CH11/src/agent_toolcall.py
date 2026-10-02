# -*- coding: utf-8 -*-
"""
agent_toolcall.py — 11장 실습: Function Calling 에이전트
===========================================================

OpenAI 표준 Function Calling 스펙을 사용하는 에이전트.
Ollama 는 OpenAI 호환 API 를 제공하므로, Qwen2.5 도 tool_calls 을 반환한다.

10장의 커스텀 JSON 방식과의 차이:
    10장) LLM 이 자유 형식 JSON 을 반환 → 파싱해서 도구 실행
    11장) LLM 이 OpenAI 표준 tool_calls 필드 반환 → 자동 매핑

실행 흐름:
    1) 사용자 요청을 messages 리스트에 추가
    2) LLM 호출 (tools 파라미터에 스키마 전달)
    3) tool_calls 이 있으면 → 각 함수 실행 → 결과를 messages 에 추가 → 2)로 복귀
    4) tool_calls 이 없으면 → 최종 답변 반환

실행:
    python3 agent_toolcall.py
    python3 agent_toolcall.py --once "3라인 상태 확인하고 재고 부족한 부품 발주해"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()

from mes_tools import TOOL_SCHEMAS, TOOL_FUNCTIONS


# ---------------------------------------------------------------------------
# OpenAI 호환 클라이언트 (Ollama 백엔드)
# ---------------------------------------------------------------------------
def create_client():
    """Ollama OpenAI 호환 클라이언트."""
    return OpenAI(
        base_url=os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1"),
        api_key="ollama",
    )


MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")


# ---------------------------------------------------------------------------
# 시스템 프롬프트 (에이전트 정체성)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 제조 현장의 통합 관리 AI 에이전트다.
사용자의 요청을 받으면 MES · ERP 시스템의 도구를 스스로 골라 사용한다.

원칙:
1) 사용자가 명시적으로 요청한 작업만 수행한다.
   조회를 요청하면 조회만 하고, 발주·알림 같은 조치는 실행하지 않는다.
2) 발주·알림은 사용자가 분명히 요청했을 때만 실행한다.
   재고가 부족해도 요청에 없으면 "부족합니다"라고 알리기만 하고 발주하지 않는다.
3) 한 요청에 여러 조회가 필요하면 도구를 여러 번 호출할 수 있다.
4) 모든 작업이 끝나면 사용자에게 한국어로 명확히 요약해서 답한다."""


# ---------------------------------------------------------------------------
# 도구 실행
# ---------------------------------------------------------------------------
def execute_tool_call(tool_call) -> str:
    """LLM 이 요청한 도구를 실행한다."""
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError:
        return f"오류: arguments 파싱 실패 ({tool_call.function.arguments!r})"

    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return f"오류: '{name}' 함수를 찾을 수 없다."

    try:
        return fn(**args)
    except Exception as e:
        return f"실행 오류: {e}"


# ---------------------------------------------------------------------------
# 에이전트 메인 루프
# ---------------------------------------------------------------------------
def run_agent(user_request: str, max_steps: int = 8) -> str:
    """Function Calling 에이전트 실행."""
    client = create_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_request},
    ]

    for step in range(1, max_steps + 1):
        print(f"\n  [Step {step}] LLM 호출...")

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
            temperature=0.1,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        # tool_calls 이 있으면 각각 실행
        if msg.tool_calls:
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                args_str = tc.function.arguments
                print(f"  [도구 호출] {fn_name}({args_str})")

                result = execute_tool_call(tc)
                preview = result[:200] + ("..." if len(result) > 200 else "")
                print(f"  [도구 결과]\n    " + preview.replace("\n", "\n    "))

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue

        # tool_calls 없으면 최종 답변
        return msg.content or "(응답 없음)"

    return "(최대 반복 횟수 초과)"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", type=str, default=None, help="1회성 요청")
    ap.add_argument("--max-steps", type=int, default=8, help="최대 반복")
    args = ap.parse_args()

    if args.once:
        print(f"[요청] {args.once}")
        answer = run_agent(args.once, max_steps=args.max_steps)
        print(f"\n[최종 답변]\n{answer}")
        return

    print("=" * 60)
    print("MES / ERP 통합 관리 에이전트 (Function Calling)")
    print(f"모델: {MODEL}")
    print("종료: exit / quit / 종료")
    print("=" * 60)

    while True:
        try:
            request = input("\n요청> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[종료]")
            break

        if request.lower() in ("exit", "quit", "종료"):
            print("[종료]")
            break

        if not request:
            continue

        try:
            answer = run_agent(request, max_steps=args.max_steps)
            print(f"\n[답변]\n{answer}")
        except Exception as e:
            print(f"[오류] {e}")


if __name__ == "__main__":
    main()
