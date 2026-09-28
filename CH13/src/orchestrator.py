"""
5. Multi-Agent Orchestrator Loop
   - 생산 계획 Agent <-> 자재 조달 Agent 간 턴 기반 협상을 제어.
   - Deadlock 방지: (a) 최대 턴 수 제한, (b) 동일 shortage 반복 시 강제 규칙 적용.
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional
import json

from shared_context import SharedManufacturingContext
from agents import ProductionPlanningAgent, MaterialProcurementAgent
import tools as tools


class NegotiationOrchestrator:
    def __init__(
        self,
        ctx: SharedManufacturingContext,
        production_agent: ProductionPlanningAgent,
        procurement_agent: MaterialProcurementAgent,
        max_turns: int = 8,
        deadlock_repeat_threshold: int = 2,
    ):
        self.ctx = ctx
        self.production_agent = production_agent
        self.procurement_agent = procurement_agent
        self.max_turns = max_turns
        self.deadlock_repeat_threshold = deadlock_repeat_threshold

        self.conversation_log: List[Dict[str, Any]] = []
        self._shortage_history: List[frozenset] = []
        self.final_schedule: Optional[List[dict]] = None
        self.outcome: str = "in_progress"  # agreed / deadlock_forced / max_turns_reached

    # ------------------------------------------------------------------
    def _initial_schedule(self) -> List[dict]:
        """생산계획 Agent의 첫 제안 전, 오케스트레이터가 '주문 그대로'를 초안으로 제공."""
        schedule = []
        for o in self.ctx.orders:
            start = self.ctx.today
            # 매우 단순한 초기 일정: 오늘 시작, 납기 전날 종료
            end = o.due_date
            schedule.append(
                {
                    "order_id": o.order_id,
                    "product": o.product,
                    "quantity": o.quantity,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                }
            )
        return schedule

    def _log(self, agent_role: str, msg: dict, tool_result: Optional[dict] = None):
        self.conversation_log.append({"agent": agent_role, "message": msg, "tool_result": tool_result})

    def _is_repeated_deadlock(self, shortages: Dict[str, float]) -> bool:
        key = frozenset(shortages.items())
        self._shortage_history.append(key)
        recent = self._shortage_history[-self.deadlock_repeat_threshold :]
        return len(recent) == self.deadlock_repeat_threshold and len(set(recent)) == 1 and len(key) > 0

    def _force_resolution(self, schedule: List[dict]) -> List[dict]:
        """
        Deadlock 강제 해소 규칙:
        우선순위가 낮은(priority 숫자가 큰) 주문부터 수량을 20%씩 순차적으로 삭감하여
        재고 제약을 만족시킬 때까지 반복. 최소 수량(0) 도달 시 주문 보류(status=rejected).
        """
        priority_map = {o.order_id: o.priority for o in self.ctx.orders}
        working = [dict(item) for item in schedule]

        for _ in range(20):  # 안전 상한
            required = tools.calculate_required_materials(self.ctx, working)
            shortages = tools.check_material_shortages(self.ctx, required)
            if not shortages:
                break
            # 우선순위 낮은(숫자 큰) 순으로 정렬해 가장 덜 중요한 주문부터 삭감
            working.sort(key=lambda it: -priority_map.get(it["order_id"], 99))
            for item in working:
                if item["quantity"] <= 0:
                    continue
                cut = max(1, int(item["quantity"] * 0.2))
                item["quantity"] = max(0, item["quantity"] - cut)
                break
        working = [it for it in working if it["quantity"] > 0]
        return working

    # ------------------------------------------------------------------
    def run(self) -> List[dict]:
        schedule = self._initial_schedule()
        conv_production: List[Dict[str, str]] = []
        conv_procurement: List[Dict[str, str]] = []

        for turn in range(1, self.max_turns + 1):
            # --- 1) 생산계획 Agent 턴 ---
            capacity_check = tools.check_capacity_violations(self.ctx, schedule)
            prod_extra = {"current_schedule": schedule, "capacity_violations": capacity_check}
            prod_msg = self.production_agent.decide(turn, conv_production, extra_context=prod_extra)
            self._log("production_planner", prod_msg)

            if prod_msg.get("schedule"):
                schedule = prod_msg["schedule"]

            conv_production.append({"role": "assistant", "content": json.dumps(prod_msg, ensure_ascii=False)})
            conv_procurement.append(
                {"role": "user", "content": f"[생산계획 Agent 제안]\n{json.dumps(prod_msg, ensure_ascii=False)}"}
            )

            # --- 2) 자재 조달 Agent가 Tool로 실제 평가 ---
            eval_result = self.procurement_agent.evaluate_with_tools(schedule)

            if eval_result["feasible"]:
                # 도구 계산상 문제 없음 -> 자재 선점 후 즉시 합의로 종료
                for item in schedule:
                    required = tools.calculate_required_materials(self.ctx, [item])
                    tools.reserve_materials(self.ctx, item["order_id"], required)
                self.final_schedule = schedule
                self.outcome = "agreed"
                self._log(
                    "material_procurement",
                    {
                        "sender": "material_procurement",
                        "turn": turn,
                        "message_type": "accept",
                        "schedule": schedule,
                        "comment": "자재/능력 제약을 모두 만족하여 최종 승인합니다.",
                    },
                    tool_result=eval_result,
                )
                return schedule

            # --- 3) Deadlock 감지 ---
            if self._is_repeated_deadlock(eval_result["shortages"]):
                forced = self._force_resolution(schedule)
                self.final_schedule = forced
                self.outcome = "deadlock_forced"
                self._log(
                    "orchestrator",
                    {
                        "sender": "orchestrator",
                        "turn": turn,
                        "message_type": "forced_resolution",
                        "schedule": forced,
                        "comment": "동일한 자재 부족이 반복되어 우선순위 기반 강제 조정 규칙을 적용했습니다.",
                    },
                    tool_result=eval_result,
                )
                return forced

            # --- 4) 자재 조달 Agent 응답 (LLM) ---
            proc_extra = {"current_schedule": schedule, **eval_result}
            proc_msg = self.procurement_agent.decide(turn, conv_procurement, extra_context=proc_extra)
            self._log("material_procurement", proc_msg, tool_result=eval_result)

            conv_procurement.append({"role": "assistant", "content": json.dumps(proc_msg, ensure_ascii=False)})
            conv_production.append(
                {"role": "user", "content": f"[자재조달 Agent 피드백]\n{json.dumps(proc_msg, ensure_ascii=False)}"}
            )

            if proc_msg.get("message_type") == "accept":
                final = proc_msg.get("schedule") or schedule
                for item in final:
                    required = tools.calculate_required_materials(self.ctx, [item])
                    tools.reserve_materials(self.ctx, item["order_id"], required)
                self.final_schedule = final
                self.outcome = "agreed"
                return final

        # max_turns 도달 -> 마지막 스케줄을 강제 조정해서 반환
        forced = self._force_resolution(schedule)
        self.final_schedule = forced
        self.outcome = "max_turns_reached"
        return forced
