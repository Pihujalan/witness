<img width="1555" height="1012" alt="ChatGPT Image Sep 6, 2026, 12_57_30 AM" src="https://github.com/user-attachments/assets/751d9f7f-b7e9-4194-b080-82350b7e60c4" /><img width="1555" height="1012" alt="image" src="https://github.com/user-attachments/assets/f19971d2-697a-4dc6-9bca-bac20278913c" /># Witness

An independent governance and audit layer for AI agent payments, built for the Razorpay AI Builder Internship 2026 (Risk track).

## The problem

AI agents can now trigger payment actions directly through APIs like Razorpay's, and MCP makes handing agents access to those tools even easier. Razorpay's own MCP server adds real safety controls (read only mode, scoped tools), but those controls still live on the agent's own tool surface. Nothing independently checks what the agent is actually doing, catches it drifting from its own normal behavior, or produces a record that can't be quietly edited afterward.

## What Witness does

Witness sits between any AI agent and Razorpay. Every payment action the agent proposes, whether it arrives as a free text instruction or a structured tool call, passes through Witness before it can execute:

- A deterministic policy engine enforces amount thresholds. No instruction text, including a prompt injection attempt, can talk its way past it, because the policy engine never reads the raw instruction, only the structured fields the interpreter extracted.
- A behavioral anomaly scorer learns each agent's own historical pattern and can hold a request that deviates from it even when it is fully within policy limits.
- Anything held for a human is re-validated at the moment of approval, not just rubber stamped from when it was first requested: payload hash, policy state, approval expiry, and whether the agent is paused are all checked again.
- Every request carries an idempotency key. Replaying or duplicating a request is recognized and blocked, not re-executed.
- The audit log is hash chained. Any edit to a past entry breaks verification immediately.
- If the LLM interpreter is unreachable, the request is blocked rather than guessed at. If the anomaly model is unreachable, an otherwise auto-approvable request is held instead of allowed. A missing signal is never treated as a clean one.

The agent can ask for a payment. It cannot approve itself, execute on its own word, or rewrite what actually happened.

## Architecture
![Uploading image.png…]()




## Supported actions

- `create_refund`: real call to Razorpay's test mode refund API, requires an existing payment.
- `initiate_payment`: real call to Razorpay's test mode order creation API.
- `revoke_token`: simulated, since Razorpay's REST API has no public equivalent to the token revocation Razorpay's MCP server exposes for agent sessions. This is stated explicitly in the response and in this README, never silently faked as a real call.

## Default policy thresholds

Amounts are in paise, matching Razorpay's own convention.

| Rule | Threshold |
| --- | --- |
| Refund auto-approve ceiling | below ₹2,000 |
| Refund hard block ceiling | ₹50,000 and above |
| Payment auto-approve ceiling | below ₹5,000 |
| Payment hard block ceiling | ₹1,00,000 and above |
| Token revocation | always requires human approval |
| Velocity cap | 5 actions per agent per minute |

Every audit entry records which policy version and which specific rule produced its decision.

## Decision vs execution

`decision` (ALLOW, HOLD, BLOCK, REJECTED) is the governance verdict: was this agent authorized to do this, right now. `execution_status` (SUCCESS, FAILED, SIMULATED, NOT_ATTEMPTED) is what actually happened when Witness tried to carry it out against Razorpay. The two are kept separate on purpose: an ALLOW where Razorpay itself failed (bad ID, network issue) is a different fact from a governance denial, and collapsing them would erase that distinction.

## Behavioral anomaly detection

The scorer is trained per agent on that agent's own history, not a generic fraud model, so what counts as anomalous is specific to how that agent normally behaves. Precision, recall, and false positive rate are computed on a held out test set and compared against a simple rule based baseline evaluated on the same data. Exact figures come from the `/metrics` endpoint at runtime rather than being fixed here, since they depend on the simulated data generated for that run.

## Tech stack

- Backend: FastAPI, SQLAlchemy, scikit-learn (LogisticRegression anomaly scorer)
- Frontend: React 18, Vite
- LLM: Groq (instruction interpretation and plain English explanation only, never part of the decision logic)
- Payments: Razorpay Python SDK, test mode only
- Storage: SQLite by default, swappable for Postgres via `DATABASE_URL`

## Running locally

Backend:

```
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env       # then fill in real TEST mode keys
uvicorn app.main:app --reload --port 8000
```

Frontend:

```
cd frontend
npm install
npm run dev
```

The app refuses to start if `RAZORPAY_TEST_KEY_ID` doesn't look like a test mode key. It is not meant to run against live credentials.

## Tests

```
cd backend
pytest
```

Covers policy rules, anomaly scoring, audit log integrity, and concurrency hardening (atomic approval locking, atomic replay/idempotency locking under simultaneous duplicate requests).

## Demo toggles

For live demonstration, three failure modes can be forced on and off without restarting anything:

- `/demo/simulate-outage`: forces Razorpay execution to fail.
- `/demo/simulate-interpreter-outage`: forces the Groq interpreter to fail. Only affects `/interpret` (free text instructions), not requests sent as pre-built structured tool calls.
- `/demo/simulate-ml-outage`: forces the anomaly scorer to report unavailable, which degrades any otherwise-ALLOW decision to HOLD.

## Safety controls summary

- Fail closed: interpreter down means BLOCK, anomaly model down means HOLD, never ALLOW.
- Approval expiry: a 10 minute window on every HOLD; an approval attempted after it has expired is rejected rather than executed on stale context.
- Credential isolation: only Witness holds the Razorpay key, never the agent.
- Atomic approval and atomic replay handling: per request locking prevents a race from ever letting the same action execute twice.
- Tamper evident audit log: hash chained, any past edit breaks verification instantly.
