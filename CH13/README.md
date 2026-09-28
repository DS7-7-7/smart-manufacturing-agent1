# Multi-Agent 생산계획 협상 시뮬레이션
13.'생산 계획 에이전트'와 '자재 조달 에이전트'를 각각 만들어, 둘이 서로 실시간 재고 
상황을 두고 대화(협상)해가며 최적의 생산 스케줄을 짜는 가상 오피스 시뮬레이션 
실습 문서(`[실습 13]`)의 아키텍처를 그대로 코드 레이어로 매핑한 구현체입니다.

```
1. Shared Manufacturing Context   -> shared_context.py
2. 생산 계획 / 자재 조달 Agent    -> agents.py
3. Protocol (JSON Output)         -> protocol.py
4. Agent Tools & State            -> tools.py
5. Multi-Agent Orchestrator Loop  -> orchestrator.py
6. Evaluation & Display           -> evaluate.py
LLM 백엔드 추상화 (Anthropic/로컬) -> llm_client.py
진입점                             -> main.py
```
## 동작 개요

1. `shared_context.py`가 의도적으로 **자재 재고 < 전체 주문 소요량**이 되는 시나리오를 생성합니다.
2. 오케스트레이터가 초기 스케줄(주문 그대로)을 만들고 협상을 시작합니다.
3. 매 턴:
   - 생산 계획 Agent(LLM)가 스케줄을 JSON으로 제안/수정합니다.
   - 자재 조달 Agent는 **LLM에 묻기 전에 `tools.py`로 실제 계산**(BOM 소요량, 부족량,
     공급업체 조달 옵션, 생산 능력 위반)을 수행합니다.
   - 계산상 문제가 없으면 즉시 승인(accept) 후 재고를 선점(commit)하고 종료합니다.
   - 문제가 있으면 그 계산 결과를 LLM(조달 Agent)에게 근거로 제공해 `counter_proposal`/`reject`를
     생성하고, 생산 계획 Agent에게 피드백으로 전달합니다.
4. **Deadlock 방지**: 동일한 자재 부족 패턴이 연속 N턴(기본 2턴) 반복되거나 `--max-turns`에
   도달하면, 오케스트레이터가 우선순위(priority) 기반 규칙으로 낮은 우선순위 주문부터
   수량을 강제 삭감해 실행 가능한 스케줄을 확정합니다.
5. `evaluate.py`가 최종 스케줄 표, 텍스트 간트차트, 자재 활용 현황, 주문별 충족률을 출력합니다.
6. 전체 대화 로그는 `negotiation_log.json`에 저장되어 턴별로 복기할 수 있습니다.

## 확장 아이디어(실습 응용)

- `shared_context.build_sample_scenario()`의 주문/재고/리드타임 숫자를 바꿔가며
  협상 난이도(충돌 강도)를 조절해볼 수 있습니다.
- `protocol.py`의 `MESSAGE_TYPES`에 `expedite_request`(긴급 조달 요청) 같은 타입을 추가하고
  `agents.py`의 시스템 프롬프트에 대응 규칙을 넣어 협상 전략을 다양화할 수 있습니다.
- `orchestrator._force_resolution()`의 규칙(우선순위 기반 20% 삭감)을 다른 정책
  (예: 납기 임박 순, 마진 순)으로 교체해볼 수 있습니다.
- 세 번째 Agent(예: 영업 Agent - 고객에게 납기 재협상)를 추가해 3자 협상 구조로 확장 가능합니다.
