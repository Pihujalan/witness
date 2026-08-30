import React, { useEffect, useState, useCallback, useRef } from 'react';
import { api, BACKEND_URL } from './api.js';
import { SCENARIOS } from './scenarios.js';

const DECISION_META = {
  allow: { code: 'ALLOW', className: 'is-allow' },
  hold_for_approval: { code: 'HOLD', className: 'is-hold' },
  block: { code: 'BLOCK', className: 'is-block' },
  rejected: { code: 'REJECTED', className: 'is-rejected' },
};

function DecisionCode({ decision }) {
  const meta = DECISION_META[decision] || { code: decision?.toUpperCase() || '—', className: '' };
  return <span className={`decision-code ${meta.className}`}>[{meta.code}]</span>;
}

const ACTION_VERBS = {
  create_refund: 'wants to issue a refund',
  initiate_payment: 'wants to initiate a payment',
  revoke_token: 'wants to revoke a token',
};

function ExecutionLine({ ev }) {
  if (ev.decision !== 'allow') {
    return (
      <span className="exec-not-run">
        Not sent to Razorpay — {ev.decision === 'block' ? 'blocked' : 'held for approval'} before execution.
      </span>
    );
  }
  if (!ev.razorpay_response) {
    return <span className="exec-not-run">Allowed, but no Razorpay sandbox is connected on this deployment.</span>;
  }
  if (ev.razorpay_response.simulated) {
    return <span className="exec-simulated">Simulated — {ev.tool_call.action} has no real sandbox equivalent.</span>;
  }
  // A real sandbox round-trip happened - make that moment unmistakable
  // rather than folding it into one line of prose. This is the point the
  // project stops looking like a simulation.
  return (
    <ul className="exec-checklist">
      <li className="exec-ran">✓ Razorpay sandbox reached</li>
      <li className="exec-ran">✓ {ev.tool_call.action} created</li>
      {ev.razorpay_response.id && <li className="exec-ran mono">✓ id: {ev.razorpay_response.id}</li>}
      {ev.razorpay_response.status && <li className="exec-ran">✓ status: {ev.razorpay_response.status}</li>}
    </ul>
  );
}

function Spotlight({ ev, onReview, busy, velocityCap }) {
  if (!ev) {
    return (
      <section className="panel spotlight spotlight-empty">
        <p className="fine-print">
          Nothing evaluated yet. Send an instruction or run a scenario on the left — the full story lands here:
          what the agent tried, what Witness decided, why, and what actually happened.
        </p>
      </section>
    );
  }
  const meta = DECISION_META[ev.decision] || { code: ev.decision?.toUpperCase() || '—', className: '' };
  return (
    <section className={`panel spotlight spotlight-${meta.className}`}>
      <div className="spotlight-top">
        <div className="spotlight-agent-line">
          <span className="spotlight-tag">Agent</span>
          <span className="mono">{ev.tool_call.agent_id}</span>
          <span className="spotlight-verb">{ACTION_VERBS[ev.tool_call.action] || ev.tool_call.action}</span>
          {ev.tool_call.amount != null && <span className="spotlight-amount">{formatPaise(ev.tool_call.amount)}</span>}
        </div>
        {ev.tool_call.raw_instruction && (
          <p className="spotlight-instruction">&ldquo;{ev.tool_call.raw_instruction}&rdquo;</p>
        )}
      </div>

      <div className="spotlight-decision-row">
        <span className={`spotlight-decision-badge ${meta.className}`}>[{meta.code}]</span>
        <span className="spotlight-timestamp mono">{timeShort(ev.timestamp)}</span>
      </div>

      {ev.decision === 'hold_for_approval' && !ev.review_note && (
        <div className="spotlight-review-actions">
          <div className="review-heading">
            <span className="review-label">⏸ Human approval required</span>
            <span className="review-prompt">— this one's on a human.</span>
          </div>
          <div className="review-buttons">
            <button className="btn-approve" disabled={busy} onClick={() => onReview(ev.seq, 'approve')}>
              Approve → execute
            </button>
            <button className="btn-reject" disabled={busy} onClick={() => onReview(ev.seq, 'reject')}>
              Reject
            </button>
          </div>
        </div>
      )}
      {ev.decision === 'block' && !ev.review_note && (
        <div className="spotlight-review-actions">
          <span className="review-prompt">Think this block is wrong?</span>
          <button className="btn-flag" disabled={busy} onClick={() => onReview(ev.seq, 'flag_false_positive')}>
            Flag as false positive
          </button>
        </div>
      )}
      {ev.review_note && <p className="spotlight-review-note">↳ {ev.review_note}</p>}

      <div className="spotlight-grid">
        <div className="spotlight-block">
          <h3 className="spotlight-block-title">Risk &middot; {(ev.anomaly.score * 100).toFixed(0)}%</h3>
          <div className="risk-meter">
            <div className="risk-fill" style={{ width: `${Math.round(ev.anomaly.score * 100)}%` }} />
          </div>

          <div className="baseline-compare">
            <div className="baseline-row">
              <span className="baseline-current">{formatPaise(ev.tool_call.amount)}</span>
              <span className="baseline-label">this request</span>
            </div>
            <div className="baseline-divider" />
            <div className="baseline-row">
              <span className="baseline-normal">
                {ev.anomaly.baseline_sample_size >= 3
                  ? `${formatPaise(ev.anomaly.baseline_amount_low)}–${formatPaise(ev.anomaly.baseline_amount_high)}`
                  : 'insufficient history'}
              </span>
              <span className="baseline-label">agent's own baseline</span>
            </div>
          </div>
          <div className="baseline-compare">
            <div className="baseline-row">
              <span className="baseline-current">{ev.anomaly.signals.velocity_1min}/min</span>
              <span className="baseline-label">this agent, now</span>
            </div>
            <div className="baseline-divider" />
            <div className="baseline-row">
              <span className="baseline-normal">cap {velocityCap ?? '—'}/min</span>
              <span className="baseline-label">policy limit</span>
            </div>
          </div>

          {ev.anomaly.signal_notes?.length > 0 && (
            <ul className="spotlight-signal-notes">
              {ev.anomaly.signal_notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="spotlight-block">
          <h3 className="spotlight-block-title">Policy</h3>
          {ev.policy.matched_rules.length > 0 ? (
            <ul className="spotlight-rules">
              {ev.policy.matched_rules.map((r) => (
                <li key={r} className="mono">{r}</li>
              ))}
            </ul>
          ) : (
            <p className="spotlight-block-value">No rule matched</p>
          )}
          <p className="fine-print">{ev.policy.policy_version} · {ev.anomaly.model_version}</p>
        </div>
        <div className="spotlight-block">
          <h3 className="spotlight-block-title">Execution</h3>
          <p className="spotlight-block-value"><ExecutionLine ev={ev} /></p>
        </div>
      </div>

      <p className="spotlight-explanation">{ev.explanation}</p>
      <p className="fine-print mono">evidence &middot; {ev.audit_entry_hash.slice(0, 16)}&hellip;</p>
    </section>
  );
}

function formatPaise(paise) {
  if (paise === null || paise === undefined) return '—';
  return `₹${(paise / 100).toLocaleString('en-IN')}`;
}

function timeShort(iso) {
  try {
    return new Date(iso).toLocaleTimeString('en-IN', { hour12: false });
  } catch {
    return '';
  }
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [events, setEvents] = useState([]);
  const [instruction, setInstruction] = useState('');
  const [agentId, setAgentId] = useState('demo-agent-alpha');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [auditEntries, setAuditEntries] = useState([]);
  const [verifyResult, setVerifyResult] = useState(null);
  const [policyInfo, setPolicyInfo] = useState(null);
  const inputRef = useRef(null);

  const refreshAudit = useCallback(() => {
    api.auditLog().then(setAuditEntries).catch(() => {});
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ ok: false }));
    api.metrics().then(setMetrics).catch(() => {});
    api.policy().then(setPolicyInfo).catch(() => {});
    refreshAudit();
  }, [refreshAudit]);

  async function pushEvent(call) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.evaluate(call);
      setEvents((prev) => [result, ...prev].slice(0, 30));
      refreshAudit();
      return result;
    } catch (e) {
      setError(String(e.message || e));
      return null;
    } finally {
      setBusy(false);
    }
  }

  async function handleFreeText(e) {
    e.preventDefault();
    if (!instruction.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const call = await api.interpret(instruction, agentId);
      await pushEvent(call);
      setInstruction('');
      inputRef.current?.focus();
    } catch (e) {
      setError(String(e.message || e));
      setBusy(false);
    }
  }

  async function handleScenario(scenario) {
    if (scenario.isBurst) {
      const calls = scenario.buildMany();
      for (const call of calls) {
        // eslint-disable-next-line no-await-in-loop
        await pushEvent(call);
      }
    } else {
      await pushEvent(scenario.build());
    }
  }

  async function handleVerify() {
    const result = await api.verifyLog();
    setVerifyResult(result);
  }

  async function handleTamperDemo() {
    if (auditEntries.length === 0) return;
    const seq = auditEntries[0].seq;
    await api.tamperDemo(seq);
    refreshAudit();
    setVerifyResult(null);
  }

  async function handleReview(seq, outcome) {
    setBusy(true);
    setError(null);
    try {
      const result = await api.review(seq, outcome);
      setEvents((prev) => [result, ...prev].slice(0, 30));
      refreshAudit();
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <div className="scanlines" aria-hidden="true" />

      <header className="topbar">
        <div className="topbar-mark">
          <span className="mark-glyph" aria-hidden="true">◈</span>
          <span className="mark-word">WITNESS</span>
        </div>
        <div className="topbar-status">
          <span className="live-dot" aria-hidden="true" />
          <span>SANDBOX MODE — no real money moves</span>
        </div>
        <div className="topbar-links">
          <span className={`node ${health?.razorpay_configured ? 'node-on' : 'node-off'}`}>razorpay</span>
          <span className={`node ${health?.llm_configured ? 'node-on' : 'node-off'}`}>groq</span>
        </div>
      </header>

      <div className="hero">
        <h1>An independent witness for AI agent payments.</h1>
        <p>
          Intent → authority → behavior → decision → accountability. Every action below is
          interpreted, checked against hard limits an agent can never talk its way past, checked
          against that agent's own behavioral baseline, then written to a hash-chained ledger that
          can't be quietly edited. Allowed actions hit Razorpay's real sandbox — nothing here is a
          mockup.
        </p>
      </div>

      <main className="layout">
        <aside className="rail">
          <section className="panel">
            <h2 className="panel-title">01 — Issue an instruction</h2>
            <form onSubmit={handleFreeText} className="instruction-form">
              <input
                ref={inputRef}
                type="text"
                value={instruction}
                onChange={(e) => setInstruction(e.target.value)}
                placeholder='"refund order ORD-1183 for ₹500"'
                disabled={busy}
              />
              <div className="form-row">
                <input
                  type="text"
                  className="agent-id-input"
                  value={agentId}
                  onChange={(e) => setAgentId(e.target.value)}
                  aria-label="Agent ID"
                />
                <button type="submit" className="btn-primary" disabled={busy}>
                  {busy ? 'Evaluating…' : 'Send'}
                </button>
              </div>
            </form>
            {error && <p className="error-text">{error}</p>}
          </section>

          <section className="panel">
            <h2 className="panel-title">02 — Or run a scenario</h2>
            <div className="scenario-list">
              {SCENARIOS.map((s) => (
                <button
                  key={s.key}
                  className="scenario-btn"
                  onClick={() => handleScenario(s)}
                  disabled={busy}
                  title={s.description}
                >
                  <span className="scenario-label">{s.label}</span>
                  <span className="scenario-arrow" aria-hidden="true">→</span>
                </button>
              ))}
            </div>
          </section>

          {policyInfo && (
            <section className="panel">
              <h2 className="panel-title">Agent authority</h2>
              <ul className="authority-list">
                <li>
                  <span>Refunds</span>
                  <span>auto ≤ {formatPaise(policyInfo.rules.refund_auto_approve_ceiling)} · block ≥ {formatPaise(policyInfo.rules.refund_hard_block_ceiling)}</span>
                </li>
                <li>
                  <span>Payments</span>
                  <span>auto ≤ {formatPaise(policyInfo.rules.payment_auto_approve_ceiling)} · block ≥ {formatPaise(policyInfo.rules.payment_hard_block_ceiling)}</span>
                </li>
                <li><span>Revocations</span><span>always human-approved</span></li>
                <li><span>Velocity cap</span><span>{policyInfo.rules.max_actions_per_minute_per_agent}/min per agent</span></li>
              </ul>
              <p className="fine-print">{policyInfo.custody_note}</p>
            </section>
          )}

          {metrics && (
            <section className="panel">
              <h2 className="panel-title">Behavioral profile</h2>
              <p className="fine-print" style={{ marginBottom: '0.6rem' }}>
                Not a fraud detector — flags when an agent drifts from its <em>own</em> baseline (amount, pace,
                counterparties), even on requests policy already allows.
              </p>
              <div className="stat-row">
                <div className="stat">
                  <span className="stat-value">{(metrics.precision * 100).toFixed(1)}<small>%</small></span>
                  <span className="stat-label">precision</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{(metrics.recall * 100).toFixed(1)}<small>%</small></span>
                  <span className="stat-label">recall</span>
                </div>
                <div className="stat stat-warn">
                  <span className="stat-value">{(metrics.false_positive_rate * 100).toFixed(1)}<small>%</small></span>
                  <span className="stat-label">false positives</span>
                </div>
              </div>
              <p className="fine-print">{metrics.note}</p>
            </section>
          )}
        </aside>

        <section className="monitor">
          <Spotlight
            ev={events[0]}
            onReview={handleReview}
            busy={busy}
            velocityCap={policyInfo?.rules?.max_actions_per_minute_per_agent}
          />

          <div className="panel panel-secondary">
            <h2 className="panel-title">Activity history</h2>
            {events.length === 0 && (
              <p className="fine-print empty-state">Past actions will line up here as you send more.</p>
            )}
            {events.length > 1 && (
              <ul className="activity-list">
                {events.slice(1).map((ev, i) => (
                  <li key={i} className={`activity-row activity-${DECISION_META[ev.decision]?.className || ''}`}>
                    <DecisionCode decision={ev.decision} />
                    <span className="feed-action">{ev.tool_call.action}</span>
                    <span className="feed-amount">{formatPaise(ev.tool_call.amount)}</span>
                    <span className="feed-time mono">{timeShort(ev.timestamp)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel">
            <div className="ledger-head">
              <h2 className="panel-title">Tamper-evident chain — the evidence</h2>
              <div className="ledger-actions">
                <button className="btn-ghost" onClick={handleVerify}>Verify integrity</button>
                <a className="btn-ghost" href={`${BACKEND_URL}/audit-log/export.csv`}>Download statement (CSV)</a>
                <button className="btn-ghost btn-ghost-danger" onClick={handleTamperDemo} disabled={auditEntries.length === 0}>
                  Tamper (demo)
                </button>
              </div>
            </div>
            {verifyResult && (
              <p className={verifyResult.valid ? 'verify-ok' : 'verify-bad'}>
                {verifyResult.valid
                  ? '✓ chain verified — every entry hashes correctly from genesis'
                  : `✗ chain broken at entry #${verifyResult.first_broken_seq} — tampering detected`}
              </p>
            )}
            <div className="ledger-wrap">
              {auditEntries.slice().reverse().slice(0, 14).map((e, idx, arr) => (
                <div key={e.seq} className="ledger-row">
                  <span className="ledger-link" aria-hidden="true">{idx < arr.length - 1 ? '│' : '┴'}</span>
                  <span className="ledger-seq">#{e.seq}</span>
                  <span className="ledger-action">{e.payload?.tool_call?.action || '—'}</span>
                  <DecisionCode decision={e.payload?.decision} />
                  <span className="ledger-hash mono">{e.entry_hash.slice(0, 14)}…</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
