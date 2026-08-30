"""
Instruction Interpreter
--------------------------
Turns a free-text instruction ("refund order ORD-1183 for the full
amount, the customer's upset") into the structured ToolCall the
Gateway understands. This is a genuine, meaningful use of an LLM: the
ambiguity of natural language is the actual hard part of "what did
the agent mean to do" - and exactly where a confused or manipulated
agent would first go wrong, which is why this sits *before* the
gateway rather than replacing it.
"""
from __future__ import annotations
import json
import os
from groq import Groq
from .schemas import ToolCall

_SYSTEM_PROMPT = """You convert a merchant's natural-language instruction into a single \
structured JSON tool call for a payments agent. Only ever output JSON matching this shape:

{
  "action": "create_refund" | "initiate_payment" | "revoke_token",
  "amount": <integer, amount in paise (INR smallest unit), or null>,
  "order_id": <string or null>,
  "payment_id": <string or null>,
  "counterpart_id": <string or null, only for revoke_token>
}

Rules:
- Convert rupee amounts to paise (multiply by 100).
- If the instruction is ambiguous about which action, pick the closest match - never invent fields not listed above.
- Output JSON only. No prose, no markdown fences.
"""


class Interpreter:
    def __init__(self, api_key: str | None = None, model: str = "llama-3.1-8b-instant"):
        self.client = Groq(api_key=api_key or os.environ["GROQ_API_KEY"])
        self.model = model

    def interpret(self, instruction: str, agent_id: str) -> ToolCall:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": instruction},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        data = json.loads(completion.choices[0].message.content)
        data["agent_id"] = agent_id
        data["raw_instruction"] = instruction
        return ToolCall(**data)
