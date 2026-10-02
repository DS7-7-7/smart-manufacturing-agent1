"""
agent.py

ReAct 프레임워크 기반 자율 에이전트를 생성한다.

에이전트는 다음 사이클을 반복하며 문제를 해결한다:
  Thought (생각) → Action (행동) → Observation (관찰) → 반복 → Final Answer

verbose=True 옵션으로 이 사고 과정이 콘솔에 그대로 출력된다.

LLM 백엔드는 llm_client 모듈의 설정을 그대로 따라간다.
환경변수 LLM_BACKEND (기본 ollama) 로 백엔드를 바꾼다.
  예) LLM_BACKEND=vllm VLLM_MODEL=Qwen/Qwen2.5-14B-Instruct-AWQ python run_mission.py
"""

from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent, AgentExecutor
from langchain.prompts import PromptTemplate

import llm_client
from tools import AGENT_TOOLS


# ============================================================
# ReAct 프롬프트 템플릿 (한국어 커스터마이즈)
# ============================================================
REACT_PROMPT_TEMPLATE = """당신은 스마트 팩토리의 자율 분석 에이전트다.
주어진 미션을 해결하기 위해 아래 도구들을 활용하며 스스로 사고하고 행동한다.

사용 가능한 도구:
{tools}

도구 이름 목록: {tool_names}

다음 형식을 반드시 지켜야 한다:

Question: 당신이 답해야 할 미션
Thought: 다음에 무엇을 해야 할지 생각한다
Action: 사용할 도구 이름 (반드시 [{tool_names}] 중 하나)
Action Input: 도구에 전달할 입력
Observation: 도구가 반환한 결과
... (이 Thought/Action/Observation 사이클을 필요한 만큼 반복)
Thought: 이제 결론을 내릴 수 있다
Final Answer: 최종 답변 (원인 분석과 대책을 명확히 정리)

시작하자.

Question: {input}
Thought: {agent_scratchpad}"""


def create_factory_agent(verbose: bool = True, max_iterations: int = 10):
    """공장 분석용 ReAct 에이전트를 생성한다.

    Args:
        verbose: True면 사고 과정을 콘솔에 출력한다 (실습의 핵심)
        max_iterations: 무한 루프 방지를 위한 최대 반복 횟수

    Returns:
        실행 가능한 AgentExecutor 인스턴스
    """

    # 1. LLM 연결 (llm_client 가 쓰는 백엔드 설정을 그대로 사용)
    cfg = llm_client.backend_config()
    llm = ChatOpenAI(
        model=cfg["model"],
        base_url=cfg["base_url"],
        api_key=cfg["api_key"],
        temperature=0.1,   # 낮게 설정 → 일관된 판단
        max_tokens=2048,
    )

    # 2. 프롬프트 준비
    prompt = PromptTemplate.from_template(REACT_PROMPT_TEMPLATE)

    # 3. ReAct 에이전트 생성
    agent = create_react_agent(
        llm=llm,
        tools=AGENT_TOOLS,
        prompt=prompt,
    )

    # 4. 실행기 감싸기
    executor = AgentExecutor(
        agent=agent,
        tools=AGENT_TOOLS,
        verbose=verbose,                    # 사고 과정 로그 출력 (핵심)
        max_iterations=max_iterations,      # 무한 루프 방지
        handle_parsing_errors=True,         # LLM 출력 파싱 실패 시 재시도
        return_intermediate_steps=True,     # 중간 단계 반환 (분석용)
    )

    return executor
