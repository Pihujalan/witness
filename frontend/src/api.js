// Every call here goes to the real Witness backend - even in the demo,
// there is no client-side mock. The backend decides what's real vs
// simulated (see razorpay_client.py); the frontend just displays it.
const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => request('/health'),
  metrics: () => request('/metrics'),
  interpret: (instruction, agentId) =>
    request('/interpret', { method: 'POST', body: JSON.stringify({ instruction, agent_id: agentId }) }),
  evaluate: (toolCall) =>
    request('/gateway/evaluate', { method: 'POST', body: JSON.stringify(toolCall) }),
  auditLog: () => request('/audit-log'),
  verifyLog: () => request('/audit-log/verify'),
  tamperDemo: (seq) => request(`/audit-log/tamper-demo/${seq}`, { method: 'POST' }),
  policy: () => request('/policy'),
  review: (seq, outcome) =>
    request(`/gateway/review/${seq}`, { method: 'POST', body: JSON.stringify({ outcome }) }),
};

export const BACKEND_URL = BASE_URL;
