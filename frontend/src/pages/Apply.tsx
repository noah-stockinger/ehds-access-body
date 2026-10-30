import { useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, type ApplicationItem, type AssistHelp, type DefinitionWarning, type FormBody, type Precheck } from '../api'
import { Articles, DECISION_TITLE, Downgrade, ErrorBox, Header, Pill, shortId, useList, useLoad, when } from '../ui'

type Kind = FormBody['requested_as']

const SENT_FILTERS: Record<string, (q: ApplicationItem) => boolean> = {
  Waiting: (q) => q.status === 'proposed',
  Approved: (q) => q.decision === 'APPROVE_STATISTICAL' || q.decision === 'APPROVE_SPE',
  Rejected: (q) => q.decision === 'REJECT',
}

// [short label under the ID, its meaning on hover]
function sentType(q: ApplicationItem) {
  if (q.requested_as === 'health data request') return ['ST', 'Statistics']
  return q.decision === 'APPROVE_STATISTICAL' ? ['SPE→ST', 'Asked for SPE, approved as statistics'] : ['SPE', 'Secure processing environment']
}

function sentStatus(q: ApplicationItem) {
  if (q.status === 'proposed' || !q.decision) return 'Waiting for the access body'
  return q.decision === 'REJECT' ? 'Rejected' : 'Approved'
}

// Demo prefill from the agreed screen design (an R01-like statistics request).
const START = {
  name: 'Dr. Sophie Lechner',
  organisation: 'Danube Institute for Diabetes Research',
  country: 'AT',
  purpose: 'We study regional differences in type 2 diabetes to plan a prevention programme with the regional health authorities.',
  question: 'How many adults have type 2 diabetes in each region and what is the prevalence?',
  definitions: [
    'Adult = aged 18 or older on 31 December 2025.',
    'Type 2 diabetes = any condition with an ICD-10 code starting with E11.',
    'Prevalence = adults with type 2 diabetes / all adults in the region × 100, one decimal.',
    'Report per region: adults, adults with type 2 diabetes and the prevalence.',
  ].join('\n'),
  why: '',
}

export default function Apply() {
  const navigate = useNavigate()
  const [kind, setKind] = useState<Kind>('health data request')
  const [f, setF] = useState(START)
  const [check, setCheck] = useState<Precheck | null>(null)
  const [planOk, setPlanOk] = useState(false)
  const [warnOk, setWarnOk] = useState(false)
  const [statsOk, setStatsOk] = useState(false)
  const [uploaded, setUploaded] = useState<{ request: { id?: string }; warnings: DefinitionWarning[] } | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const apps = useLoad(api.applications, [])
  const sent = useList(apps.data, SENT_FILTERS)
  const assistOn = useLoad(api.assistOn, []).data?.enabled ?? false
  const [help, setHelp] = useState<AssistHelp | null>(null)
  const [assistModel, setAssistModel] = useState<string | undefined>()

  const access = kind === 'health data access application'
  // Any edit makes the last pre-check stale: the applicant must read the new plan.
  const edit = (k: keyof typeof START) => (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setF({ ...f, [k]: e.target.value }); setCheck(null); setPlanOk(false); setWarnOk(false); setStatsOk(false)
  }
  const body = (plan_confirmed: boolean): FormBody => ({
    applicant: { name: f.name, organisation: f.organisation, country: f.country },
    requested_as: kind,
    purpose: f.purpose,
    question: f.question,
    definitions: f.definitions.split('\n').map((l) => l.trim()).filter(Boolean),
    why_statistics_not_enough: access ? f.why : undefined,
    plan_confirmed,
    warnings_confirmed: warnOk,
    assist_model: assistModel,
  })

  async function run(step: () => Promise<void>) {
    setBusy(true); setError(null)
    try { await step() } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }
  const precheck = () => run(async () => { setCheck(await api.precheck(body(false))); setPlanOk(false); setWarnOk(false); setStatsOk(false) })
  const askHelp = () => run(async () => { setHelp(await api.assist(body(false))) })
  // A suggestion only fills the form: the applicant still checks it, reads the plan and confirms.
  const useSuggestion = () => {
    const s = help!.suggestion!
    setF({ ...f, question: s.question, definitions: s.definitions.join('\n') })
    setAssistModel(help!.model); setHelp(null); setCheck(null); setPlanOk(false); setWarnOk(false); setStatsOk(false)
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    run(async () => { const v = await api.submit(body(planOk)); navigate(`/applicant/${v.id}`) })
  }
  const upload = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    run(async () => {
      let request: { id?: string }
      try { request = JSON.parse(await file.text()) } catch { throw new Error(`${file.name} is not valid JSON.`) }
      const warnings = (await api.precheckJson(request)).definition_warnings
      if (warnings.some(mustConfirm)) { setUploaded({ request, warnings }); setWarnOk(false); return }
      await api.submitJson(request)
      navigate(`/applicant/${request.id}`)
    })
  }
  const sendUploaded = () => run(async () => {
    await api.submitJson(uploaded!.request)
    navigate(`/applicant/${uploaded!.request.id}`)
  })
  const warned = check?.definition_warnings.some(mustConfirm) ?? false
  const downgraded = access && check?.likely_decision === 'APPROVE_STATISTICAL'

  return (
    <>
      <Header role="Applicant portal">
        <span className="who">Signed in as <b>DEMO USER</b></span>
      </Header>
      <main className="wrap">
        <div className="split">
          <form className="main panel" onSubmit={submit} aria-labelledby="form-h">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <h1 id="form-h">New application</h1>
              <p className="muted">Fill in the form or upload a request as JSON. The fields follow Art. 67 of the EHDS Regulation.</p>
            </div>

            <fieldset>
              <legend>What do you need?</legend>
              <label className="choice">
                <input type="radio" name="kind" checked={!access} onChange={() => { setKind('health data request'); setCheck(null) }} />
                <span><strong>Anonymised statistics</strong> · health data request, Art. 69<br />
                  <span className="small muted">You get tables of numbers. You never see patient records.</span></span>
              </label>
              <label className="choice">
                <input type="radio" name="kind" checked={access} onChange={() => { setKind('health data access application'); setCheck(null) }} />
                <span><strong>Pseudonymised records</strong> · health data access application, Art. 67 and 68<br />
                  <span className="small muted">You work inside a secure environment and cannot download records. Explain why statistics are not enough.</span></span>
              </label>
            </fieldset>

            <div className="fields3">
              <label className="field">Applicant<input required value={f.name} onChange={edit('name')} autoComplete="name" /></label>
              <label className="field">Organisation<input required value={f.organisation} onChange={edit('organisation')} autoComplete="organization" /></label>
              <label className="field">Country<input required value={f.country} onChange={edit('country')} maxLength={2} /></label>
            </div>
            <label className="field">Purpose<textarea required rows={3} value={f.purpose} onChange={edit('purpose')} /></label>
            <label className="field">Question<input required value={f.question} onChange={edit('question')} /></label>
            <label className="field">Definitions, one per line, in plain English
              <textarea required className="code" rows={5} value={f.definitions} onChange={edit('definitions')} />
              <span className="hint">Write "Term = meaning". End with a "Report per …" line.</span>
            </label>
            {access && (
              <label className="field">Why are anonymised statistics not enough? (Art. 67(2)(e))
                <textarea rows={3} value={f.why} onChange={edit('why')} />
                <span className="hint">Required for records. If it does not show why you need individual-level data, you get anonymised statistics instead.</span>
              </label>
            )}

            {error && <ErrorBox>{error}</ErrorBox>}

            {help && <HelpResult help={help} onUse={useSuggestion} onClose={() => setHelp(null)} />}
            {check && <CheckResult check={check} />}
            {downgraded && <Downgrade why={f.why.trim()} next="To get records, change your reason and check again." />}
            {check && (
              <label className="check">
                <input type="checkbox" checked={planOk} onChange={(e) => setPlanOk(e.target.checked)} />
                <span>The plan above describes what I need.</span>
              </label>
            )}
            {downgraded && (
              <label className="check">
                <input type="checkbox" checked={statsOk} onChange={(e) => setStatsOk(e.target.checked)} />
                <span>I understand that I will get anonymised statistics, not records.</span>
              </label>
            )}
            {warned && <SendAnyway checked={warnOk} onChange={setWarnOk} />}
            {uploaded && (
              <section className="panel" aria-live="polite" style={{ background: 'var(--ground)' }}>
                <h2 style={{ fontSize: 20 }}>Your upload has not been sent yet</h2>
                <Warnings warnings={uploaded.warnings} />
                <SendAnyway checked={warnOk} onChange={setWarnOk} />
                <div className="actions">
                  <button type="button" className="btn primary" disabled={busy || !warnOk} onClick={sendUploaded}>Send anyway</button>
                  <button type="button" className="btn outline" disabled={busy} onClick={() => setUploaded(null)}>Cancel</button>
                </div>
              </section>
            )}

            <div className="actions">
              {!check ? (
                <button type="button" className="btn primary" disabled={busy} onClick={precheck}>{busy ? 'Checking…' : 'Check my draft'}</button>
              ) : (
                <button type="submit" className="btn primary" disabled={busy || !planOk || (warned && !warnOk) || (downgraded && !statsOk)}>{busy ? 'Submitting…' : warned ? 'Send anyway' : 'Submit application'}</button>
              )}
              {assistOn && <button type="button" className="btn outline" disabled={busy} onClick={askHelp}>Help me write this</button>}
              <label className="btn outline">
                Upload JSON instead
                <input type="file" accept="application/json,.json" onChange={upload} className="sr-only" />
              </label>
              {busy && <span className="small muted" role="status">The rules and the model read your request; this takes a few seconds.</span>}
              <span className="small muted">Only the request text is checked. Patient data never leaves the access body.</span>
            </div>
          </form>

          <aside className="side panel flush" aria-labelledby="mine-h">
            <div className="panel-head" style={{ padding: '18px 20px' }}>
              <h2 id="mine-h" style={{ fontSize: 20 }}>Sent Requests</h2>
            </div>
            {sent.controls}
            {apps.error && <div style={{ padding: 20 }}><ErrorBox>{apps.error}</ErrorBox></div>}
            {apps.data && sent.shown.length === 0 && <p className="empty">No requests match.</p>}
            <ul className="queue">
              {sent.shown.map((q) => (
                <li key={q.id} className={q.status === 'proposed' || !q.decision ? 'waiting' : q.decision}>
                  <Link to={`/applicant/${q.id}`}>
                    <span className="idcol">
                      <span className="id" title={q.id}>{shortId(q.id)}</span>
                      <abbr className="type" title={sentType(q)[1]}>{sentType(q)[0]}</abbr>
                    </span>
                    <span className="body"><span className="org">{q.organisation}</span>
                      <span className="st">{sentStatus(q)} · {when(q.received)}</span></span>
                  </Link>
                </li>
              ))}
            </ul>
          </aside>
        </div>
      </main>
    </>
  )
}

const mustConfirm = (w: DefinitionWarning) => w.severity !== 'unsure'
const WARNING_LOOK = {
  wrong: { box: 'danger', title: 'This looks wrong' },
  check: { box: 'warn', title: 'Please check this' },
  unsure: { box: 'info', title: 'We could not confirm this' },
}

function Warnings({ warnings }: { warnings: DefinitionWarning[] }) {
  return (
    <>
      {warnings.map((w) => (
        <div key={w.message} className={`callout ${WARNING_LOOK[w.severity].box}`}>
          <h3>{WARNING_LOOK[w.severity].title}</h3>
          <p className="small">{w.message}</p>
        </div>
      ))}
    </>
  )
}

function SendAnyway({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="check">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>I have seen the warnings on my definitions and want to send them as written.</span>
    </label>
  )
}

function HelpResult({ help, onUse, onClose }: { help: AssistHelp; onUse: () => void; onClose: () => void }) {
  const { suggestion, check } = help
  return (
    <section className="panel" aria-live="polite" style={{ background: 'var(--ground)' }}>
      <h2 style={{ fontSize: 20 }}>Suggestion from an AI model</h2>
      <p className="small muted">{help.model} wrote this. It decides nothing and can be wrong, so please read it. The findings below it come from the rules.</p>
      {help.message && <p>{help.message}</p>}
      {!suggestion && check.likely_decision === 'REJECT' && <p>We can't suggest a rewrite, because the rules would refuse this purpose: {check.reason}</p>}
      {!suggestion && check.likely_decision !== 'REJECT' && <p>The model could not draft definitions for this. Please add more detail to your question.</p>}
      {help.left_out.length > 0 && <p className="callout warn small">Check that nothing got lost. The suggested definitions don't mention: {help.left_out.join(', ')}</p>}
      {suggestion && (
        <div>
          <p className="small"><strong>Question:</strong> {suggestion.question}</p>
          <ul className="bullets small">{suggestion.definitions.map((d) => <li key={d}>{d}</li>)}</ul>
        </div>
      )}
      <Warnings warnings={check.definition_warnings} />
      {check.unclaimed_words.length > 0 && <p className="callout danger small">The rules still can't read: {check.unclaimed_words.join(', ')}</p>}
      <div className="actions">
        {suggestion && <button type="button" className="btn primary" onClick={onUse}>Use this suggestion</button>}
        <button type="button" className="btn outline" onClick={onClose}>{suggestion ? 'Keep my text' : 'Close'}</button>
      </div>
    </section>
  )
}

function CheckResult({ check }: { check: Precheck }) {
  const unread = check.unclaimed_parts ?? []
  const notInData = check.review_reasons.filter((r) => r.startsWith('Sanity: ')).map((r) => r.replace('Sanity: ', ''))
  return (
    <section className={`panel verdict appear ${check.likely_decision}`} aria-live="polite" style={{ background: 'var(--ground)' }}>
      <p className="small"><strong>{check.notice}</strong></p>
      <div className="line">
        <h2 style={{ fontSize: 20 }}>Likely: {DECISION_TITLE[check.likely_decision]}</h2>
        <Pill decision={check.likely_decision} />
        <Articles articles={check.articles} />
      </div>
      <p>{check.reason}</p>
      {check.needs_review && <p className="callout warn small">An officer will look at this application in detail before deciding.</p>}
      {check.plan_text.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 6 }}>How we will read your definitions</h3>
          <ul className="bullets small">{check.plan_text.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}
      <Warnings warnings={check.definition_warnings} />
      {notInData.length > 0 && (
        <div className="callout warn">
          <h3>This will not work as written</h3>
          <ul className="bullets small">{notInData.map((n) => <li key={n}>{n}</li>)}</ul>
        </div>
      )}
      {unread.length > 0 && (
        <div className="callout danger">
          <h3>What we could not read</h3>
          <ul className="bullets small">{unread.map((u) => <li key={u}>{u}</li>)}</ul>
          {unread.some((u) => /\b(19|20)\d{2}\b|start_date|onset_date|\byears?\b/i.test(u)) && (
            <p className="small">Diagnoses cannot be limited to a date range yet: every diagnosis counts, whatever its date.</p>
          )}
          <p className="small">As written, no numbers would be computed and an officer would have to look at it first. Rephrase these parts, then check again.</p>
        </div>
      )}
      {check.notes.length > 0 && <ul className="bullets small muted">{check.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
    </section>
  )
}
