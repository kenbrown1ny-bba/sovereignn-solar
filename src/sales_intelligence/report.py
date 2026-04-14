"""
Training Intelligence Report generator for Sovereign Solar.

Takes the output of ObjectionAnalyzer and renders a human-readable
weekly coaching report (text) or a structured dict for downstream use.
"""

from datetime import date, timedelta

from .analyzer import ObjectionAnalyzer
from .models import SalesCall


def generate_report(calls: list[SalesCall], week_of: date | None = None) -> str:
    """
    Generate a plain-text Training Intelligence Report.

    Args:
        calls:   All SalesCall records for the reporting period.
        week_of: The Monday of the reporting week. Defaults to the most
                 recent Monday relative to today.

    Returns:
        A formatted multi-line string suitable for printing or storing.
    """
    if week_of is None:
        today = date.today()
        week_of = today - timedelta(days=today.weekday())

    analyzer = ObjectionAnalyzer(calls)
    obj_summaries = analyzer.objection_summaries()
    agent_stats = analyzer.agent_stats()
    winning = analyzer.winning_moments(top_n=5)
    coaching = analyzer.coaching_recommendations()

    lines: list[str] = []

    # Header
    lines += [
        f"TRAINING INTELLIGENCE REPORT - Week of {week_of.strftime('%B %d, %Y')}",
        "",
    ]

    # Top objections
    lines += ["TOP OBJECTIONS THIS WEEK:"]
    for i, summary in enumerate(obj_summaries[:5], start=1):
        label = summary.objection_type.value.replace("_", "/").title()
        flag = " NEEDS IMPROVEMENT" if summary.needs_improvement() else ""
        lines.append(
            f"{i}. {label} (mentioned in {summary.total_mentions} calls) "
            f"- Success rate: {summary.success_rate * 100:.0f}%{flag}"
        )
        if summary.best_call_id:
            lines.append(
                f"   Best handled in: Call #{summary.best_call_id} "
                f"({summary.best_call_agent}'s call)"
            )
        if summary.needs_improvement() and summary.best_call_id:
            lines.append(
                f"   NEEDS IMPROVEMENT - Recommend: Watch Call #{summary.best_call_id} "
                f"for better approach"
            )
    lines.append("")

    # Agent performance
    lines += ["AGENT PERFORMANCE:"]
    for stats in agent_stats:
        lines.append(
            f"- {stats.agent_name}: {stats.total_calls} calls, "
            f"{stats.close_rate * 100:.0f}% close rate"
        )
    lines.append("")

    # Coaching recommendations
    if coaching:
        lines += ["RECOMMENDED COACHING:"]
        for rec in coaching:
            if rec["issue"] == "Top performer":
                lines.append(f"- {rec['agent']}: {rec['action']}")
            else:
                lines.append(f"- {rec['agent']}: {rec['action']}")
                if "technique_tip" in rec:
                    lines.append(f"  Tip: {rec['technique_tip']}")
        lines.append("")

    # Winning moments
    if winning:
        lines += ["TOP WINNING MOMENTS:"]
        for moment in winning:
            lines.append(f"- Call #{moment.call_id}: {moment.description}")
            if moment.technique:
                lines.append(f"  Technique: {moment.technique}")
        lines.append("")

    return "\n".join(lines)


def generate_report_dict(calls: list[SalesCall], week_of: date | None = None) -> dict:
    """
    Generate a structured dict version of the Training Intelligence Report.

    Suitable for JSON serialization or passing to downstream systems
    (dashboards, LLM prompts, databases).
    """
    if week_of is None:
        today = date.today()
        week_of = today - timedelta(days=today.weekday())

    analyzer = ObjectionAnalyzer(calls)

    return {
        "week_of": week_of.isoformat(),
        "total_calls": len(calls),
        "objection_summaries": [
            s.to_dict() for s in analyzer.objection_summaries()
        ],
        "agent_stats": [s.to_dict() for s in analyzer.agent_stats()],
        "winning_moments": [
            m.to_dict() for m in analyzer.winning_moments(top_n=5)
        ],
        "coaching_recommendations": analyzer.coaching_recommendations(),
    }
