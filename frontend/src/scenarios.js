// Preset scenarios for the demo buttons - repeatable, so a judge sees
// the same cause/effect every time rather than depending on how they
// phrase a free-text instruction. Each is a real, structured ToolCall
// sent straight to /gateway/evaluate.

let counter = 0;
const nextId = (prefix) => `${prefix}-${Date.now()}-${counter++}`;

export const SCENARIOS = [
  {
    key: 'normal_refund',
    label: 'Normal refund',
    description: 'A routine, small refund - should sail through.',
    build: () => ({
      action: 'create_refund',
      amount: 450_00,
      payment_id: nextId('pay'),
      order_id: nextId('order'),
      agent_id: 'demo-agent-alpha',
    }),
  },
  {
    key: 'large_refund',
    label: 'Large refund — needs approval',
    description: 'Above the auto-approve ceiling, held for a human.',
    build: () => ({
      action: 'create_refund',
      amount: 8_500_00,
      payment_id: nextId('pay'),
      order_id: nextId('order'),
      agent_id: 'demo-agent-alpha',
    }),
  },
  {
    key: 'rapid_burst',
    label: 'Rapid refund burst — rogue pattern',
    description: 'Fires 6 refunds in a row from the same agent to trip the velocity cap.',
    isBurst: true,
    buildMany: () =>
      Array.from({ length: 6 }, () => ({
        action: 'create_refund',
        amount: 300_00 + Math.floor(Math.random() * 200_00),
        payment_id: nextId('pay'),
        order_id: nextId('order'),
        agent_id: 'demo-agent-rogue',
      })),
  },
  {
    key: 'unfamiliar_revoke',
    label: 'Revoke token — unfamiliar session',
    description: 'Token revocation always needs human confirmation, regardless of amount.',
    build: () => ({
      action: 'revoke_token',
      counterpart_id: nextId('session'),
      agent_id: 'demo-agent-alpha',
    }),
  },
];
