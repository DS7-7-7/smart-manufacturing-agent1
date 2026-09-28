"""
main.py - 실행 진입점

사용 예:
  # 로컬 Ollama (기본)
  python main.py

  # 모델 바꾸기
  OLLAMA_MODEL=qwen3:30b python main.py

  # OpenAI API 사용
  LLM_BACKEND=gpt OPENAI_API_KEY=sk-... python main.py

  (백엔드는 환경변수 LLM_BACKEND 로 선택: ollama | gpt.
   설정은 공용 llm_client.py 한 곳에만 있다.)
"""

from __future__ import annotations
import argparse
import json

from shared_context import SharedManufacturingContext
from agents import ProductionPlanningAgent, MaterialProcurementAgent
from orchestrator import NegotiationOrchestrator
import evaluate


def parse_args():
    p = argparse.ArgumentParser(description="Multi-Agent 생산계획 협상 시뮬레이션")
    p.add_argument("--max-turns", type=int, default=8,
                   help="최대 협상 턴 수 (Deadlock 방지 상한)")
    p.add_argument("--save-log", default="negotiation_log.json",
                   help="대화 로그 저장 경로")
    return p.parse_args()


def main():
    import os
    args = parse_args()

    # 1. 공유 제조 환경 구성
    ctx = SharedManufacturingContext().build_sample_scenario()

    # 2. Agent 생성
    #    LLM 백엔드는 llm_client 가 환경변수(LLM_BACKEND)로 처리하므로
    #    에이전트별로 주입할 필요가 없다.
    production_agent = ProductionPlanningAgent(ctx)
    procurement_agent = MaterialProcurementAgent(ctx)

    # 3. Orchestrator 실행 (협상 루프)
    orchestrator = NegotiationOrchestrator(
        ctx, production_agent, procurement_agent, max_turns=args.max_turns)

    backend = os.environ.get("LLM_BACKEND", "ollama")
    print("=" * 70)
    print(" Multi-Agent 생산계획 협상 시뮬레이션 시작")
    print(f" LLM 백엔드: {backend}")
    print("=" * 70)

    final_schedule = orchestrator.run()

    # 4. 결과 표시
    evaluate.print_summary(ctx, final_schedule, orchestrator.outcome)

    # 대화 로그 저장 (턴별로 무슨 메시지가 오갔는지 복기 가능)
    with open(args.save_log, "w", encoding="utf-8") as f:
        json.dump(orchestrator.conversation_log, f,
                  ensure_ascii=False, indent=2, default=str)
    print(f"\n[대화 로그 저장됨] {args.save_log}")


if __name__ == "__main__":
    main()