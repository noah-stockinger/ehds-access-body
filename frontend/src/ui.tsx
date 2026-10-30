import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import type { Decision, Numbers } from './api'

export const DECISION_LABEL: Record<Decision, string> = {
  REJECT: 'Reject',
  APPROVE_STATISTICAL: 'Statistics',
  APPROVE_SPE: 'Data permit · SPE',
}

export const DECISION_TITLE: Record<Decision, string> = {
  REJECT: 'Rejected',
  APPROVE_STATISTICAL: 'Approved as anonymised statistics',
  APPROVE_SPE: 'Approved for a secure processing environment',
}

// Form IDs are F-<timestamp>: the last digits are the ones that differ between applications.
export const shortId = (id: string) => (id.startsWith('F-') ? `F-${id.slice(-4)}` : id)

export function useLoad<T>(load: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(load, deps)
  const reload = useCallback(() => {
    setError(null)
    return run().then(setData, (e: Error) => setError(e.message))
  }, [run])
  useEffect(() => { setData(null); reload() }, [reload])
  return { data, error, reload, setData }
}

type Listed = { id: string; organisation: string; received: string }
const SORTS: Record<string, [string, (a: Listed, b: Listed) => number]> = {
  newest: ['Newest first', (a, b) => b.received.localeCompare(a.received) || a.id.localeCompare(b.id)],
  oldest: ['Oldest first', (a, b) => a.received.localeCompare(b.received) || a.id.localeCompare(b.id)],
  az: ['Name A to Z', (a, b) => a.organisation.localeCompare(b.organisation) || a.id.localeCompare(b.id)],
  za: ['Name Z to A', (a, b) => b.organisation.localeCompare(a.organisation) || a.id.localeCompare(b.id)],
}

/** Sort, filter and search for the inbox and the sent requests. `filters`: label → does this item belong? */
export function useList<T extends Listed>(items: T[] | null, filters: Record<string, (item: T) => boolean>) {
  const [sort, setSort] = useState('newest')
  const [filter, setFilter] = useState('All')
  const [search, setSearch] = useState('')
  const words = search.trim().toLowerCase()
  const shown = (items ?? [])
    .filter((q) => filter === 'All' || filters[filter]?.(q))
    .filter((q) => !words || `${q.organisation} ${q.id}`.toLowerCase().includes(words))
    .sort(SORTS[sort][1])
  const controls = (
    <div className="listctl">
      <input type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name or ID" aria-label="Search name or ID" />
      <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort by">
        {Object.entries(SORTS).map(([key, [label]]) => <option key={key} value={key}>{label}</option>)}
      </select>
      <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Show only">
        {['All', ...Object.keys(filters)].map((f) => <option key={f}>{f}</option>)}
      </select>
    </div>
  )
  return { shown, controls }
}

export function Footer() {
  return (
    <footer className="foot">
      <div className="wrap">
        <p><b>Prototype for the AIM Healthcare Hackathon Vienna 2026.</b> Synthetic data only: do not enter real personal data.</p>
        <ul className="arts">
          <li><a className="pill neutral" href="https://eur-lex.europa.eu/eli/reg/2025/327/oj/eng">EHDS, Reg. (EU) 2025/327, Chapter IV</a></li>
          <li className="pill neutral">Every decision by a person</li>
          <li className="pill neutral">Full audit log</li>
          <li className="pill neutral">Patients' opt-outs respected (Art. 71)</li>
        </ul>
        <p className="small">
          <a href="https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng">EU AI Act</a>: an AI model helps prepare proposals; staff oversee and decide, and each step is logged. This prototype has not been through a conformity assessment and holds no certification.
        </p>
      </div>
    </footer>
  )
}

export function DemoBar() {
  const links: [string, string][] = [['/apply', 'Applicant'], ['/staff', 'Staff']]
  return (
    <nav className="demobar" aria-label="Demo roles">
      <div className="wrap">
        <span>Demo · switch role:</span>
        {links.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
      </div>
    </nav>
  )
}

export function Header({ role, staff, children }: { role: string; staff?: boolean; children?: ReactNode }) {
  return (
    <header className={staff ? 'head staff' : 'head'}>
      <div className="wrap">
        <div className="brand"><b>Health Data Access Body</b><span>{role}</span></div>
        {children}
      </div>
    </header>
  )
}

export function Pill({ decision }: { decision: Decision }) {
  return <span className={`pill ${decision}`}>{DECISION_LABEL[decision]}</span>
}

// The applicant asked for records but the rules offer statistics (S-003 rule 4). The examples match rules.py SPE_JUSTIFICATION.
export function Downgrade({ why, next }: { why?: string | null; next: string }) {
  return (
    <div className="callout warn" role="status">
      <h3>You asked for pseudonymised records. This gives you anonymised statistics instead.</h3>
      <p className="small">We could not find a reason why statistics are not enough.{why && <> You wrote: “{why}”</>}</p>
      <p className="small">{next} Explain why you need individual-level data, for example to link records of each patient over time or to train a model on patient histories.</p>
    </div>
  )
}

export function Articles({ articles }: { articles: string[] }) {
  return <span className="arts">{articles.map((a) => <span className="art" key={a}>Art. {a}</span>)}</span>
}

export function ErrorBox({ children }: { children: ReactNode }) {
  return <div className="callout danger" role="alert">{children}</div>
}

export function Loading({ what }: { what: string }) {
  return <p className="skeleton" aria-live="polite">Loading {what}…</p>
}

type IconName = 'yes' | 'no' | 'bad' | 'lock' | 'flag' | 'download' | 'back'
const PATHS: Record<IconName, ReactNode> = {
  yes: <path d="M4 10.5l4 4 8-9" />,
  no: <path d="M5 10h10" />,
  bad: <path d="M5 5l10 10M15 5L5 15" />,
  lock: <><rect x="4" y="9" width="12" height="8" rx="1.5" /><path d="M7 9V6.5a3 3 0 016 0V9" /></>,
  flag: <path d="M5 17V3.5M5 4h9l-2 3.5 2 3.5H5" />,
  download: <path d="M10 3v10M6 9l4 4 4-4M4 16h12" />,
  back: <path d="M16 10H4M9 5l-5 5 5 5" />,
}

export function Icon({ name, label, className }: { name: IconName; label?: string; className?: string }) {
  return (
    <svg className={`ico ${className ?? ''}`} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      {PATHS[name]}
    </svg>
  )
}

export function when(ts: string) {
  return new Date(ts).toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

// "adults_with_type_2_diabetes" → "Adults with type 2 diabetes"; "_pct" → " %"
function heading(key: string) {
  const s = key.replace(/_pct$/, ' %').replace(/_/g, ' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

// Shares and means are reported with one decimal (S-017); JSON drops the trailing ".0".
const oneDecimal = (key: string) => /_pct$|mean/.test(key)

function Cell({ v, k }: { v: unknown; k: string }) {
  if (typeof v === 'number') return <>{oneDecimal(k) ? v.toFixed(1) : v.toLocaleString('en')}</>
  if (v === null || v === undefined) return <span className="small-cell">–</span>
  // "<10" and "suppressed" are small-cell results; never show them as 0
  return <span className="small-cell">{String(v)}</span>
}

/** Group → measures table, or a flat list of figures (e.g. the SPE cohort size). */
export function NumbersTable({ numbers, caption }: { numbers: Numbers; caption: string }) {
  const rows = Object.entries(numbers)
  const grouped = rows.every(([, v]) => v !== null && typeof v === 'object')
  if (!grouped) {
    return (
      <dl className="facts">
        {rows.map(([k, v]) => <div key={k}><dt>{heading(k)}</dt><dd><Cell v={v} k={k} /></dd></div>)}
      </dl>
    )
  }
  const cols = [...new Set(rows.flatMap(([, v]) => Object.keys(v as object)))]
  return (
    <div className="tablebox">
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead><tr><th scope="col">Group</th>{cols.map((c) => <th scope="col" className="num" key={c}>{heading(c)}</th>)}</tr></thead>
        <tbody>
          {rows.map(([g, v]) => (
            <tr key={g}><th scope="row">{g}</th>{cols.map((c) => <td className="num" key={c}><Cell v={(v as Record<string, unknown>)[c]} k={c} /></td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Definitions with the parts the parser could not read highlighted (S-056), and only those: the same word can be fine elsewhere. */
export function Definitions({ lines, unclaimed }: { lines: string[]; unclaimed: string[] }) {
  const parts = unclaimed.filter(Boolean).map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const pattern = parts.length ? new RegExp(`(${parts.join('|')})`, 'i') : null
  return (
    <ol className="defs">
      {lines.map((line, i) => (
        <li key={i}>
          {pattern ? line.split(pattern).map((part, j) => (j % 2 ? <mark className="unclaimed" key={j}>{part}</mark> : part)) : line}
        </li>
      ))}
    </ol>
  )
}
