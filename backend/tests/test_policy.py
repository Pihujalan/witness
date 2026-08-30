from app.policy import PolicyEngine
from app.schemas import ToolCall, ActionType, Decision


def make_call(action, amount=None, **kw):
    return ToolCall(action=action, amount=amount, agent_id="test-agent", **kw)


def test_small_refund_auto_allows():
    engine = PolicyEngine()
    verdict = engine.evaluate(make_call(ActionType.CREATE_REFUND, amount=500_00), recent_call_count_last_minute=1)
    assert verdict.decision == Decision.ALLOW


def test_large_refund_needs_approval():
    engine = PolicyEngine()
    verdict = engine.evaluate(make_call(ActionType.CREATE_REFUND, amount=5_000_00), recent_call_count_last_minute=1)
    assert verdict.decision == Decision.HOLD


def test_huge_refund_is_blocked():
    engine = PolicyEngine()
    verdict = engine.evaluate(make_call(ActionType.CREATE_REFUND, amount=60_000_00), recent_call_count_last_minute=1)
    assert verdict.decision == Decision.BLOCK


def test_velocity_cap_blocks_even_small_amount():
    engine = PolicyEngine()
    verdict = engine.evaluate(make_call(ActionType.CREATE_REFUND, amount=100_00), recent_call_count_last_minute=10)
    assert verdict.decision == Decision.BLOCK


def test_revoke_token_always_holds():
    engine = PolicyEngine()
    verdict = engine.evaluate(make_call(ActionType.REVOKE_TOKEN, counterpart_id="sess-1"), recent_call_count_last_minute=1)
    assert verdict.decision == Decision.HOLD
