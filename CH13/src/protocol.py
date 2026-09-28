"""
3. Protocol (JSON Output)
   - 두 Agent가 주고받는 메시지의 스키마를 정의하고 검증한다.
   - LLM 출력이 자유 텍스트가 아니라 구조화된 JSON이 되도록 강제하는 계약.
"""

from __future__ import annotations
from typing import Dict, List, Any, Tuple

MESSAGE_TYPES = {
    "proposal",         # 새 생산 스케줄 제안
    "counter_proposal",  # 수정 제안
    "accept",           # 합의
    "reject",           # 거절 (사유 필요)
    "info_request",     # 추가 정보 요청
    "info_response",    # 정보 응답
}

REQUIRED_KEYS = {
    "sender",
    "turn",
    "message_type",
    "comment",
}

SCHEDULE_ITEM_KEYS = {"order_id", "product", "quantity", "start_date", "end_date"}


def build_system_protocol_text(agent_role_name: str) -> str:
    """Agent 시스템 프롬프트에 삽입할 '출력 형식 계약' 텍스트."""
    return f"""
[출력 프로토콜]
당신({agent_role_name})은 반드시 아래 JSON 형식으로만 응답해야 합니다.
설명, 마크다운 코드블록, 그 외 텍스트를 절대 포함하지 마세요. 순수 JSON 객체 하나만 출력합니다.

{{
  "sender": "production_planner" 또는 "material_procurement",
  "turn": <int>,
  "message_type": "proposal" | "counter_proposal" | "accept" | "reject" | "info_request" | "info_response",
  "schedule": [
    {{"order_id": "ORD-001", "product": "WidgetA", "quantity": 100, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
  ],
  "adjustments": ["이전 제안 대비 변경한 내용을 사람이 읽을 수 있게 요약"],
  "comment": "협상 상대에게 전달할 핵심 메시지 (한국어, 2~4문장)"
}}

규칙:
- "schedule"은 전체 주문에 대한 최신 생산계획 스냅샷입니다 (증분이 아니라 항상 전체를 다시 작성).
- 합의(accept)하는 경우에도 마지막으로 합의한 schedule을 그대로 포함하세요.
- 자재/능력 제약을 근거 없이 무시하지 마세요. 반드시 상대가 제공한 계산 결과(부족량, 조달 옵션, 능력 위반)를 참고해 조정하세요.
"""


def validate_message(msg: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errors = []
    missing = REQUIRED_KEYS - set(msg.keys())
    if missing:
        errors.append(f"필수 키 누락: {missing}")

    if msg.get("message_type") not in MESSAGE_TYPES:
        errors.append(f"알 수 없는 message_type: {msg.get('message_type')}")

    schedule = msg.get("schedule")
    if schedule is not None:
        if not isinstance(schedule, list):
            errors.append("schedule은 list여야 합니다.")
        else:
            for i, item in enumerate(schedule):
                if not isinstance(item, dict):
                    errors.append(f"schedule[{i}]는 dict여야 합니다.")
                    continue
                missing_keys = SCHEDULE_ITEM_KEYS - set(item.keys())
                if missing_keys:
                    errors.append(f"schedule[{i}] 키 누락: {missing_keys}")

    return (len(errors) == 0), errors
