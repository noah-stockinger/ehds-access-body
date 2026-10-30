import { useState, type FormEvent } from 'react'
import { NavLink, useParams } from 'react-router-dom'
import { api, type Decision, type Explanations, type Flag, type KevAnswer, type LogEvent, type QueueItem, type TraceStep } from '../api'
import { Articles, DECISION_LABEL, DECISION_TITLE, Definitions, ErrorBox, Header, Icon, Loading, NumbersTable, Pill, shortId, useList, useLoad, when } from '../ui'

const STATUS_LABEL = { proposed: 'To confirm', confirmed: 'Confirmed', overridden: 'Overridden' }
const CONFIRM_LABEL: Record<Decision, string> = {
  REJECT: 'Confirm rejection',
  APPROVE_STATISTICAL: 'Confirm and release statistics',
  APPROVE_SPE: 'Confirm and issue data permit',
}

// Question IDs from docs/DESIGN.md (K1–K6)
const KEV_QUESTION: Record<string, string> = {
  K1_category: 'Which Art. 54 category does the purpose fall under?',
  K2_negated: 'Is the prohibited use negated, hypothetical or reported?',
  K3_individual_level: 'Does the applicant say why statistics are not enough?',
  K4_plan_faithful: 'Does the plain-English plan match the definitions?',
  K5_per_patient: 'Does the report line ask for per-patient output?',
  K6_identifies_people: 'Could the results be used to identify people?',
}

const INBOX_FILTERS: Record<string, (q: QueueItem) => boolean> = {
  'To confirm': (q) => q.status === 'proposed',
  'Needs review': (q) => q.needs_review,
  Confirmed: (q) => q.status === 'confirmed',
  Overridden: (q) => q.status === 'overridden',
  Rejections: (q) => q.decision === 'REJECT',
  Statistics: (q) => q.decision === 'APPROVE_STATISTICAL',
  'Data permits': (q) => q.decision === 'APPROVE_SPE',
}

const shown = (v: KevAnswer['rules']) =>
  Array.isArray(v) ? v.map((x) => x.replace(/_/g, ' ')).join(', ') : v === true ? 'yes' : v === false ? 'no' : '–'

function kevAnswer(k: KevAnswer) {
  const a = k.answer
  if (a.type === 'choice') return a.choice.replace(/_/g, ' ')
  if (a.type === 'noul' && a.noul !== undefined) return `${a.noul >= 0.5 ? 'Yes' : 'No'} (p yes = ${a.noul.toFixed(2)})`
  return String(a.score ?? '–')
}

// When the decision model changed the outcome (backend trace step "1b decision model …", kev.MODEL_STEP), say so
// plainly: it found a prohibited purpose the keywords missed, overruled a keyword rejection, or was overruled itself.
function ModelEffect({ trace, decision }: { trace: TraceStep[]; decision: Decision }) {
  const step = trace.find((s) => s.rule.startsWith('1b decision model'))
  if (!step) return null
  const [reading, ...rest] = step.evidence
  const title = step.matched ? 'The model found a prohibited purpose the keyword rules missed'
    : decision === 'REJECT' ? 'Keyword rejection kept, although the model reads the purpose as allowed'
      : 'The model overruled the keyword rule'
  const what = step.matched ? 'Check the purpose yourself before you confirm the rejection.'
    : decision === 'REJECT' ? 'The request contains text addressed to the system, so the model may not clear it.'
      : 'The proposal is an approval for you to check; the keyword evidence is in the trace below.'
  return (
    <div className={`callout ${step.matched || decision === 'REJECT' ? 'danger' : 'info'}`} role="note">
      <h3>{title}</h3>
      <p className="small" style={{ margin: 0 }}>{what}</p>
      <ul className="bullets small">{[reading, ...rest].map((e) => <li key={e}>{e}</li>)}</ul>
    </div>
  )
}

function storedOfficer() {
  try { return localStorage.getItem('officer') ?? '' } catch { return '' }
}

export default function Staff() {
  const { id } = useParams()
  const [officer, setOfficer] = useState(storedOfficer)
  const queue = useLoad(api.queue, [])
  const inbox = useList(queue.data, INBOX_FILTERS)
  const saveOfficer = (v: string) => {
    setOfficer(v)
    try { localStorage.setItem('officer', v) } catch { /* private window: keep it in memory */ }
  }
  const open = queue.data?.filter((q) => q.status === 'proposed').length ?? 0

  return (
    <>
      <Header role="Staff console" staff>
        <label className="who">Officer
          <input value={officer} onChange={(e) => saveOfficer(e.target.value)} placeholder="Your name" aria-label="Officer name" />
        </label>
      </Header>
      <main className="wrap"><div className="split">
        <section className="side panel flush" aria-labelledby="inbox-h">
          <div className="panel-head" style={{ padding: '18px 20px' }}>
            <h1 id="inbox-h" style={{ fontSize: 22 }}>Inbox</h1>
            {queue.data && <span className="small muted">{queue.data.length} applications · {open} to confirm</span>}
          </div>
          {queue.error && <div style={{ padding: 20 }}><ErrorBox>{queue.error}</ErrorBox></div>}
          {!queue.data && !queue.error && <Loading what="the inbox" />}
          {queue.data?.length === 0 && <p className="empty">No applications yet. Run <code>make seed</code> or submit one.</p>}
          {queue.data && queue.data.length > 0 && inbox.controls}
          {queue.data && queue.data.length > 0 && inbox.shown.length === 0 && <p className="empty">No applications match.</p>}
          <ul className="queue">
            {inbox.shown.map((q) => (
              <li key={q.id}>
                <NavLink to={`/staff/${q.id}`} aria-current={q.id === id ? 'page' : undefined}>
                  <span className="id" title={q.id}>{shortId(q.id)}</span>
                  <span className="body">
                    <span className="org">{q.organisation}</span>
                    <span className="st">{STATUS_LABEL[q.status]} · {q.mode} · {when(q.received)}</span>
                  </span>
                  <span className="tags">
                    <Pill decision={q.decision} />
                    {q.needs_review && <span className="pill review"><Icon name="flag" className="" />Review</span>}
                  </span>
                </NavLink>
              </li>
            ))}
          </ul>
        </section>
        <div className="main">
          {id ? <Detail key={id} id={id} officer={officer} onChange={queue.reload} />
            : <div className="panel"><p className="muted">Pick an application from the inbox.</p></div>}
        </div>
      </div></main>
    </>
  )
}

function Detail({ id, officer, onChange }: { id: string; officer: string; onChange: () => void }) {
  const view = useLoad(() => api.staff(id), [id])
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  const [overriding, setOverriding] = useState(false)

  if (view.error) return <ErrorBox>{view.error}</ErrorBox>
  if (!view.data) return <div className="panel"><Loading what={id} /></div>
  const v = view.data
  const a = v.answer
  const noPermit = a.decision === 'APPROVE_SPE' && !a.permit
  const r = v.request

  async function act(run: () => Promise<unknown>) {
    setBusy(true); setActionError(null)
    try {
      await run()
      setOverriding(false)
      await view.reload()
      onChange()
    } catch (e) { setActionError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <>
      <section className={`panel verdict appear ${a.decision}`} aria-labelledby="detail-h">
        <span className="mono muted">{v.id} · {r.requested_as} · received {when(v.received)}</span>
        <h2 id="detail-h">{v.applicant.organisation}</h2>
        <div className="line">
          <Pill decision={a.decision} />
          <Articles articles={a.articles} />
          <span className="pill neutral">{v.status === 'proposed' ? 'Proposal, not yet decided' : `${STATUS_LABEL[v.status]} by ${v.staff}`}</span>
          <span className="pill neutral">Mode: {a.mode}</span>
          {a.needs_review && <span className="pill review"><Icon name="flag" />Needs review</span>}
          {r.requested_as === 'health data access application' && a.decision === 'APPROVE_STATISTICAL' && <span className="pill review">Requested SPE → Statistics</span>}
        </div>
        <p className="reason">{a.reason}</p>
        <ModelEffect trace={a.trace} decision={a.decision} />
        {v.status === 'overridden' && (
          <p className="small muted">The rules first proposed: {DECISION_LABEL[v.proposal.decision]} (Art. {v.proposal.articles.join(', ')}).</p>
        )}
        {noPermit && <p className="callout warn small">No data permit can be issued for this application as written, so it cannot be confirmed. Ask the applicant to correct it, or override.</p>}
        <div className="actions">
          {v.status === 'proposed' && !noPermit && (
            <button type="button" className={`btn ${a.decision === 'REJECT' ? 'danger' : 'go'}`} disabled={busy}
              onClick={() => act(() => api.confirm(id, officer))}>{busy ? 'Saving…' : CONFIRM_LABEL[a.decision]}</button>
          )}
          <button type="button" className="btn ghost" disabled={busy} aria-expanded={overriding} onClick={() => setOverriding(!overriding)}>
            Override decision
          </button>
          <span className="small muted">
            {v.status === 'proposed' ? 'Nothing reaches the applicant until you confirm or override.' : 'The applicant sees this decision.'}
          </span>
        </div>
        {actionError && <ErrorBox>{actionError}</ErrorBox>}
        {overriding && <OverrideForm current={a.decision} busy={busy} onSubmit={(body) => act(() => api.override(id, { staff: officer, ...body }))} />}
      </section>

      <WhatToCheck explanations={v.explanations} decided={v.status !== 'proposed'} />

      <section className="panel" aria-labelledby="req-h">
        <h3 id="req-h">What was asked</h3>
        <blockquote className="quote">{r.purpose}</blockquote>
        <p><strong>Question:</strong> {r.question}</p>
        <div className="grid2">
          <div>
            <h3 style={{ marginBottom: 8 }}>Definitions as written</h3>
            <Definitions lines={r.definitions} unclaimed={a.unclaimed_parts ?? []} />
            {a.unclaimed_words.length > 0 && <p className="small" style={{ marginTop: 8, color: 'var(--reject)' }}>Not understood: {(a.unclaimed_parts?.length ? a.unclaimed_parts : a.unclaimed_words).join(a.unclaimed_parts?.length ? ' / ' : ', ')}</p>}
            {a.notes.length > 0 && <div className="callout warn" style={{ marginTop: 8 }}><h3>Notes on the definitions</h3><ul className="bullets">{a.notes.map((n) => <li key={n}>{n}</li>)}</ul></div>}
          </div>
          <div>
            <h3 style={{ marginBottom: 8 }}>How the app reads them</h3>
            {a.plan_text.length ? <ul className="bullets small">{a.plan_text.map((p) => <li key={p}>{p}</li>)}</ul>
              : <p className="small muted">No query plan: rejected requests are never computed.</p>}
          </div>
        </div>
      </section>

      <div className="grid2">
        <section className="panel" aria-labelledby="trace-h">
          <h3 id="trace-h">Rules checked, in order</h3>
          <p className="small muted">Open a rule to see what it is, what was checked and why. A tick means the rule matched, which is not always good: a match on a prohibited purpose rejects.</p>
          <ol className="plain trace">
            {a.trace.map((s) => (
              <RuleStep key={s.rule} step={s} explanation={v.explanations.rules[s.rule] ?? null} />
            ))}
          </ol>
        </section>
        <section className="panel" aria-labelledby="kev-h">
          <h3 id="kev-h">What the model answered</h3>
          {a.kev.length === 0 ? <p className="muted small">No model used. Mode: {a.mode}. The decision follows fixed rules only.</p> : (
            <ul className="plain">
              {a.kev.map((k) => (
                <li key={k.question} className={`callout ${k.agrees === null ? 'info' : k.agrees ? 'ok' : 'warn'}`}>
                  <span className="small">{k.instructions ?? KEV_QUESTION[k.question] ?? k.question}</span>
                  <strong>{kevAnswer(k)}</strong>
                  <span className="mono">confidence {k.confidence.toFixed(2)} · {k.model} · {k.agrees === null ? 'no rule to compare'
                    : k.agrees ? 'agrees with the rules' : `rules say: ${shown(k.rules)}`}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="small muted">{a.mode.endsWith('-led')
            ? 'In this mode the model can reject a request or turn a keyword rejection into a review. It never approves on its own, and you make the decision.'
            : 'The model only answers these questions. The rules propose and you decide.'}</p>
        </section>
      </div>

      {a.answer && (
        <section className="panel" aria-labelledby="num-h">
          <div className="panel-head"><h3 id="num-h">Result</h3><span className="small muted">{v.status === 'proposed' ? 'Withheld from the applicant until you confirm' : 'Released to the applicant'}</span></div>
          <NumbersTable numbers={a.answer} caption={`Result of ${v.id}`} />
        </section>
      )}

      <section className="panel" aria-labelledby="log-h">
        <details className="toggle">
          <summary><h3 id="log-h">Audit log ({v.log.length})</h3></summary>
          <LogList events={v.log} />
        </details>
      </section>
    </>
  )
}

function FlagItem({ flag }: { flag: Flag }) {
  return (
    <li className="flag">
      <p><b>Why it was flagged:</b> {flag.why}</p>
      <p><b>What to check:</b> {flag.check}</p>
      <details>
        <summary className="small">The system's own message</summary>
        <p className="small mono">{flag.text}</p>
      </details>
    </li>
  )
}

// The first thing an officer reads: why the system raised this, then what they are responsible for checking.
function WhatToCheck({ explanations: e, decided }: { explanations: Explanations; decided: boolean }) {
  return (
    <section className="panel" aria-labelledby="check-h">
      <h3 id="check-h">{decided ? 'What was to be checked' : 'What you need to check'}</h3>
      {e.review.length > 0 ? (
        <div className="callout warn">
          <h3>{e.review.length === 1 ? '1 point needs your judgement' : `${e.review.length} points need your judgement`}</h3>
          <ul className="plain flags">{e.review.map((f) => <FlagItem key={f.text} flag={f} />)}</ul>
        </div>
      ) : <p className="small muted">The system flagged nothing for this application. That does not replace your own check.</p>}
      <div>
        <h4>Before you decide</h4>
        <ul className="bullets small">{e.checklist.map((c) => <li key={c}>{c}</li>)}</ul>
      </div>
      {e.signals.length > 0 && (
        <div className="callout info">
          <h3>Signals (these change nothing by themselves)</h3>
          <ul className="plain flags">{e.signals.map((f) => <FlagItem key={f.text} flag={f} />)}</ul>
        </div>
      )}
    </section>
  )
}

function RuleStep({ step: s, explanation: x }: { step: TraceStep; explanation: Explanations['rules'][string] }) {
  return (
    <li>
      <Icon name={s.matched ? 'yes' : 'no'} className={s.matched ? 'yes' : 'no'} label={s.matched ? 'matched' : 'not matched'} />
      <details className="rule">
        <summary>{s.rule}{s.evidence.map((e) => <span className="ev" key={e}>{e}</span>)}</summary>
        {x ? (
          <dl className="facts stack">
            <div><dt>What this rule is</dt><dd>{x.what}</dd></div>
            <div><dt>What was checked</dt><dd>{x.checked}</dd></div>
            <div><dt>Why it exists</dt><dd>{x.why}</dd></div>
            <div><dt>Result here</dt><dd>{s.matched ? x.matched : x.not_matched}</dd></div>
          </dl>
        ) : <p className="small muted">No explanation is recorded for this rule.</p>}
      </details>
    </li>
  )
}

function OverrideForm({ current, busy, onSubmit }: { current: Decision; busy: boolean; onSubmit: (b: { decision: Decision; reason: string; articles: string[] }) => void }) {
  const options = (Object.keys(DECISION_TITLE) as Decision[]).filter((d) => d !== current)
  const [decision, setDecision] = useState<Decision>(options[0])
  const [reason, setReason] = useState('')
  const [articles, setArticles] = useState(current === 'REJECT' ? '53, 69' : '54')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({ decision, reason: reason.trim(), articles: articles.split(/[,\s]+/).filter(Boolean) })
  }
  return (
    <form className="panel" style={{ background: 'var(--ground)' }} onSubmit={submit}>
      <h3>Override the proposal</h3>
      <div className="fields3">
        <label className="field">New decision
          <select value={decision} onChange={(e) => setDecision(e.target.value as Decision)}>
            {options.map((d) => <option key={d} value={d}>{DECISION_TITLE[d]}</option>)}
          </select>
        </label>
        <label className="field">Articles
          <input value={articles} onChange={(e) => setArticles(e.target.value)} />
          <span className="hint">Comma-separated, e.g. 54</span>
        </label>
      </div>
      <label className="field">Reason the applicant will read
        <textarea rows={3} required value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      <div className="actions">
        <button type="submit" className="btn primary" disabled={busy || !reason.trim()}>{busy ? 'Saving…' : 'Save override'}</button>
        <span className="small muted">Saved in the register with your name.</span>
      </div>
    </form>
  )
}

const ACTION_TEXT: Record<string, string> = {
  received: 'Application received',
  decided: 'Decision proposed',
  numbers_computed: 'Numbers computed',
  results_exported: 'Results exported as CSV',
  definitions_read: 'Definitions read',
  confirmed: 'Staff confirmed',
  overridden: 'Staff overrode the proposal',
  spe_created: 'Secure environment created',
  spe_opened: 'Secure environment opened',
  spe_deleted: 'Secure environment deleted',
  spe_rstudio_opened: 'RStudio opened',
  spe_rstudio_stopped: 'RStudio session ended',
}

function describe(e: LogEvent) {
  const d = e.detail ?? {}
  if (e.action === 'rule_checked') return `${d.rule} · ${d.matched ? 'matched' : 'not matched'}`
  if (e.action === 'model_answered') {
    const k = d as unknown as KevAnswer
    return `${KEV_QUESTION[k.question] ?? k.question} · ${kevAnswer(k)}`
  }
  if (e.action === 'review_reason') return `Needs review: ${d.reason}`
  if (e.action === 'signal') return `Signal: ${d.signal}`
  if (e.action === 'definition_warning') return `Definition warning: ${d.message}`
  if (e.action === 'numbers_computed') return d.computed ? 'Numbers computed' : 'No numbers computed'
  if (e.action === 'query_run') return `Database query (SQL) · ${d.matches_computed_numbers ? 'gives the same numbers' : 'does NOT give the same numbers, check it'}`
  const to = d.to ?? d.decision
  const decision = typeof to === 'string' ? DECISION_LABEL[to as Decision] ?? to : null
  const why = typeof d.why === 'string' ? d.why : null
  const base = ACTION_TEXT[e.action] ?? e.action.replace(/^spe_(\w+)_refused$/, 'Refused: $1').replace(/_/g, ' ')
  return [base, decision, why].filter(Boolean).join(' · ')
}

// Every entry opens to what was recorded for it (S-038): rule evidence, or the model's question, input and probabilities.
function LogDetail({ detail }: { detail: Record<string, unknown> }) {
  return (
    <dl className="facts stack">
      {Object.entries(detail).map(([key, value]) => (
        <div key={key}>
          <dt>{key.replace(/_/g, ' ')}</dt>
          <dd><pre>{typeof value === 'string' ? value : JSON.stringify(value, null, 2)}</pre></dd>
        </div>
      ))}
    </dl>
  )
}

export function LogList({ events }: { events: LogEvent[] }) {
  if (!events.length) return <p className="muted small">Nothing logged yet.</p>
  return (
    <ol className="plain log">
      {events.map((e) => (
        <li key={e.id}>
          <span className="t">{new Date(e.ts).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
          <details className={e.action.endsWith('_refused') ? 'refused' : undefined}>
            <summary>{describe(e)} <span className="actor">· {e.actor}</span></summary>
            {Object.keys(e.detail ?? {}).length > 0 ? <LogDetail detail={e.detail} /> : <p className="small muted">Nothing more was recorded.</p>}
          </details>
        </li>
      ))}
    </ol>
  )
}
