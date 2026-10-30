import { Link, useParams } from 'react-router-dom'
import { api, BASE } from '../api'
import { Articles, DECISION_TITLE, Definitions, Downgrade, ErrorBox, Header, Icon, Loading, NumbersTable, Pill, useLoad, when } from '../ui'

const STATUS_LABEL = { proposed: 'Proposed, not yet decided', confirmed: 'Confirmed', overridden: 'Changed by the access body' }

export default function ApplicantView() {
  const { id = '' } = useParams()
  const view = useLoad(() => api.applicant(id), [id])
  const v = view.data

  return (
    <>
      <Header role="Applicant portal"><Link to="/apply" className="small">New application</Link></Header>
      <main className="wrap">
        <Link to="/apply" className="btn small ghost back"><Icon name="back" />Back to applications</Link>
        {view.error && <ErrorBox>{view.error}</ErrorBox>}
        {!v && !view.error && <Loading what={`application ${id}`} />}
        {v && (
          <div className="split">
            <div className="main">
              <section className={`panel verdict ${v.decision}`} aria-labelledby="app-h">
                <span className="mono muted">Application {v.id}</span>
                <div className="panel-head">
                  <h2 id="app-h">Your application</h2>
                  <div className="line">
                    <Pill decision={v.decision} />
                    <span className="pill neutral">{STATUS_LABEL[v.status]}</span>
                  </div>
                </div>
                <dl className="facts">
                  <div><dt>Applicant</dt><dd>{v.request.applicant.name}, {v.request.applicant.organisation}</dd></div>
                  <div><dt>You asked for</dt><dd>{v.request.requested_as}, {v.request.requested_format}</dd></div>
                  <div><dt>Submitted</dt><dd>{when(v.request.submitted)}</dd></div>
                </dl>
                <h3>Purpose</h3>
                <p>{v.request.purpose}</p>
                <h3>Question</h3>
                <p>{v.request.question}</p>
                <h3>Definitions</h3>
                <Definitions lines={v.request.definitions} unclaimed={[]} />
                {v.notes.length > 0 && <div className="callout warn"><h3>Notes on your definitions</h3><ul className="bullets">{v.notes.map((n) => <li key={n}>{n}</li>)}</ul></div>}
              </section>

              <section className={`panel verdict appear ${v.decision}`} aria-labelledby="dec-h">
                <div className="line">
                  <h1 id="dec-h">{v.status === 'proposed' ? `Proposed: ${DECISION_TITLE[v.decision].toLowerCase()}` : DECISION_TITLE[v.decision]}</h1>
                  <Pill decision={v.decision} />
                  <Articles articles={v.articles} />
                </div>
                {/* After an override the officer's reason explains the outcome, not the rules. */}
                {v.request.requested_as === 'health data access application' && v.decision === 'APPROVE_STATISTICAL' && v.status !== 'overridden' && (
                  <Downgrade why={v.request.why_statistics_not_enough} next="To get records, submit a new application." />
                )}
                <p className="reason">{v.reason}</p>
                <p className="small muted">{v.status_text}</p>
                {v.ai_note && <p className="callout info small">{v.ai_note}</p>}
              </section>

              {v.withheld && (
                <div className="callout warn" role="status">
                  <h3 style={{ display: 'flex', gap: 8 }}><Icon name="lock" />Withheld until confirmed</h3>
                  <p>{v.withheld}</p>
                </div>
              )}

              {v.answer && !v.permit && (
                <section className="panel appear" aria-labelledby="res-h">
                  <div className="panel-head">
                    <h2 id="res-h">Your answer</h2>
                    {v.decision === 'APPROVE_STATISTICAL' && (
                      <a className="btn small ghost" href={`${BASE}/applicant/requests/${encodeURIComponent(v.id)}/results.csv`}><Icon name="download" />Download as CSV</a>
                    )}
                  </div>
                  <NumbersTable numbers={v.answer} caption={`Answer to ${v.id}`} />
                  <p className="small muted">Counts below 10 show as &lt;10. Shares and means over fewer than 10 patients show as suppressed. Patients who opted out are left out everywhere.</p>
                </section>
              )}

              {v.permit && (
                <section className="panel appear" aria-labelledby="permit-h">
                  <div className="panel-head">
                    <h2 id="permit-h">Data permit {v.permit.permit_id}</h2>
                    <span className="small muted">Art. 68</span>
                  </div>
                  <dl className="facts">
                    <div><dt>Cohort</dt><dd>{typeof v.answer?.cohort_size === 'number' ? `${v.answer.cohort_size.toLocaleString('en')} patients` : v.permit.cohort}</dd></div>
                    <div><dt>Record types</dt><dd>{v.permit.data.join(', ')}</dd></div>
                    <div><dt>Authorised persons</dt><dd>{v.permit.authorised_persons.join(', ')}</dd></div>
                    <div><dt>Valid</dt><dd>{v.permit.valid_from} to {v.permit.valid_until}</dd></div>
                  </dl>
                  <div className="actions">
                    <Link className="btn primary" to={`/spe/${v.id}?user=${encodeURIComponent(v.permit.authorised_persons[0] ?? '')}`}>Open the secure environment</Link>
                    <span className="small muted">You work on the records there. They cannot be downloaded.</span>
                  </div>
                </section>
              )}

              {v.duties.length > 0 && (
                <section className="callout warn" aria-labelledby="duty-h">
                  <h3 id="duty-h">Your duties</h3>
                  <ul className="bullets">{v.duties.map((d) => <li key={d}>{d}</li>)}</ul>
                </section>
              )}
            </div>

            <aside className="side panel" aria-labelledby="how-h">
              <h2 id="how-h" style={{ fontSize: 20 }}>How we checked</h2>
              <ol className="steps">
                <li><span className="dot done" aria-hidden="true" /><span><strong>Received</strong><span className="small muted">Application {v.id} is in the register.</span></span></li>
                <li><span className="dot done" aria-hidden="true" /><span><strong>Checked automatically</strong><span className="small muted">Mode: {v.mode}</span></span></li>
                <li><span className={`dot ${v.status === 'proposed' ? 'now' : 'done'}`} aria-hidden="true" />
                  <span><strong>{v.status === 'proposed' ? 'Waiting for an officer' : 'Decided by an officer'}</strong>
                    <span className="small muted">{v.status === 'proposed' ? 'The proposal is not a decision yet.' : 'An access body officer made the decision.'}</span></span></li>
              </ol>
              <ul className="plain trace">
                {v.steps.map((s) => {
                  const yes = s.endsWith(': yes')
                  return <li key={s}><Icon name={yes ? 'yes' : 'no'} className={yes ? 'yes' : 'no'} label={yes ? 'yes' : 'no'} /><span>{s.replace(/: (yes|no)$/, '')}</span></li>
                })}
              </ul>
              {v.plan_text.length > 0 && (
                <details>
                  <summary className="small" style={{ cursor: 'pointer' }}>How we read your definitions</summary>
                  <ul className="bullets small" style={{ marginTop: 8 }}>{v.plan_text.map((p) => <li key={p}>{p}</li>)}</ul>
                </details>
              )}
            </aside>
          </div>
        )}
      </main>
    </>
  )
}
