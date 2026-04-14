"""
Sales objection analyzer for the Sovereign Solar Intelligence Engine.

Processes a collection of SalesCall records and produces:
  - Per-objection-type success rates and best examples
  - Per-agent performance stats
  - Ranked winning moments
  - Coaching recommendations
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from .models import (
    AgentStats,
    CallOutcome,
    ObjectionSummary,
    ObjectionType,
    SalesCall,
    WinningMoment,
    Objection,
)


def load_calls_from_json(path: str | Path) -> list[SalesCall]:
    """Deserialize a list of SalesCall objects from a JSON file."""
    with open(path, "r") as fh:
        raw = json.load(fh)
    return [_call_from_dict(c) for c in raw]


def _call_from_dict(d: dict) -> SalesCall:
    objections = [
        Objection(
            type=ObjectionType(o["type"]),
            raw_text=o["raw_text"],
            handled_successfully=o["handled_successfully"],
            handling_technique=o.get("handling_technique"),
            timestamp_seconds=o.get("timestamp_seconds"),
        )
        for o in d.get("objections", [])
    ]
    winning_moments = [
        WinningMoment(
            call_id=d["call_id"],
            description=w["description"],
            timestamp_seconds=w.get("timestamp_seconds"),
            technique=w.get("technique"),
        )
        for w in d.get("winning_moments", [])
    ]
    return SalesCall(
        call_id=d["call_id"],
        agent_name=d["agent_name"],
        customer_name=d["customer_name"],
        date=d["date"],
        duration_seconds=d["duration_seconds"],
        outcome=CallOutcome(d["outcome"]),
        objections=objections,
        winning_moments=winning_moments,
        notes=d.get("notes", ""),
    )


class ObjectionAnalyzer:
    """
    Analyzes a corpus of sales calls to surface coaching insights.

    Usage:
        analyzer = ObjectionAnalyzer(calls)
        objection_summaries = analyzer.objection_summaries()
        agent_stats = analyzer.agent_stats()
        coaching = analyzer.coaching_recommendations()
    """

    # Below this success-rate threshold an objection type is flagged
    # for improvement and generates a concrete coaching recommendation.
    IMPROVEMENT_THRESHOLD = 0.60

    def __init__(self, calls: list[SalesCall]) -> None:
        self._calls = calls

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def objection_summaries(self) -> list[ObjectionSummary]:
        """Return per-type objection stats, sorted by mention count descending."""
        buckets: dict[ObjectionType, list[Objection]] = defaultdict(list)
        objection_call_map: dict[tuple, str] = {}  # (type, obj_idx) -> call_id

        for call in self._calls:
            for obj in call.objections:
                key = (obj.type, id(obj))
                buckets[obj.type].append(obj)
                objection_call_map[key] = call.call_id

        summaries: list[ObjectionSummary] = []
        for obj_type, objs in buckets.items():
            total = len(objs)
            successful = [o for o in objs if o.handled_successfully]
            best_call_id, best_agent, best_technique = self._find_best_example(
                obj_type
            )
            summaries.append(
                ObjectionSummary(
                    objection_type=obj_type,
                    total_mentions=total,
                    successful_handles=len(successful),
                    best_call_id=best_call_id,
                    best_call_agent=best_agent,
                    best_handling_technique=best_technique,
                )
            )

        summaries.sort(key=lambda s: s.total_mentions, reverse=True)
        return summaries

    def agent_stats(self) -> list[AgentStats]:
        """Return per-agent performance stats, sorted by close rate descending."""
        buckets: dict[str, list[SalesCall]] = defaultdict(list)
        for call in self._calls:
            buckets[call.agent_name].append(call)

        stats: list[AgentStats] = []
        for agent, agent_calls in buckets.items():
            closed = sum(1 for c in agent_calls if c.closed)
            all_objs = [o for c in agent_calls for o in c.objections]
            successful_objs = [o for o in all_objs if o.handled_successfully]
            stats.append(
                AgentStats(
                    agent_name=agent,
                    total_calls=len(agent_calls),
                    closed_calls=closed,
                    objections_faced=len(all_objs),
                    objections_handled_successfully=len(successful_objs),
                )
            )

        stats.sort(key=lambda s: s.close_rate, reverse=True)
        return stats

    def winning_moments(self, top_n: int = 5) -> list[WinningMoment]:
        """Return the top N winning moments across all calls."""
        all_moments: list[WinningMoment] = []
        for call in self._calls:
            all_moments.extend(call.winning_moments)
        # Return in call-id order (stable, deterministic) limited to top_n
        return all_moments[:top_n]

    def coaching_recommendations(self) -> list[dict]:
        """
        Generate actionable coaching recommendations.

        Rules:
        - Any objection type below IMPROVEMENT_THRESHOLD triggers a study tip
          pointing to the best-handled example call.
        - The top-performing agent on any objection type is flagged to share
          their technique with the team.
        """
        recommendations: list[dict] = []
        summaries = self.objection_summaries()
        agent_stats = self.agent_stats()

        # Best overall agent by close rate for positive call-outs
        top_agent = agent_stats[0].agent_name if agent_stats else None

        for summary in summaries:
            if summary.needs_improvement(self.IMPROVEMENT_THRESHOLD):
                # Find agents who struggle most with this objection type
                weak_agents = self._agents_needing_coaching_on(summary.objection_type)
                for agent in weak_agents:
                    rec = {
                        "agent": agent,
                        "issue": f"Low success rate on '{summary.objection_type.value}' objections "
                                 f"({summary.success_rate * 100:.0f}%)",
                        "action": f"Study Call #{summary.best_call_id} "
                                  f"({summary.best_call_agent} handled it best)",
                    }
                    if summary.best_handling_technique:
                        rec["technique_tip"] = summary.best_handling_technique
                    recommendations.append(rec)

        # Positive: highlight top agent's shareable technique
        if top_agent:
            top_objection_type = self._top_objection_type_for_agent(top_agent)
            if top_objection_type:
                recommendations.append(
                    {
                        "agent": top_agent,
                        "issue": "Top performer",
                        "action": f"Share {top_objection_type.value} handling technique with team",
                    }
                )

        return recommendations

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_best_example(
        self, obj_type: ObjectionType
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Return (call_id, agent_name, technique) for the best handled example."""
        for call in self._calls:
            for obj in call.objections:
                if obj.type == obj_type and obj.handled_successfully:
                    return call.call_id, call.agent_name, obj.handling_technique
        return None, None, None

    def _agents_needing_coaching_on(self, obj_type: ObjectionType) -> list[str]:
        """Return agent names whose success rate on obj_type is below threshold."""
        agent_counts: dict[str, dict] = defaultdict(lambda: {"total": 0, "success": 0})
        for call in self._calls:
            for obj in call.objections:
                if obj.type == obj_type:
                    agent_counts[call.agent_name]["total"] += 1
                    if obj.handled_successfully:
                        agent_counts[call.agent_name]["success"] += 1

        weak: list[str] = []
        for agent, counts in agent_counts.items():
            if counts["total"] > 0:
                rate = counts["success"] / counts["total"]
                if rate < self.IMPROVEMENT_THRESHOLD:
                    weak.append(agent)
        return weak

    def _top_objection_type_for_agent(
        self, agent_name: str
    ) -> Optional[ObjectionType]:
        """Return the objection type an agent handles most successfully."""
        type_counts: dict[ObjectionType, dict] = defaultdict(
            lambda: {"total": 0, "success": 0}
        )
        for call in self._calls:
            if call.agent_name != agent_name:
                continue
            for obj in call.objections:
                type_counts[obj.type]["total"] += 1
                if obj.handled_successfully:
                    type_counts[obj.type]["success"] += 1

        best_type: Optional[ObjectionType] = None
        best_rate = 0.0
        for obj_type, counts in type_counts.items():
            if counts["total"] > 0:
                rate = counts["success"] / counts["total"]
                if rate > best_rate:
                    best_rate = rate
                    best_type = obj_type
        return best_type
