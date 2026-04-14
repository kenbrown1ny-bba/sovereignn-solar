"""Unit tests for the sales objection analyzer."""

import json
import os
import tempfile
import pytest
from datetime import date

from src.sales_intelligence import (
    ObjectionAnalyzer,
    SalesCall,
    Objection,
    ObjectionType,
    CallOutcome,
    WinningMoment,
    load_calls_from_json,
    generate_report,
    generate_report_dict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_call(
    call_id: str,
    agent: str,
    outcome: CallOutcome = CallOutcome.CLOSED,
    objections: list[Objection] | None = None,
    winning_moments: list[WinningMoment] | None = None,
) -> SalesCall:
    return SalesCall(
        call_id=call_id,
        agent_name=agent,
        customer_name="Test Customer",
        date="2026-04-10",
        duration_seconds=1200,
        outcome=outcome,
        objections=objections or [],
        winning_moments=winning_moments or [],
    )


def _cost_obj(success: bool, technique: str | None = None) -> Objection:
    return Objection(
        type=ObjectionType.COST,
        raw_text="It's too expensive.",
        handled_successfully=success,
        handling_technique=technique,
    )


def _roof_obj(success: bool) -> Objection:
    return Objection(
        type=ObjectionType.ROOF_CONCERNS,
        raw_text="Worried about the roof.",
        handled_successfully=success,
    )


# ---------------------------------------------------------------------------
# ObjectionAnalyzer tests
# ---------------------------------------------------------------------------

class TestObjectionSummaries:
    def test_basic_success_rate(self):
        calls = [
            _make_call("1", "David", objections=[_cost_obj(True)]),
            _make_call("2", "David", objections=[_cost_obj(True)]),
            _make_call("3", "Maria", objections=[_cost_obj(False)]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        summaries = analyzer.objection_summaries()

        assert len(summaries) == 1
        cost = summaries[0]
        assert cost.objection_type == ObjectionType.COST
        assert cost.total_mentions == 3
        assert cost.successful_handles == 2
        assert abs(cost.success_rate - 2 / 3) < 1e-9

    def test_sorted_by_mention_count(self):
        calls = [
            _make_call("1", "David", objections=[_cost_obj(True), _cost_obj(True)]),
            _make_call("2", "Maria", objections=[_roof_obj(False)]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        summaries = analyzer.objection_summaries()

        assert summaries[0].objection_type == ObjectionType.COST
        assert summaries[0].total_mentions == 2
        assert summaries[1].objection_type == ObjectionType.ROOF_CONCERNS

    def test_best_call_id_points_to_first_successful_example(self):
        calls = [
            _make_call("99", "Maria", objections=[_cost_obj(False)]),
            _make_call("42", "David", objections=[_cost_obj(True, "Financing breakdown")]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        summaries = analyzer.objection_summaries()

        cost = next(s for s in summaries if s.objection_type == ObjectionType.COST)
        assert cost.best_call_id == "42"
        assert cost.best_call_agent == "David"
        assert cost.best_handling_technique == "Financing breakdown"

    def test_needs_improvement_flag(self):
        calls = [
            _make_call("1", "Maria", objections=[_roof_obj(False)]),
            _make_call("2", "Maria", objections=[_roof_obj(False)]),
            _make_call("3", "David", objections=[_roof_obj(True)]),  # 33% success
        ]
        analyzer = ObjectionAnalyzer(calls)
        summaries = analyzer.objection_summaries()

        roof = summaries[0]
        assert roof.needs_improvement()  # 33% < 60% threshold

    def test_no_improvement_needed_above_threshold(self):
        calls = [
            _make_call("1", "David", objections=[_cost_obj(True)]),
            _make_call("2", "David", objections=[_cost_obj(True)]),
            _make_call("3", "David", objections=[_cost_obj(True)]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        summaries = analyzer.objection_summaries()

        cost = summaries[0]
        assert not cost.needs_improvement()


class TestAgentStats:
    def test_close_rate(self):
        calls = [
            _make_call("1", "David", outcome=CallOutcome.CLOSED),
            _make_call("2", "David", outcome=CallOutcome.CLOSED),
            _make_call("3", "David", outcome=CallOutcome.NOT_INTERESTED),
            _make_call("4", "David", outcome=CallOutcome.NOT_INTERESTED),
        ]
        analyzer = ObjectionAnalyzer(calls)
        stats = analyzer.agent_stats()

        assert len(stats) == 1
        david = stats[0]
        assert david.total_calls == 4
        assert david.closed_calls == 2
        assert david.close_rate == 0.5

    def test_sorted_by_close_rate(self):
        calls = [
            _make_call("1", "David", outcome=CallOutcome.CLOSED),
            _make_call("2", "David", outcome=CallOutcome.CLOSED),
            _make_call("3", "Maria", outcome=CallOutcome.CLOSED),
            _make_call("4", "Maria", outcome=CallOutcome.NOT_INTERESTED),
        ]
        analyzer = ObjectionAnalyzer(calls)
        stats = analyzer.agent_stats()

        assert stats[0].agent_name == "David"   # 100%
        assert stats[1].agent_name == "Maria"   # 50%

    def test_empty_calls(self):
        analyzer = ObjectionAnalyzer([])
        assert analyzer.agent_stats() == []
        assert analyzer.objection_summaries() == []


class TestCoachingRecommendations:
    def test_generates_recommendation_for_low_performer(self):
        calls = [
            _make_call("2", "David", objections=[_roof_obj(True)]),
            _make_call("3", "Maria", objections=[_roof_obj(False)]),
            _make_call("4", "Maria", objections=[_roof_obj(False)]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        recs = analyzer.coaching_recommendations()

        # Maria should appear in recommendations for roof concerns
        maria_recs = [r for r in recs if r["agent"] == "Maria"]
        assert len(maria_recs) >= 1
        assert "roof_concerns" in maria_recs[0]["issue"]

    def test_no_recs_when_all_performing_well(self):
        calls = [
            _make_call("1", "David", objections=[_cost_obj(True)]),
            _make_call("2", "David", objections=[_cost_obj(True)]),
        ]
        analyzer = ObjectionAnalyzer(calls)
        recs = analyzer.coaching_recommendations()

        # No improvement recs — only positive callouts allowed
        improvement_recs = [r for r in recs if r["issue"] != "Top performer"]
        assert improvement_recs == []


# ---------------------------------------------------------------------------
# Report generation tests
# ---------------------------------------------------------------------------

class TestReportGeneration:
    def _sample_calls(self) -> list[SalesCall]:
        return [
            _make_call(
                "8", "David",
                outcome=CallOutcome.CLOSED,
                objections=[_cost_obj(True, "Financing breakdown")],
                winning_moments=[
                    WinningMoment("8", "Cost objection closed with financing breakdown")
                ],
            ),
            _make_call("3", "Maria", objections=[_roof_obj(False)]),
        ]

    def test_report_contains_key_sections(self):
        calls = self._sample_calls()
        report = generate_report(calls, week_of=date(2026, 4, 14))

        assert "TRAINING INTELLIGENCE REPORT" in report
        assert "Week of April 14, 2026" in report
        assert "TOP OBJECTIONS THIS WEEK" in report
        assert "AGENT PERFORMANCE" in report
        assert "TOP WINNING MOMENTS" in report

    def test_report_dict_structure(self):
        calls = self._sample_calls()
        d = generate_report_dict(calls, week_of=date(2026, 4, 14))

        assert d["week_of"] == "2026-04-14"
        assert d["total_calls"] == 2
        assert isinstance(d["objection_summaries"], list)
        assert isinstance(d["agent_stats"], list)
        assert isinstance(d["winning_moments"], list)
        assert isinstance(d["coaching_recommendations"], list)


# ---------------------------------------------------------------------------
# load_calls_from_json tests
# ---------------------------------------------------------------------------

class TestLoadCallsFromJson:
    def test_round_trip(self):
        calls = [
            _make_call(
                "7", "John",
                outcome=CallOutcome.CLOSED,
                objections=[_cost_obj(True, "Tax credit walkthrough")],
                winning_moments=[WinningMoment("7", "Great close")],
            )
        ]
        raw = [c.to_dict() for c in calls]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as fh:
            json.dump(raw, fh)
            tmp_path = fh.name

        try:
            loaded = load_calls_from_json(tmp_path)
            assert len(loaded) == 1
            assert loaded[0].call_id == "7"
            assert loaded[0].agent_name == "John"
            assert loaded[0].closed is True
            assert loaded[0].objections[0].type == ObjectionType.COST
            assert loaded[0].objections[0].handled_successfully is True
        finally:
            os.unlink(tmp_path)
