"""
Shared data shapes for the whole gateway. Keeping these in one place
means the policy engine, anomaly scorer, audit log, and API layer are
all describing the same thing, not four slightly different ones.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    CREATE_REFUND = "create_refund"
    INITIATE_PAYMENT = "initiate_payment"
    REVOKE_TOKEN = "revoke_token"


class ToolCall(BaseModel):
    """A structured action an agent wants to take, before it ever reaches Razorpay."""

    action: ActionType
    amount: Optional[int] = Field(default=None, description="Amount in paise (INR smallest unit)")
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    merchant_id: Optional[str] = None
    counterpart_id: Optional[str] = Field(default=None, description="Session/token id, for revoke_token")
    agent_id: str = Field(default="demo-agent", description="Which agent/session issued this call")
    raw_instruction: Optional[str] = Field(default=None, description="Original natural-language instruction, if any")


class Decision(str, Enum):
    ALLOW = "allow"
    HOLD = "hold_for_approval"
    BLOCK = "block"
    REJECTED = "rejected"  # a human explicitly rejected a held action - distinct from an automatic BLOCK


class ReviewOutcome(str, Enum):
    """What a human did with a HOLD or BLOCK entry after the fact.
    Deliberately narrow: approve/reject only make sense for a HOLD (that's
    the whole point of holding it for a person). flag_false_positive only
    applies to a BLOCK, and never re-executes it - a hard-block ceiling is
    meant to be absolute; Witness records the human's judgment as a
    governance outcome instead of quietly overriding its own safety rail.
    """
    APPROVE = "approve"
    REJECT = "reject"
    FLAG_FALSE_POSITIVE = "flag_false_positive"


class PolicyVerdict(BaseModel):
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)
    policy_version: str = "unversioned"


class AnomalyVerdict(BaseModel):
    model_config = {"protected_namespaces": ()}  # "model_version" collides with pydantic's own "model_" prefix otherwise

    score: float = Field(ge=0.0, le=1.0)
    is_anomalous: bool
    signals: dict[str, float] = Field(default_factory=dict)
    signal_notes: list[str] = Field(default_factory=list)
    model_version: str = "unversioned"
    # The agent's own real historical range, not a generic threshold - this is
    # what makes "1.5x this agent's normal deviation" into an actual number a
    # judge can compare against, rather than a ratio they have to trust.
    baseline_amount_low: Optional[float] = None
    baseline_amount_high: Optional[float] = None
    baseline_sample_size: int = 0


class GatewayResult(BaseModel):
    seq: int
    tool_call: ToolCall
    policy: PolicyVerdict
    anomaly: AnomalyVerdict
    decision: Decision
    explanation: str
    razorpay_response: Optional[dict] = None
    timestamp: str
    audit_entry_hash: str
    review_note: Optional[str] = Field(
        default=None, description="Set only when this record IS a human review of an earlier HOLD/BLOCK entry."
    )
