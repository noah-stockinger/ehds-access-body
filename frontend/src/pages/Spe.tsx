import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorBox, Header, Icon, Loading, useLoad } from '../ui'
import { LogList } from './Staff'

export default function Spe() {
  const { id = '' } = useParams()
  const [params] = useSearchParams()
  const user = params.get('user') ?? ''
  const spe = useLoad(() => (user ? api.spe(id, user) : Promise.resolve(null)), [id, user])
  const log = useLoad(() => api.log(id), [id, user])
  const [blocked, setBlocked] = useState<string | null>(null)

  async function download() {
    try { await api.download(id, user) } catch (e) { setBlocked((e as Error).message) }
    log.reload()
  }
  const [starting, setStarting] = useState(false)
  const [rstudioError, setRstudioError] = useState<string | null>(null)
  async function openRStudio() {
    setStarting(true); setRstudioError(null)
    // Opened before the await: browsers block a new tab that does not come straight from the click.
    const tab = window.open('', '_blank')
    if (tab) { tab.opener = null; tab.document.body.textContent = 'Starting RStudio…' }
    try {
      const { url } = await api.rstudio(id, user)
      if (tab) tab.location.href = url
      else setRstudioError('Your browser blocked the new tab. Allow pop-ups for this page and try again.')
    } catch (e) { tab?.close(); setRstudioError((e as Error).message) } finally { setStarting(false) }
    log.reload()
  }
  const p = spe.data?.permit
  const proof = spe.data?.proof
  const speEvents = log.data?.filter((e) => e.action.startsWith('spe_')) ?? []

  return (
    <>
      <Header role={`Secure processing environment · ${id}`}>
        <span className="who">Signed in as <b>DEMO USER</b></span>
      </Header>
      <main className="wrap">
        <Link to={`/applicant/${id}`} className="btn small ghost back"><Icon name="back" />Back to application</Link>
        {!user &&<div className="panel"><p>Open this workspace from the data permit on your application.</p></div>}
        {spe.error && (
          <div className="callout danger" role="alert">
            <h3 style={{ display: 'flex', gap: 8 }}><Icon name="lock" />Access refused</h3>
            <p>{spe.error}</p>
            <p className="small">This attempt was logged.</p>
          </div>
        )}
        {user && !spe.data && !spe.error && <Loading what="the workspace" />}
        {p && proof && (
          <div className="split">
            <section className="main" aria-labelledby="ws-h">
              <div className="panel verdict APPROVE_SPE">
                <h1 id="ws-h">Your secure workspace</h1>
                <p className="reason">Work with the permit's records in RStudio. They are ready as <code>con</code> in the R console.</p>
                <div className="arts">
                  <span className="pill neutral">No network</span>
                  <span className="pill neutral">Read-only data</span>
                  <span className="pill neutral">No downloads</span>
                </div>
                <div className="actions">
                  <button type="button" className="btn primary" disabled={starting} onClick={openRStudio}>{starting ? 'Starting RStudio…' : 'Open RStudio'}</button>
                </div>
                {rstudioError && <ErrorBox>{rstudioError}</ErrorBox>}
              </div>

              <div className="panel">
                <h2>Data in this workspace</h2>
                <p className="small muted">Only the cohort and the record types in the permit.</p>
                <div className="terminal" aria-label="Proof of what the workspace holds">
                  <span className="p">Proof, computed from the workspace file</span>
                  <span>{'cohort size'.padEnd(24, '.')} {proof.cohort_size.toLocaleString('en')}</span>
                  {Object.entries(proof.tables).map(([t, n]) => <span key={t}>{t.padEnd(24, '.')} {n.toLocaleString('en')} rows</span>)}
                  <span>{'opted-out IDs inside'.padEnd(24, '.')} <b style={{ color: '#7fd6c4' }}>{proof.opted_out_ids_inside}</b></span>
                </div>
              </div>

              <div className="panel">
                <h2>Taking data out</h2>
                <p>Records stay in this workspace. Every attempt to download them is refused and logged (Art. 73).</p>
                <div className="actions">
                  <button type="button" className="btn ghost" onClick={download}><Icon name="download" />Try to download the records</button>
                </div>
                {blocked && (
                  <div className="callout danger appear" role="alert">
                    <h3 style={{ display: 'flex', gap: 8 }}><Icon name="lock" />Download blocked</h3>
                    <p>{blocked}</p>
                    <p className="small">This attempt was logged in the register.</p>
                  </div>
                )}
              </div>

              <div className="panel">
                {/* A refused download opens the log: the demo must show the attempt being logged (S-020, S-040). */}
                <details className="toggle" open={!!blocked}>
                  <summary><h3>Activity log ({speEvents.length})</h3></summary>
                  <LogList events={speEvents} />
                </details>
              </div>
            </section>

            <aside className="side panel" aria-labelledby="permit-h">
              <h2 id="permit-h">Data permit {p.permit_id}</h2>
              <p className="small muted">Art. 68 · {p.organisation}</p>
              <dl className="facts stack">
                <div><dt>Purpose</dt><dd>{p.purpose}</dd></div>
                <div><dt>Cohort</dt><dd>{p.cohort}</dd></div>
                <div><dt>Format</dt><dd>{p.format}</dd></div>
                <div><dt>Authorised persons</dt><dd>{p.authorised_persons.join(', ')}</dd></div>
                <div><dt>Valid</dt><dd>{p.valid_from} to {p.valid_until}</dd></div>
                <div><dt>Tools</dt><dd>{p.spe_tools.join(', ')}</dd></div>
                <div><dt>Fees</dt><dd>{p.fees}</dd></div>
              </dl>
              <div>
                <h3 style={{ marginBottom: 6 }}>Conditions of use</h3>
                <ul className="bullets small">{p.conditions_of_use.map((c) => <li key={c}>{c}</li>)}</ul>
              </div>
            </aside>
          </div>
        )}
      </main>
    </>
  )
}
