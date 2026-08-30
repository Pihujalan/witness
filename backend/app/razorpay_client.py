"""
Razorpay Sandbox Client
-------------------------
Thin wrapper around the official `razorpay` Python SDK, hard-locked
to test-mode keys. This is what an "allow" decision actually forwards
to - a real Razorpay API call, not a mock response.
"""
from __future__ import annotations
import os
import razorpay
from .schemas import ToolCall, ActionType


class RazorpayGuardError(Exception):
    pass


class RazorpaySandboxClient:
    def __init__(self, key_id: str | None = None, key_secret: str | None = None):
        key_id = key_id or os.environ["RAZORPAY_TEST_KEY_ID"]
        key_secret = key_secret or os.environ["RAZORPAY_TEST_KEY_SECRET"]
        if not key_id.startswith("rzp_test_"):
            # This project must never run against live production credentials -
            # refuse to even start rather than risk it.
            raise RazorpayGuardError(
                "Refusing to start: RAZORPAY_TEST_KEY_ID doesn't look like a test-mode key "
                "(expected it to start with 'rzp_test_')."
            )
        self.client = razorpay.Client(auth=(key_id, key_secret))

    def execute(self, call: ToolCall) -> dict:
        if call.action == ActionType.CREATE_REFUND:
            return self.client.payment.refund(call.payment_id, {"amount": call.amount})

        if call.action == ActionType.INITIATE_PAYMENT:
            # Test-mode order creation stands in for "initiate payment" here -
            # actually capturing a payment needs a checkout/card step that
            # can't run headless. The gateway decision is what's under test,
            # not Razorpay's checkout UI.
            return self.client.order.create({
                "amount": call.amount,
                "currency": "INR",
                "receipt": f"witness-{call.order_id or 'auto'}",
            })

        if call.action == ActionType.REVOKE_TOKEN:
            # Razorpay's MCP server exposes revoke_token for agent session
            # tokens; there's no equivalent public REST call in the SDK, so
            # this is simulated. Be explicit about that in the README and
            # in the response itself - never silently fake a real call.
            return {"simulated": True, "action": "revoke_token", "counterpart_id": call.counterpart_id}

        raise ValueError(f"Unsupported action: {call.action}")
