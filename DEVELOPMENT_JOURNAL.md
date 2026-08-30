# Witness — Development Journal

## 🎯 Strategic Direction: The Agent Integrity Gateway
This project targets a concrete, verified gap: Razorpay's own public `razorpay-mcp-server` exposes payment-moving tools (`create_refund`, `initiate_payment`, `revoke_token`) to AI agents with exactly one safety control — a binary `READ_ONLY` flag. No per-action approval, no audit trail, no anomaly detection.

### The Problem:
Agentic commerce is being built faster than the safety layer around it. Razorpay's own CEO was live-demoed a manipulative discount tactic by their own Agent Studio AI in March 2026 (reported by MediaNama); their public response was a self-declared policy post, not an independently verifiable mechanism. Their real MCP server — checked directly, not assumed — still has zero granular controls as of this build.

### The Solution:
**Witness**: a policy-gated, anomaly-scored, tamper-evidently-logged gateway that sits between an AI agent and Razorpay's real sandbox API.
- **Gates** risky actions (large refunds, token revocations, velocity bursts) behind configurable rules.
- **Scores** every action for anomalous agent behavior with a trained classifier, not fixed thresholds alone.
- **Logs** every decision to a hash-chained, database-backed ledger that can't be silently edited or quietly reset.
- **Explains** every decision in plain English, live, via an LLM call.

---

## 🏗️ Architecture: Intent → Authority → Behavior → Decision → Accountability

**Instruction Interpreter** (intent) → **Policy Engine** (authority) → **Anomaly Scorer** (behavior) → **Decision Engine** → **[Human Review, if HOLD]** → **Razorpay Sandbox** (execution) → **Audit Log** (accountability)

Four layers answer four different questions, stated explicitly after external review pushed on it (see #015/#016): the LLM interprets *what the agent is asking to do*; the policy engine decides *what it is allowed to do at all* (a hard boundary — deterministic, never overridden by the model); the anomaly scorer decides, only on the branch policy already passed, *whether this agent is behaving like itself*; and the ledger records *what was decided, by which policy/model version, and what happened next*. The agent never holds Razorpay credentials — only Witness does — so the architecture itself, not just a rule, is what makes bypass impossible.

### Component Responsibilities:
- **Instruction Interpreter** (`app/interpreter.py`): free-text → structured `ToolCall`, via Groq (`llama-3.1-8b-instant`).
- **Policy Engine** (`app/policy.py`, `POLICY_VERSION`): declarative amount/velocity/scope rules; decides allow / hold / block. Has final authority — the anomaly model can escalate its ALLOW, never downgrade its HOLD or BLOCK.
- **Anomaly Scorer** (`app/anomaly.py`, `app/simulate.py`, `MODEL_VERSION`): logistic regression trained on scripted normal-vs-rogue agent behavior, with honestly-reported precision/recall/false-positive rate. Answers "is this agent behaving like its own baseline," not "is this fraud" — a behavioral-deviation engine, not a generic detector. Two tiers: score ≥ 0.5 escalates an ALLOW to HOLD; score ≥ `EXTREME_ANOMALY_THRESHOLD` (0.85) escalates straight to BLOCK, because severe behavioral drift shouldn't be waved through just for staying under a rupee ceiling.
- **Explainer** (`app/explainer.py`): turns policy + anomaly signals into one plain-English sentence; `anomaly.explain_signals()` additionally renders the raw feature vector as human-readable ⚠/✓ bullets (velocity, amount deviation, counterparty novelty) so "risk: 0.91" is never shown without a reason.
- **Audit Log** (`app/audit.py`): hash-chained, SQLAlchemy-backed (SQLite dev / Postgres prod), tamper-evident (never called "immutable" — the log is append-verifiable, not un-editable by someone with raw DB access) and restart-durable. A human review of a HOLD/BLOCK entry is appended as a *new*, linked entry (`review_of_seq`) rather than mutating the original, so the chain itself reads as a custody trail: agent requested → Witness held → human decided → (if approved) Witness executed.
- **Razorpay Sandbox Client** (`app/razorpay_client.py`): hard-locked to `rzp_test_` keys; refuses to start on anything else. Its credentials live only in this process's environment — no endpoint returns them, and no schema an agent receives carries them.

This file tracks every real decision, pivot, and fix — what was suggested, what was decided, and what was actually verified — not a cleaned-up retelling.

## Status Legend
- ✅ **Fixed** — solution implemented and verified.
- ⚠️ **Workaround** — partial fix; limitation documented, not hidden.
- ❌ **Rejected** — idea or approach abandoned; reasoning kept for the record.
- 🔀 **Pivot** — direction changed mid-stream, previous reasoning superseded.

---

## Failure Class Taxonomy
- **Idea Validity Failures**: an idea turns out to already be shipped, already crowded, or already solved elsewhere.
- **Metric Integrity Failures**: a result looks too good to be honest (trivially-separable synthetic data, suspiciously perfect recall).
- **Infrastructure Assumption Failures**: an assumption about hosting, persistence, or environment turns out false.
- **Scope Discipline Failures**: pressure (external or self-imposed) to add complexity that doesn't serve a real judging criterion.
- **Framing Risks**: a technically sound idea that could land badly if pitched with the wrong tone.

> [!NOTE]
> The point of this taxonomy is the same as in any real project: most of these aren't coding bugs, they're judgment calls that turned out wrong on first pass and got caught before shipping.

---

### [Issue #001] Idea Validity — "Recovery Copilot" was already shipped
- **User Suggestion**: wanted a concrete project idea for the buildathon's Revenue Recovery track.
- **Agent Decision**: proposed an AI agent that recovers revenue from failed payments and checkout abandonment.
- **Status**: ❌ **Rejected**
- **Symptoms**: none in code — caught during idea research, before any build started.
- **Root Cause**: Razorpay's own Agent Studio already ships this exact capability as pre-built agents — "Subscription Recovery" and "Abandoned Cart Conversion."
- **Implementation**: N/A.
- **Verified**: ✅ Confirmed directly against Razorpay's Agent Studio product page before committing to the idea.

### [Issue #002] Idea Validity — dark-pattern / price-discrimination "Integrity Auditor"
- **User Suggestion**: wanted an idea with genuine "how did you find that" impact, not a repackaged existing category.
- **Agent Decision**: anchored to a real, press-covered incident — Razorpay's CEO was live-demoed a manipulative discount tactic by their own Agent Studio AI (MediaNama, March 2026); raised Consumer Protection Act and price-discrimination concerns; Razorpay's CPO responded with a self-declared audit-trail claim, no independent verification offered.
- **Status**: 🔀 **Pivot** (superseded by #003, reasoning carried forward)
- **Symptoms**: N/A.
- **Root Cause**: N/A — this was the right problem space, wrong anchor point (see #003).
- **Implementation**: N/A.
- **Verified**: ✅ Re-checked in August whether Razorpay had since fixed this — they hadn't. A fresh Aug 18, 2026 MediaNama piece about their new "Vulcan" model cited the same unresolved trust question.

### [Issue #003] Pivot — anchor to Razorpay's real, public MCP server
- **User Suggestion**: pushed back repeatedly ("is this already there," "does this already exist") until the idea was standing on something concrete.
- **Agent Decision**: found that Razorpay's actual public `razorpay-mcp-server` repo exposes `create_refund`, `initiate_payment`, and `revoke_token` to agents with exactly one safety control: a binary `READ_ONLY` flag. Confirmed directly from the README, not assumed.
- **Status**: ✅ **Adopted**
- **Symptoms**: N/A.
- **Root Cause**: N/A — this is the gap the project is now built around.
- **Implementation**: became the whole premise of Witness.
- **Verified**: ✅ README inspected directly; no per-action approval, audit log, or anomaly detection exists on the real server as of this build.

### [Issue #004] "Isn't this just a generic MCP firewall?"
- **User Suggestion**: flagged that the general idea felt like something many people could be building.
- **Agent Decision**: searched for existing MCP security proxies. Found `mcp-firewall` (open-source, generic policy/audit proxy, early-stage) and "Slash for Agents" (commercial spend-control platform, own payment rails). Confirmed the general category is real and forming.
- **Status**: ⚠️ **Workaround** (scope sharpened, category risk not eliminated)
- **Symptoms**: risk that Witness reads as redundant if pitched generically.
- **Root Cause**: "gate MCP tool calls" is a real, active product category; the differentiator has to be domain-specific, not conceptual.
- **Implementation**: locked scope to what neither existing tool does — payments-fraud-specific anomaly detection, real Razorpay server integration, grounding in Razorpay's own documented incident. Decision recorded to never let the pitch or README drift into "generic MCP wrapper" framing.
- **Verified**: ⚠️ Mitigated by design; final judgment on whether this reads as sufficiently differentiated rests with the judges.

### [Issue #005] Track selection — AI Risk Manager vs. Growth & Agentic Commerce
- **User Suggestion**: asked directly whether Risk Manager was too common a category to stand out in.
- **Agent Decision**: both tracks' rubric language fit Witness. Risk Manager's explicit "defense-only, honest metrics including false-positive cost" bar was judged the tighter match, since Witness's core output is real precision/recall/FPR numbers.
- **Status**: ✅ **Decided**
- **Implementation**: submission track set to AI Risk Manager.
- **Verified**: N/A — a judgment call, not something to verify by testing.

### [Issue #006] Stack decision — Python/FastAPI + React over unified Next.js
- **User Suggestion**: asked to discuss tech stack explicitly before building.
- **Agent Decision**: traded lower devops risk (one deploy target under Next.js) for the ability to run a genuinely trained scikit-learn model for the anomaly scorer instead of hand-rolled JS thresholds. LLM provider set to Groq (free tier, OpenAI-compatible, fast).
- **Status**: ✅ **Decided**
- **Implementation**: `backend/` (FastAPI) + `frontend/` (Vite/React), two deploy targets (Render + Vercel).
- **Verified**: ✅ Both scaffolds build and install cleanly; see #007–#009.

### [Issue #007] Policy Engine + hash-chained Audit Log — initial build
- **Symptoms**: N/A — first implementation.
- **Root Cause**: N/A.
- **Implementation**: `app/policy.py` (amount/velocity/scope rules for refunds, payments, token revocation) and `app/audit.py` (SHA-256 hash-chained log, initially in-memory + optional flat-file persistence).
- **Status**: ✅ **Fixed**
- **Verified**: ✅ 9/9 unit tests passed on first full run, including a deliberate-tamper test (`tamper_for_demo`) confirming detection actually works, not just in theory.

### [Issue #008] Anomaly scorer's first result was suspiciously perfect
- **Symptoms**: initial synthetic training data produced **100% recall**.
- **Root Cause**: synthetic "rogue" cases were trivially separable from "normal" ones — the classifier found an easy boundary that wouldn't survive scrutiny. This is exactly the "too easy" trap flagged in the project's own build plan.
- **Agent Decision**: rewrote `app/simulate.py` so a slice of normal cases include legitimate bursts (e.g. batch refunds) that genuinely overlap with borderline rogue cases in feature space.
- **Status**: ✅ **Fixed**
- **Implementation**: added overlapping "legitimate burst" and "borderline rogue" sub-populations to the data generator.
- **Verified**: ✅ Re-ran training: **86.1% precision / 96.7% recall / 7.8% false-positive rate** — real numbers with real misses and real false alarms, defensible under questioning. All tests still pass.

### [Issue #009] Frontend v1 looked generic / templated
- **User Suggestion**: "UI/UX plays a very important role... I don't want it to look like AI-generated UI/UX."
- **Agent Decision**: first pass was functional but visually generic — uniform rounded cards, one button style everywhere, a big alert-box banner. Rebuilt around a distinct "control-room ledger" identity.
- **Status**: ✅ **Fixed**
- **Implementation**: `frontend/src/App.jsx` + `styles.css` rewritten — bracket-style `[ALLOW]`/`[HOLD]`/`[BLOCK]` status codes, a chain-linked ledger row visualization, a faint scanline texture, an asymmetric control-rail-plus-monitor layout instead of symmetric dashboard cards, IBM Plex Mono/Sans throughout.
- **Verified**: ✅ Builds cleanly (`npm run build`); visually reviewed against the "avoid generic AI-dashboard" checklist (no purple-blue gradients, no uniform rounded-lg everywhere, no emoji-as-icons).

### [Issue #010] Pressure to "make it more complicated" for its own sake
- **User Suggestion**: "we're using AI to build this, why not make it more complicated or better, tech-stack-wise and idea-wise?"
- **Agent Decision**: pushed back explicitly. Complexity is only worth adding when it serves a real judging criterion (honest metrics, execution reliability); added complexity for its own sake increases what can break before the deadline and what has to be defended live in the panel interview.
- **Status**: ✅ **Decided** (scope discipline maintained)
- **Implementation**: no speculative complexity added; subsequent additions (#011, #012) were each tied to a specific, named justification, not general ambition.
- **Verified**: N/A — a standing engineering principle for the rest of the build, not a one-time fix.

### [Issue #011] Audit log would have silently reset on every redeploy
- **User Suggestion**: asked directly whether the project used a database at all.
- **Root Cause**: in-memory list / flat-file persistence does not survive most free hosting tiers, which wipe the filesystem on redeploy or cold restart — a real risk given the entire pitch of the ledger is that it can't quietly lose history.
- **Agent Decision**: migrated `app/audit.py` to a real database via SQLAlchemy — SQLite for local dev (zero setup), pointed at a free hosted Postgres (Neon/Supabase) for the live deployment via `DATABASE_URL`.
- **Status**: ✅ **Fixed**
- **Implementation**: `audit_entries` table (seq, timestamp, payload, prev_hash, entry_hash); same public interface (`append`, `verify_chain`, `all_entries`, `tamper_for_demo`) so `main.py` needed only a one-line constructor change.
- **Verified**: ✅ Killed the running server mid-session and restarted it fresh — all 3 test entries survived, and the hash chain still verified as valid. All 9 tests still pass against the new backend.

### [Issue #012] No way to get a real "statement" out of the ledger
- **User Suggestion**: "won't we be getting any transaction Excel doc or something like banks do?"
- **Agent Decision**: added a CSV export endpoint — a real, downloadable statement (seq, timestamp, action, amount, agent, decision, anomaly score, explanation, hash), opens directly in Excel/Sheets.
- **Status**: ✅ **Fixed**
- **Implementation**: `GET /audit-log/export.csv` in `app/main.py`; "Download statement (CSV)" link added to the frontend ledger panel.
- **Verified**: ✅ Manually tested via curl — correct headers, correct rows, correct rupee formatting (paise converted to INR).

### [Issue #013] Policy thresholds are not "certified" — documented, not assumed
- **User Suggestion**: "where are you getting the certified policies from?"
- **Agent Decision**: acknowledged directly that the amount thresholds in `DEFAULT_RULES` (₹2,000 / ₹50,000 / ₹5,000 / ₹1,00,000) are illustrative defaults chosen for the demo, not sourced from any real Razorpay policy document or RBI regulation — those aren't public, and even if they were, they vary per merchant.
- **Status**: ✅ **Documented** (not a defect — a scope statement)
- **Implementation**: framing decided for the README/pitch: "thresholds shown are illustrative defaults; a real deployment would have these configured by the merchant's own risk team."
- **Verified**: N/A — an honesty commitment, not a testable fix.

### [Issue #014] Dashboard had no hierarchy of attention — "everything in one dashboard?"
- **User Suggestion**: confirmed the single-dashboard approach was the right call for a live judge demo, but pushed on attention order: a judge's eyes should land on *what did the agent try to do* → *what did Witness decide* → *why* → *what actually happened*, with the ledger as supporting evidence underneath — not a flat feed where the latest decision has no more visual weight than the tenth.
- **Agent Decision**: pulled the most recent event out of the feed entirely into its own large "Spotlight" card at the top of the monitor column (Action → Decision → Risk/Policy/Execution → Evidence hash), and demoted the old feed to a compact, visually secondary "Activity history" strip (decision code + action + amount + time, one line each, no explanation text — that detail now lives only in the Spotlight).
- **Status**: ✅ **Fixed**
- **Implementation**: `frontend/src/App.jsx` (`Spotlight`, `ExecutionLine`, `ACTION_VERBS`), `frontend/src/styles.css` (`.spotlight*`, `.activity-*`).
- **Verified**: ✅ Rebuilt, restarted the live stack, screenshotted — confirmed the latest action is now unmistakably the first thing on screen, with history and the hash-chained ledger clearly secondary.

### [Issue #015] External architecture stress-test — 14 loopholes, triaged not bulk-implemented
- **User Suggestion**: a detailed 14-point critique of the architecture (credential custody / bypass risk, LLM hallucinating financial facts, policy-vs-ML precedence, no HOLD approval workflow, thin audit records, unversioned policy/model, unexplained risk scores, no cold-start behavior, agent impersonation, replay attacks, "immutable" vs. tamper-evident terminology, no Agent Authority framing, no false-positive review loop, an over-polished UI risking "cool dashboard" instead of "controls real money") — explicitly followed by the user's own instruction not to respond by bulk-adding features, but to make the three highest-leverage claims airtight: bypass-proof custody, a real HOLD→approval→execution loop, and complete decision provenance.
- **Agent Decision**: triaged rather than implementing all 14 point-for-point:
  - **Already true, just stated explicitly now**: the agent never holds Razorpay credentials (`CUSTODY_NOTE` in `main.py`, surfaced in the new Agent Authority panel) — bypassing Witness was never architecturally possible, it just wasn't *said* anywhere.
  - **Built now**: a real HOLD → human review → execution chain (`POST /gateway/review/{seq}`, `ReviewOutcome` enum, Approve/Reject buttons for HOLD, a non-executing "flag as false positive" for BLOCK); `policy_version` + `model_version` stamped on every verdict; human-readable `signal_notes` instead of a bare risk score; an `/policy` endpoint + Agent Authority rail panel showing the actual ceilings a request is being checked against; terminology audit confirmed the log is consistently called "tamper-evident," never "immutable."
  - **Explicitly deferred, not silently dropped**: (1) forcing refund *amounts* to come from a trusted Razorpay lookup rather than LLM inference — the right principle ("LLMs interpret intent, never establish financial truth"), but real enforcement needs sandbox payments that already exist to fetch against, which the demo's synthetic scenario IDs don't have; (2) a cold-start "insufficient behavioral history → conservative mode" state for brand-new agents; (3) agent authentication / per-agent capability tokens (anti-impersonation); (4) idempotency keys / replay-attack rejection. All four are real gaps, named here on purpose so the architecture doc states them as known limitations instead of pretending they don't exist.
- **Status**: ✅ **Fixed** (the three prioritized items) / ⚠️ **Documented, deferred** (the four named above)
- **Implementation**: `app/schemas.py` (`ReviewOutcome`, `Decision.REJECTED`, versioned `PolicyVerdict`/`AnomalyVerdict`, `GatewayResult.seq`/`review_note`), `app/main.py` (`/gateway/review/{seq}`, `/policy`, `CUSTODY_NOTE`), `app/anomaly.py` (`explain_signals`), frontend Agent Authority panel + Spotlight review actions.
- **Verified**: ✅ Full backend test suite (9/9) still passes. Live curl trace: evaluated a ₹8,500 refund → correctly HOLD; approved it via `/gateway/review/0` → new linked entry, decision ALLOW, hash chain still verifies (`/audit-log/verify` → `valid: true`); a second review attempt on the same entry correctly rejected with 409. Screenshotted the live UI showing the Approve/Reject buttons and Agent Authority panel rendering real data.

### [Issue #016] Policy vs. ML precedence — made "authority vs. behavior" explicit, added a severe-anomaly tier
- **User Suggestion**: sharpened the distinction further after #015 — policy and the anomaly model aren't two competitors both guessing "is this fraud," they answer genuinely different questions ("can you do this" vs. "are you behaving like yourself"). Pointed out the existing design (ML can only escalate ALLOW→HOLD, never override a BLOCK) was already right, but was missing a top tier: behavior can be anomalous *enough* to block outright even when nothing broke a policy rule.
- **Agent Decision**: added `EXTREME_ANOMALY_THRESHOLD = 0.85` in `app/anomaly.py` — on the branch where policy says ALLOW, a score at or above it now escalates straight to BLOCK instead of HOLD, with its own reason string. Renamed the "Anomaly scorer" rail panel to "Behavioral profile" with an explicit "not a fraud detector" line, and added a `DECISION_HIERARCHY_NOTE` (Intent → Authority → Behavior → Decision → Accountability) surfaced via `/policy` and worked into the hero copy.
- **Status**: ✅ **Fixed**
- **Implementation**: `app/anomaly.py`, `app/main.py` (decision branch + `/policy` response), `frontend/src/App.jsx` copy changes.
- **Verified**: ✅ Unit tests still pass; the escalation branch only fires on the policy-ALLOW path, confirmed by re-reading the modified `evaluate()` logic against the existing HOLD/BLOCK velocity and ceiling tests, which are unaffected.

### [Issue #017] Making the current decision the unmistakable centerpiece, plus a real bug the new UI exposed
- **User Suggestion**: after seeing the redesigned dashboard, gave positive but specific feedback: (1) the HOLD state's copy ("Approved by whom? This one's on a human —") was too subtle for a live demo — needed an explicit "HUMAN APPROVAL REQUIRED" label with the joke as secondary text; (2) show the agent's actual behavioral baseline next to the anomaly, not just a ratio ("Amount is 1.5× baseline" → "₹1,500 vs. this agent's own ₹400–₹900"), so it's visible that the model judges deviation from *this agent*, not an absolute danger threshold; (3) make execution success, once real, look like a checklist, not a sentence.
- **Agent Decision**: implemented all three. Also, while wiring in the real baseline numbers, reproduced the exact scenario a judge would hit in the demo (an agent whose first few refunds are identical amounts) and found the underlying `amount_zscore` calculation had a real bug: `_features_for_action`'s zero-variance fallback used an absolute floor of `1.0` (i.e. one *paisa*), so an agent with zero historical variance produced z-scores like `805000.0` — a number that would have rendered directly on screen as "Amount is 805000.0× this agent's normal deviation," which is exactly the kind of number that makes a judge stop trusting the whole dashboard. This was always latent in the code (`app/simulate.py`, present since #008) but silent, because the raw z-score was previously only ever fed to the model, never displayed to a human — the new `explain_signals()` from #015/#016 is what surfaced it.
- **Status**: ✅ **Fixed**
- **Implementation**: `app/simulate.py` (zero-variance floor now scales with the amount itself: `max(abs(agent_mean) * 0.05, 100.0)` paise, not a flat 1.0), `app/anomaly.py` (`explain_signals` now says "far outside this agent's normal range" instead of printing a raw ratio once `|z| >= 10`, so even a legitimately extreme z-score never renders as an absurd-looking number), `app/schemas.py` + `app/main.py` (`baseline_amount_low/high`, `baseline_sample_size` on `AnomalyVerdict`, computed from the agent's real transaction history — reads "insufficient history" honestly when there are fewer than 3 prior actions, rather than fabricating a range), `frontend/src/App.jsx`/`styles.css` (explicit `HUMAN APPROVAL REQUIRED` label, `.baseline-compare` showing current-vs-baseline for both amount and velocity, `.exec-checklist` for real sandbox execution, a filled decision-badge chip and further-muted Activity History panel to sharpen the visual hierarchy toward the current decision).
- **Verified**: ✅ Unit tests still 9/9. Reproduced the exact failing case directly against the fixed function (`agent_mean=45000, agent_std=0.0, amount=850000` → z-score is still mathematically `357.8`, used correctly by the model, but `explain_signals` now renders "far outside this agent's normal range" instead of a raw multiplier) and again live through the running server with three identical ₹450 refunds followed by a ₹8,500 one — confirmed via screenshot that the dashboard shows a clean baseline comparison (₹8,500 vs. agent baseline ₹450–₹450) instead of the broken number.
- **Process note**: hit a genuinely flaky piece of this sandbox mid-verification — a backend process survived a `kill` via its recorded PID and kept serving stale state against a now-read-only SQLite file, producing confusing `OperationalError: attempt to write a readonly database` errors that had nothing to do with the code. Resolved by force-killing the actual PID from `ps aux` rather than trusting the PID file, and cross-checking the fix at the function level (not just through the live server) before trusting the live re-test.

---

## Capability Milestones
1. [x] Policy Engine — amount/velocity/scope rules for all three action types, versioned (`policy_version`).
2. [x] Hash-chained, database-backed Audit Log — survives restarts, tamper-evident, reviews recorded as linked entries.
3. [x] Anomaly Scorer — trained model, honest (non-rigged) precision/recall/FPR, versioned, two-tier escalation (HOLD / BLOCK), human-readable signal notes.
4. [x] Instruction Interpreter + Explainer — Groq-powered, code complete (untested against a live key).
5. [x] Razorpay Sandbox Client — hard-locked to test-mode keys, code complete (untested against real keys).
6. [x] Frontend console — redesigned around a Spotlight (Action→Decision→Risk/Policy/Execution) hierarchy, Agent Authority + Behavioral Profile panels, builds cleanly, not yet wired to a live backend deployment.
7. [x] HOLD → human review → execution workflow, with a non-executing false-positive flag for BLOCK entries.
8. [ ] End-to-end live test with real Groq + Razorpay test keys.
9. [ ] Deployed to Render (backend) + Vercel (frontend) with a persistent Postgres ledger.
10. [ ] Architecture doc — must explicitly name the deferred gaps from #015 (LLM financial-fact trust boundary, cold-start conservative mode, agent authentication, replay/idempotency protection) as known limitations, not omit them.
11. [ ] Pitch video, GitHub repo finalized for submission.

---

## 🚀 Submission Roadmap
- **Now → keys wired up**: connect real Groq + Razorpay test credentials, verify Interpreter/Explainer/Razorpay calls end-to-end.
- **Deploy**: backend → Render (+ Neon/Supabase Postgres), frontend → Vercel.
- **Polish**: architecture doc, honest-scope README, 5-minute pitch video built around the live demo.
- **Stretch**: a respectful, well-written GitHub issue on `razorpay/razorpay-mcp-server` referencing the working prototype.
- **Deadline**: September 5, 2026 — submit early in the day, not at the deadline hour.

---

## 🛠️ Maintenance Directives
1. **Record the pivot, not just the outcome** — every rejected idea and every "why" stays in this file, even the ones that made the project look worse for a moment.
2. **Journal before "done"** — update this file when a component is verified, not just when it's written.
3. **Metrics get a suspicion check** — a result that looks too clean gets re-examined before it gets reported anywhere.
