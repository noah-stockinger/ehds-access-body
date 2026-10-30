// Thin client for docs/API.md. Shapes follow src/hdab/contracts.py and src/hdab/views.py.
export const BASE = import.meta.env.VITE_API ?? 'http://127.0.0.1:8000'

export type Decision = 'REJECT' | 'APPROVE_STATISTICAL' | 'APPROVE_SPE'
export type Status = 'proposed' | 'confirmed' | 'overridden'
type Value = number | string | null
export type Numbers = Record<string, Value | Record<string, Value>>

export interface Applicant { name: string; organisation: string; country: string }
export interface TraceStep { rule: string; matched: boolean; evidence: string[] }
// One model question (K1–K6). `rules` / `agrees` are null when no rule answers the same question.
export interface KevAnswer {
  question: string
  instructions?: string
  answer: { type: 'choice'; choice: string; confidence: number; probabilities: Record<string, number> } | { type: 'noul' | 'score'; noul?: number; score?: number }
  model: string
  confidence: number
  rules: string[] | boolean | null
  agrees: boolean | null
}

export interface Permit {
  permit_id: string
  data: string[]
  cohort: string
  format: string
  purpose: string
  authorised_persons: string[]
  organisation: string
  valid_from: string
  valid_until: string
  duration_years: number
  spe_tools: string[]
  conditions_of_use: string[]
  fees: string
}

export interface Answer {
  decision: Decision
  articles: string[]
  reason: string
  answer: Numbers | null
  needs_review: boolean
  review_reasons: string[]
  trace: TraceStep[]
  signals: string[]
  plan_text: string[]
  notes: string[]
  unclaimed_words: string[]
  unclaimed_parts?: string[]
  kev: KevAnswer[]
  permit: Permit | null
  mode: string
}

export interface Request {
  id: string
  submitted: string
  applicant: Applicant
  requested_as: 'health data request' | 'health data access application'
  requested_format: string
  purpose: string
  question: string
  definitions: string[]
  why_statistics_not_enough?: string | null
}

export interface QueueItem { id: string; received: string; organisation: string; decision: Decision; needs_review: boolean; status: Status; mode: string }
export interface LogEvent { id: number; ts: string; actor: string; action: string; detail: Record<string, unknown> }

export interface RuleExplanation { what: string; checked: string; why: string; matched: string; not_matched: string }
export interface Flag { text: string; why: string; check: string }
export interface Explanations { rules: Record<string, RuleExplanation | null>; review: Flag[]; signals: Flag[]; checklist: string[] }

export interface StaffView {
  id: string
  status: Status
  staff: string | null
  received: string
  decided: string
  applicant: Applicant
  request: Request
  answer: Answer
  proposal: Answer
  log: LogEvent[]
  explanations: Explanations
}

export interface ApplicantView {
  id: string
  status: Status
  request: Request
  status_text: string
  decision: Decision
  articles: string[]
  reason: string
  steps: string[]
  plan_text: string[]
  notes: string[]
  mode: string
  ai_note: string | null
  answer: Numbers | null
  permit: Permit | null
  duties: string[]
  withheld?: string
}

export interface Precheck {
  notice: string
  likely_decision: Decision
  articles: string[]
  reason: string
  needs_review: boolean
  review_reasons: string[]
  plan_text: string[]
  notes: string[]
  definition_warnings: DefinitionWarning[]
  unclaimed_words: string[]
  unclaimed_parts?: string[]
}

export interface DefinitionWarning { severity: 'wrong' | 'check' | 'unsure'; definition: string; message: string }

export interface FormBody {
  applicant: Applicant
  requested_as: Request['requested_as']
  purpose: string
  question: string
  definitions: string[]
  why_statistics_not_enough?: string
  plan_confirmed: boolean
  warnings_confirmed: boolean
  assist_model?: string
}

export interface AssistHelp {
  model: string
  message: string | null
  suggestion: { question: string; definitions: string[] } | null
  left_out: string[]
  check: Precheck
}

export interface RStudioSession { url: string }
export interface Spe { permit: Permit; proof: { cohort_size: number; tables: Record<string, number>; opted_out_ids_inside: number } }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) { super(message); this.status = status }
}

// FastAPI sends {detail: string} or, for 422, {detail: [{msg}]}; "Value error, " is pydantic's prefix.
function message(body: unknown, status: number): string {
  const d = (body as { detail?: unknown })?.detail
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map((e) => String(e.msg).replace(/^Value error, /, '')).join(' ')
  return `The server answered ${status}.`
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(BASE + path, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } })
  } catch {
    throw new ApiError(0, `The backend at ${BASE} does not answer. Start it with "make dev".`)
  }
  const body = res.headers.get('content-type')?.includes('json') ? await res.json() : null
  if (!res.ok) throw new ApiError(res.status, message(body, res.status))
  return body as T
}

const post = <T>(path: string, body: unknown) => call<T>(path, { method: 'POST', body: JSON.stringify(body) })
const user = (u: string) => `?user=${encodeURIComponent(u)}`

export interface ApplicationItem { id: string; received: string; organisation: string; requested_as: Request['requested_as']; status: Status; decision: Decision | null }

export const api = {
  applications: () => call<ApplicationItem[]>('/applicant/requests'),
  queue: () => call<QueueItem[]>('/staff/queue'),
  staff: (id: string) => call<StaffView>(`/staff/requests/${id}`),
  confirm: (id: string, staff: string) => post<Answer>(`/staff/requests/${id}/confirm`, { staff }),
  override: (id: string, body: { staff: string; decision: Decision; reason: string; articles: string[] }) =>
    post<Answer>(`/staff/requests/${id}/override`, body),
  applicant: (id: string) => call<ApplicantView>(`/applicant/requests/${id}`),
  precheck: (form: FormBody) => post<Precheck>('/form/precheck', form),
  assist: (form: FormBody) => post<AssistHelp>('/form/assist', form),
  assistOn: () => call<{ enabled: boolean }>('/form/assist'),
  submit: (form: FormBody) => post<ApplicantView>('/form/submit', form),
  precheckJson: (request: unknown) => post<Precheck>('/precheck', request),
  submitJson: (request: unknown) => post<Answer & { id?: string }>('/requests', request),
  log: (id: string) => call<LogEvent[]>(`/register/${id}/log`),
  spe: (id: string, u: string) => call<Spe>(`/spe/${id}${user(u)}`),
  download: (id: string, u: string) => call<never>(`/spe/${id}/download${user(u)}`),
  rstudio: (id: string, u: string) => post<RStudioSession>(`/spe/${id}/rstudio${user(u)}`, {}),
}
