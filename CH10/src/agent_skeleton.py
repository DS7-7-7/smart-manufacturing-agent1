# -*- coding: utf-8 -*-
"""
agent_skeleton.py — 10장 실습: AI 에이전트 뼈대 구조
========================================================

에이전트의 4대 요소를 모두 구현한 최소 뼈대다.

    1) 프로파일링 (Profile)   : 시스템 프롬프트로 역할 부여
    2) 메모리 (Memory)        : 대화 이력을 유지
    3) 계획 (Planning)        : LLM 이 도구 사용 여부를 스스로 판단
    4) 도구 (Tools)           : tools.py 에서 정의한 계산기·재고조회

에이전트는 사용자 요청을 받으면 다음 순서로 작동한다.
    사용자 질문 → LLM 판단 → 도구 호출 결정 → 도구 실행 → 결과 관찰 → 최종 답변

실행:
    python3 agent_skeleton.py                # 대화형 실행
    python3 agent_skeleton.py --once "P-2201 재고와 가격 알려줘"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 상위 폴더의 llm_client import
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from llm_client import chat

from tools import TOOLS, get_tool, format_tools_description


# ---------------------------------------------------------------------------
# 1) 프로파일링 — 시스템 프롬프트
# ---------------------------------------------------------------------------
def build_system_prompt() -> str:
    """에이전트의 정체성과 도구 사용 규칙을 정의."""
    return f"""당신은 제조 현장의 자재 관리 담당 AI 에이전트다.
사용자의 요청을 이해하고, 필요하면 아래 도구를 스스로 선택해 사용한다.

[사용 가능한 도구]
{format_tools_description()}

[응답 규칙]
1) 도구가 필요하면 다음 JSON 형식으로만 답한다.
   {{"action": "tool_call", "tool": "도구이름", "args": "인자"}}

2) 도구 사용이 끝나 최종 답변을 할 준비가 되면 다음 형식으로 답한다.
   {{"action": "final_answer", "answer": "사용자에게 전달할 답변"}}

3) 다른 형식으로 답하지 않는다. JSON 만 반환한다.
"""


# ---------------------------------------------------------------------------
# 2) 메모리 — 대화 이력 유지
# ---------------------------------------------------------------------------
class Memory:
    """짧은 대화 이력을 유지하는 단기 메모리."""

    def __init__(self):
        self.messages: list[dict] = []

    def add(self, role: str, content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def as_prompt(self) -> str:
        """메모리 내용을 프롬프트용 문자열로 변환."""
        lines = []
        for m in self.messages:
            lines.append(f"[{m['role']}] {m['content']}")
        return "\n".join(lines)

    def reset(self) -> None:
        self.messages.clear()


# ---------------------------------------------------------------------------
# 3) 계획 — LLM 응답을 파싱해 도구 호출 여부 판단
# ---------------------------------------------------------------------------
def parse_action(llm_response: str) -> dict:
    """LLM 응답에서 JSON 액션을 추출."""
    # 코드 블록 마크 제거
    text = llm_response.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]

    # JSON 부분만 추출
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return {"action": "final_answer", "answer": llm_response}

    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {"action": "final_answer", "answer": llm_response}


# ---------------------------------------------------------------------------
# 4) 도구 실행
# ---------------------------------------------------------------------------
def execute_tool(tool_name: str, args: str) -> str:
    """도구 이름으로 조회해서 실행."""
    tool = get_tool(tool_name)
    if tool is None:
        return f"오류: '{tool_name}' 도구를 찾을 수 없다."
    try:
        return tool["run"](args)
    except Exception as e:
        return f"도구 실행 오류: {e}"


# ---------------------------------------------------------------------------
# 에이전트 메인 루프
# ---------------------------------------------------------------------------
def run_agent(user_request: str, memory: Memory, max_steps: int = 5) -> str:
    """에이전트를 실행해 최종 답변을 반환.

    다음 사이클을 최대 max_steps 번 반복한다.
        LLM 호출 → 액션 파싱 → 도구 실행 or 최종 답변
    """
    system = build_system_prompt()
    memory.add("user", user_request)

    for step in range(1, max_steps + 1):
        print(f"\n  [Step {step}] LLM 판단 중...")

        # LLM 에게 현재까지의 상황을 전달
        user_prompt = (
            f"이전 대화:\n{memory.as_prompt()}\n\n"
            f"다음 액션을 JSON 형식으로 결정하라."
        )
        response = chat(system, user_prompt, temperature=0.1, max_tokens=400)
        action = parse_action(response)

        # 액션에 따라 분기
        if action.get("action") == "tool_call":
            tool_name = action.get("tool", "")
            tool_args = action.get("args", "")
            print(f"  [도구 호출] {tool_name}({tool_args!r})")

            result = execute_tool(tool_name, str(tool_args))
            print(f"  [도구 결과]\n    " + result.replace("\n", "\n    "))

            # 도구 결과를 메모리에 추가
            memory.add(
                "tool_result",
                f"{tool_name}({tool_args}) → {result}",
            )

        elif action.get("action") == "final_answer":
            answer = action.get("answer", "")
            memory.add("agent", answer)
            return answer

        else:
            # 형식 오류 시 원본 응답을 그대로 반환
            return response

    return "(최대 반복 횟수 초과 — 답변을 만들지 못함)"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", type=str, default=None, help="1회성 요청")
    ap.add_argument("--max-steps", type=int, default=5, help="최대 반복 횟수")
    args = ap.parse_args()

    memory = Memory()

    if args.once:
        print(f"[요청] {args.once}")
        answer = run_agent(args.once, memory, max_steps=args.max_steps)
        print(f"\n[최종 답변] {answer}")
        return

    # 대화형 모드
    print("=" * 60)
    print("자재 관리 에이전트 (프로파일링 + 메모리 + 계획 + 도구)")
    print("종료: exit / quit / 종료")
    print("초기화: reset")
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

        if request.lower() == "reset":
            memory.reset()
            print("[메모리 초기화]")
            continue

        if not request:
            continue

        try:
            answer = run_agent(request, memory, max_steps=args.max_steps)
            print(f"\n[답변] {answer}")
        except Exception as e:
            print(f"[오류] {e}")


if __name__ == "__main__":
    main()
