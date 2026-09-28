"""
2. 생산 계획 Agent / 자재 조달 Agent
   - System Prompt (목표/역할) + 3.Protocol(JSON Output) 을 결합.
   - 4.Agent Tools 결과를 프롬프트에 주입받아 "근거 기반" 판단을 하도록 구성.

LLM 호출
   - 교재 공용 모듈 llm_client.chat() 에 위임한다.
   - 백엔드 전환은 환경변수 LLM_BACKEND (gpt | ollama) 로 하며,
     설정은 llm_client 한 곳에만 있다.
   - chat() 은 멀티턴 메시지 리스트를 그대로 받으므로 협상 대화에 그대로 쓸 수 있다.
"""

from __future__ import annotations
from typing import Dict, List, Any, Optional
import json
import re

from llm_client import chat            # 교재 공용 LLM 클라이언트 (gpt | ollama)
from protocol import build_system_protocol_text, validate_message
from shared_context import SharedManufacturingContext
import tools as tools


def _extract_json(text: str) -> dict:
    """모델이 코드블록/잡담을 섞어 보내는 경우까지 방어적으로 JSON을 추출."""
    text = text.strip()
    # ```json ... ``` 형태 제거
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    else:
        # 첫 '{' 부터 마지막 '}' 까지만 취함
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    return json.loads(text)


class BaseAgent:
    role_key = "base"
    role_name_kr = "기본 에이전트"

    def __init__(self, ctx: SharedManufacturingContext):
        # LLM 백엔드는 llm_client 가 환경변수로 처리하므로 주입할 필요가 없다.
        self.ctx = ctx
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        raise NotImplementedError

    def decide(
        self,
        turn: int,
        conversation_history: List[Dict[str, str]],
        extra_context: Optional[dict] = None,
        max_retries: int = 2,
    ) -> Dict[str, Any]:
        """LLM 호출 -> JSON 파싱 -> 검증. 실패 시 재시도(형식 오류 피드백 포함)."""
        user_payload = {
            "turn": turn,
            "shared_context_snapshot": self.ctx.snapshot(),
            "tool_results": extra_context or {},
            "instruction": "위 정보를 근거로 다음 턴의 메시지를 JSON으로만 응답하세요.",
        }
        messages = list(conversation_history) + [
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ]

        last_error = None
        for attempt in range(max_retries + 1):
            # 공용 chat() 에 멀티턴 메시지 리스트를 그대로 넘긴다.
            raw = chat(self.system_prompt, messages, max_tokens=1500)
            try:
                parsed = _extract_json(raw)
                ok, errors = validate_message(parsed)
                if ok:
                    return parsed
                last_error = "; ".join(errors)
            except Exception as e:  # noqa: BLE001
                last_error = str(e)

            # 형식 오류를 알려주고 재시도
            messages.append({"role": "assistant", "content": raw})
            messages.append(
                {
                    "role": "user",
                    "content": f"이전 응답이 프로토콜을 위반했습니다: {last_error}\n"
                    f"순수 JSON 객체만 다시 출력하세요.",
                }
            )

        # 재시도 모두 실패 -> 안전한 폴백 메시지 (오케스트레이터가 deadlock으로 처리 가능)
        return {
            "sender": self.role_key,
            "turn": turn,
            "message_type": "info_request",
            "schedule": [],
            "adjustments": [],
            "comment": f"[시스템] JSON 파싱 실패로 폴백 응답 반환. 마지막 오류: {last_error}",
        }


class ProductionPlanningAgent(BaseAgent):
    role_key = "production_planner"
    role_name_kr = "생산 계획 Agent"

    def _build_system_prompt(self) -> str:
        return f"""
당신은 제조기업의 '생산 계획 Agent'입니다.

[역할]
- 고객 주문 확인
- 생산 우선순위 결정
- 생산량 및 생산 순서 결정
- 생산 일정(schedule) 수립

[목표]
납기 지연을 최소화하면서 최대한 많은 주문을 생산한다.

[협상 원칙]
- 자재 조달 Agent가 제시하는 부족량(shortages), 조달 가능 옵션(procurement_options),
  생산 능력 위반(capacity_violations)을 무시하지 말고 스케줄에 반영하세요.
- 자재가 부족하면: (a) 우선순위(priority 숫자가 작을수록 중요)가 낮은 주문의 수량을 줄이거나
  시작일을 늦추거나, (b) 조달 리드타임에 맞춰 생산 시작일을 뒤로 미루는 방식으로 조정하세요.
- 모든 주문을 100% 만족시킬 수 없다면, 우선순위가 높은 주문부터 최대한 보호하고
  그 사실을 comment에 명시하세요.
- 근거 없이 상대 주장을 무시하거나, 동일한 스케줄을 반복 제안하지 마세요.

{build_system_protocol_text("생산 계획 Agent (production_planner)")}
/no_think
"""


class MaterialProcurementAgent(BaseAgent):
    role_key = "material_procurement"
    role_name_kr = "자재 조달 Agent"

    def _build_system_prompt(self) -> str:
        return f"""
당신은 제조기업의 '자재 조달 Agent'입니다.

[역할]
- 현재 자재 재고 확인
- 생산에 필요한 자재 계산 (BOM 기준)
- 부족 자재 확인
- 공급업체의 조달 가능량 및 납기 확인

[목표]
자재 부족이 발생하지 않도록 조달 계획을 수립한다.

[협상 원칙]
- tool_results에 제공되는 required_materials / shortages / procurement_options /
  capacity_violations 계산 결과를 근거로만 판단하세요. 임의로 재고 수치를 지어내지 마세요.
- 부족이 없으면(message_type="accept") 생산계획 Agent의 schedule을 그대로 승인하세요.
- 부족이 있으면 counter_proposal 또는 reject로 응답하되, 어떤 자재가 얼마나 부족하고
  어떤 공급업체를 통해 언제까지 얼마나 조달 가능한지 comment에 요약하세요.
- 조달로 완전히 메울 수 없는 부족분이 있다면, 생산계획 Agent가 수량/일정을 조정하도록
  구체적인 상한선(조달 가능 수량, 예상 도착일)을 제시하세요.

{build_system_protocol_text("자재 조달 Agent (material_procurement)")}
/no_think
"""

    def evaluate_with_tools(self, schedule: List[dict]) -> dict:
        """생산계획 Agent가 제안한 schedule을 실제 계산 도구로 평가."""
        return tools.evaluate_schedule(self.ctx, schedule)