"""
Data models for the Sovereign Solar Sales Intelligence Engine.

Represents the core domain objects: calls, objections, agents, and outcomes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ObjectionType(str, Enum):
    COST = "cost"
    TIMING = "timing"
    ROOF_CONCERNS = "roof_concerns"
    HOA_RESTRICTIONS = "hoa_restrictions"
    CREDIT = "credit"
    EXISTING_CONTRACT = "existing_contract"
    NOT_INTERESTED = "not_interested"
    SPOUSE_DECISION = "spouse_decision"
    OTHER = "other"


class CallOutcome(str, Enum):
    CLOSED = "closed"
    FOLLOW_UP_SCHEDULED = "follow_up_scheduled"
    NOT_INTERESTED = "not_interested"
    NO_ANSWER = "no_answer"
    CALLBACK_REQUESTED = "callback_requested"


@dataclass
class Objection:
    """A single objection raised during a sales call."""
    type: ObjectionType
    raw_text: str
    handled_successfully: bool
    handling_technique: Optional[str] = None
    timestamp_seconds: Optional[int] = None  # offset into call recording

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "raw_text": self.raw_text,
            "handled_successfully": self.handled_successfully,
            "handling_technique": self.handling_technique,
            "timestamp_seconds": self.timestamp_seconds,
        }


@dataclass
class WinningMoment:
    """A notable positive moment in a call worth highlighting for coaching."""
    call_id: str
    description: str
    timestamp_seconds: Optional[int] = None
    technique: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "description": self.description,
            "timestamp_seconds": self.timestamp_seconds,
            "technique": self.technique,
        }


@dataclass
class SalesCall:
    """A complete sales call record with metadata, objections, and outcome."""
    call_id: str
    agent_name: str
    customer_name: str
    date: str                          # ISO-8601 date string, e.g. "2026-04-08"
    duration_seconds: int
    outcome: CallOutcome
    objections: list[Objection] = field(default_factory=list)
    winning_moments: list[WinningMoment] = field(default_factory=list)
    notes: str = ""

    @property
    def closed(self) -> bool:
        return self.outcome == CallOutcome.CLOSED

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "agent_name": self.agent_name,
            "customer_name": self.customer_name,
            "date": self.date,
            "duration_seconds": self.duration_seconds,
            "outcome": self.outcome.value,
            "objections": [o.to_dict() for o in self.objections],
            "winning_moments": [w.to_dict() for w in self.winning_moments],
            "notes": self.notes,
        }


@dataclass
class AgentStats:
    """Aggregated performance stats for a single agent over a reporting period."""
    agent_name: str
    total_calls: int
    closed_calls: int
    objections_faced: int
    objections_handled_successfully: int

    @property
    def close_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.closed_calls / self.total_calls

    @property
    def objection_success_rate(self) -> float:
        if self.objections_faced == 0:
            return 0.0
        return self.objections_handled_successfully / self.objections_faced

    def to_dict(self) -> dict:
        return {
            "agent_name": self.agent_name,
            "total_calls": self.total_calls,
            "closed_calls": self.closed_calls,
            "close_rate_pct": round(self.close_rate * 100, 1),
            "objections_faced": self.objections_faced,
            "objection_success_rate_pct": round(self.objection_success_rate * 100, 1),
        }


@dataclass
class ObjectionSummary:
    """Aggregated stats for a single objection type across all calls."""
    objection_type: ObjectionType
    total_mentions: int
    successful_handles: int
    best_call_id: Optional[str] = None
    best_call_agent: Optional[str] = None
    best_handling_technique: Optional[str] = None

    @property
    def success_rate(self) -> float:
        if self.total_mentions == 0:
            return 0.0
        return self.successful_handles / self.total_mentions

    def needs_improvement(self, threshold: float = 0.60) -> bool:
        return self.success_rate < threshold

    def to_dict(self) -> dict:
        return {
            "objection_type": self.objection_type.value,
            "total_mentions": self.total_mentions,
            "successful_handles": self.successful_handles,
            "success_rate_pct": round(self.success_rate * 100, 1),
            "best_call_id": self.best_call_id,
            "best_call_agent": self.best_call_agent,
            "best_handling_technique": self.best_handling_technique,
            "needs_improvement": self.needs_improvement(),
        }
