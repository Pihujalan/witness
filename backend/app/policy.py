"""
Policy Engine
-------------
Rule-based checks that decide whether a tool call is allowed outright,
held for human approval, or blocked - before it ever reaches Razorpay
or the anomaly scorer. Rules are declarative and named, so the audit
trail can point at *which rule* fired instead of just "the AI said no".

This is the "bounded and gated" half of the buildathon's own rubric
language for the Growth & Agentic Commerce track.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from .schemas import ToolCall, ActionType, Decision, PolicyVerdict

# Amounts are in paise (1 INR = 100 paise), matching Razorpay's own convention.
DEFAULT_RULES = {
    "refund_auto_approve_ceiling": 2_000_00,     # >= this, a refund needs human sign-off
    "refund_hard_block_ceiling": 50_000_00,      # >= this, always block outright
    "payment_auto_approve_ceiling": 5_000_00,
    "payment_hard_block_ceiling": 1_00_000_00,
    "max_actions_per_minute_per_agent": 5,
}


# Bumped whenever DEFAULT_RULES changes shape or thresholds, so every audit
# entry records exactly which version of the rules produced its decision -
# "why was this approved" has to stay answerable even after the policy
# itself has since changed.
POLICY_VERSION = "refund-policy-v1"


@dataclass
class PolicyEngine:
    rules: dict = field(default_factory=lambda: dict(DEFAULT_RULES))
    version: str = POLICY_VERSION

    def evaluate(self, call: ToolCall, recent_call_count_last_minute: int) -> PolicyVerdict:
        reasons: list[str] = []
        matched: list[str] = []
        decision = Decision.ALLOW

        # Velocity check applies to every action type, before anything else.
        if recent_call_count_last_minute > self.rules["max_actions_per_minute_per_agent"]:
            matched.append("max_actions_per_minute_per_agent")
            reasons.append(
                f"{recent_call_count_last_minute} actions from this agent in the last minute "
                f"exceeds the cap of {self.rules['max_actions_per_minute_per_agent']}."
            )
            decision = Decision.BLOCK

        if call.action == ActionType.CREATE_REFUND:
            amount = call.amount or 0
            if amount >= self.rules["refund_hard_block_ceiling"]:
                matched.append("refund_hard_block_ceiling")
                reasons.append(
                    f"Refund of ₹{amount/100:,.0f} exceeds the hard block ceiling of "
                    f"₹{self.rules['refund_hard_block_ceiling']/100:,.0f}."
                )
                decision = Decision.BLOCK
            elif amount >= self.rules["refund_auto_approve_ceiling"] and decision == Decision.ALLOW:
                matched.append("refund_auto_approve_ceiling")
                reasons.append(
                    f"Refund of ₹{amount/100:,.0f} is above the ₹"
                    f"{self.rules['refund_auto_approve_ceiling']/100:,.0f} auto-approve ceiling "
                    "— needs human sign-off."
                )
                decision = Decision.HOLD

        elif call.action == ActionType.INITIATE_PAYMENT:
            amount = call.amount or 0
            if amount >= self.rules["payment_hard_block_ceiling"]:
                matched.append("payment_hard_block_ceiling")
                reasons.append(f"Payment of ₹{amount/100:,.0f} exceeds the hard block ceiling.")
                decision = Decision.BLOCK
            elif amount >= self.rules["payment_auto_approve_ceiling"] and decision == Decision.ALLOW:
                matched.append("payment_auto_approve_ceiling")
                reasons.append(f"Payment of ₹{amount/100:,.0f} needs human sign-off before it goes through.")
                decision = Decision.HOLD

        elif call.action == ActionType.REVOKE_TOKEN:
            # Revoking access always widens or removes trust - it's never routine,
            # regardless of any "amount" (there isn't one).
            if decision == Decision.ALLOW:
                matched.append("revoke_token_always_hold")
                reasons.append("Token revocation always requires human confirmation.")
                decision = Decision.HOLD

        if not reasons:
            reasons.append("No policy rule matched; action is within all configured limits.")

        return PolicyVerdict(decision=decision, reasons=reasons, matched_rules=matched, policy_version=self.version)
