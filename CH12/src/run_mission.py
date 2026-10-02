"""
run_mission.py

에이전트에게 미션을 부여하고 실행한다.
콘솔에 에이전트의 사고 과정이 실시간으로 출력된다.

실행 방법:
  1. 다른 터미널에서 vLLM 서버가 실행 중인지 확인
  2. uv run python run_mission.py
"""

from agent import create_factory_agent


# ============================================================
# 미션 정의
# ============================================================
MISSION = (
    "이번 달 불량률이 3% 증가했다. "
    "어느 라인에서 어떤 원인으로 증가했는지 분석하고, "
    "즉시·단기·재발 방지 세 단계로 대책을 세워라."
)


def main():
    print("=" * 60)
    print("자율 에이전트 미션 실행")
    print("=" * 60)
    print(f"\n미션:\n  {MISSION}\n")
    print("=" * 60)
    print("에이전트 사고 과정 (verbose)")
    print("=" * 60)

    # 에이전트 생성
    executor = create_factory_agent(verbose=True, max_iterations=10)

    # 미션 실행
    try:
        result = executor.invoke({"input": MISSION})
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        return

    # 최종 결론 출력
    print("\n" + "=" * 60)
    print("최종 결론")
    print("=" * 60)
    print(result["output"])

    # 중간 단계 개수 리포트
    steps = result.get("intermediate_steps", [])
    print(f"\n총 {len(steps)}단계의 Thought → Action → Observation 사이클로 결론에 도달했다.")


if __name__ == "__main__":
    main()
