"""
Explainer
---------
Turns the Policy Engine's matched rules and the Anomaly Scorer's
signal breakdown into one plain-English sentence a merchant - or a
judge - can actually read, instead of a wall of numbers. This is the
piece that makes the audit trail *transparent*, not just logged, and
it's what should be on screen the moment something gets held or
blocked in the live demo.
"""
from __future__ import annotations
import os
from groq import Groq
from .schemas import PolicyVerdict, AnomalyVerdict, Decision, ToolCall

_SYSTEM_PROMPT = """You write one or two short, plain-English sentences explaining why a \
payments agent's action was allowed, held for approval, or blocked. Be specific and concrete \
- name the actual numbers involved. No hedging, no apologies."""


class Explainer:
    def __init__(self, api_key: str | None = None, model: str = "llama-3.1-8b-instant"):
        self.client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])
        self.model = model

    def explain(self, call: ToolCall, policy: PolicyVerdict, anomaly: AnomalyVerdict, decision: Decision) -> str:
        context = (
            f"Action: {call.action.value}, amount (paise): {call.amount}, decision: {decision.value}.\n"
            f"Policy reasons: {policy.reasons}.\n"
            f"Anomaly score: {anomaly.score:.2f} (flagged={anomaly.is_anomalous}), signals: {anomaly.signals}."
        )
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        return completion.choices[0].message.content.strip()
