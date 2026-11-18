// Shapes returned by the AskMedi /v1 API (backend/app/api/v1/schemas.py).

export interface User {
  id: string
  email: string
  role: 'public' | 'provider' | 'reviewer' | 'admin'
  email_verified: boolean
  consent_required: boolean
  created_at: string
}

export interface Tokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface AuthResponse {
  user: User
  tokens: Tokens
}

export interface Conversation {
  id: string
  title: string
  risk_level: 'normal' | 'elevated'
  created_at: string
  updated_at: string
}

export interface Citation {
  position: number
  chunk_id: string
  doc_id: string
  title: string
  section: string | null
  source: string
  url: string | null
  score: number
}

export type MessageStatus = 'complete' | 'refused' | 'crisis' | 'emergency' | 'aborted' | 'error' | 'triage'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  status: MessageStatus
  refusal_reason: string | null
  created_at: string
  citations: Citation[]
}

export interface ConversationDetail extends Conversation {
  messages: Message[]
}

export interface Helpline {
  name: string
  phone: string
  note: string
}

export interface CrisisPayload {
  message: string
  helplines: Helpline[]
  directory: string
}

export interface EmergencyPayload {
  message: string
  number: string
}

/** One question of the 3-step medicine check. */
export interface TriageQuestion {
  step: number
  total: number
  question: string
  options: { id: string; label: string }[]
  multi: boolean
  intro?: string
  error?: string
}

/** A non-prescription medicine, copied from its FDA Drug Facts label. */
export interface MedicineCard {
  name: string
  citation: number
  active_ingredient?: string
  uses?: string
  directions?: string
  do_not_use?: string
  ask_doctor?: string
  ask_pharmacist?: string
  stop_use?: string
  pregnancy?: string
}

export interface MedicinesPayload {
  symptom: string
  items: MedicineCard[]
  excluded: { name: string; reason: string }[]
  check_interactions: boolean
  see_doctor_if: string
  disclaimer: string
}

/** Server-sent events emitted by POST /v1/conversations/{id}/messages. */
export type ChatEvent =
  | { type: 'status'; data: { stage: string } }
  | { type: 'sentence'; data: { text: string; citations: number[] } }
  | { type: 'citations'; data: { items: Citation[]; disclaimer: string } }
  | { type: 'refusal'; data: { reason: string; message: string } }
  | { type: 'crisis'; data: CrisisPayload }
  | { type: 'emergency'; data: EmergencyPayload }
  | { type: 'banner'; data: { kind: 'crisis' | 'emergency' } & Partial<CrisisPayload & EmergencyPayload> }
  | { type: 'triage'; data: TriageQuestion }
  | { type: 'medicines'; data: MedicinesPayload }
  | { type: 'done'; data: { message_id: string; status: MessageStatus } }
  | { type: 'error'; data: { message: string } }

// -- Insurance policy demo ---------------------------------------------------------
export interface PolicySummary {
  id: string
  title: string
  form: string
  edition: string
  source_url: string
  sections: { number: string; title: string; page: number }[]
}

export type ExclusionCell =
  | { status: 'excluded'; clause: string; page: number; page_label: string; quote: string }
  | { status: 'not_found' }

export interface Comparison {
  policies: { id: string; title: string; form: string; edition: string }[]
  rows: { key: string; label: string; differs: boolean; cells: Record<string, ExclusionCell> }[]
  differences: string[]
  note: string
}

export interface SectionDiff {
  section: string
  rows: {
    summary: string
    in_all: boolean
    cells: Record<string, { clause: string; page: number; page_label: string; text: string }>
  }[]
}

export interface PolicyAnswer {
  answer: { text: string; citations: number[] }[]
  citations: { position: number; policy: string; clause: string; url: string | null }[]
  refused: boolean
  message: string | null
}

export interface DailyMetrics {
  date: string
  answers: number
  by_status: Record<string, number>
  avg_latency_ms: number | null
  safety_events: number
}

/** GET /v1/admin/metrics (admin only). */
export interface AdminMetrics {
  window_days: number
  usage: { answers: number; active_conversations: number; users_total: number; new_users: number }
  answers_by_status: Record<string, number>
  answer_rate: number | null
  refusals_by_reason: Record<string, number>
  safety_events: Record<string, number>
  latency_ms: { p50: number | null; p95: number | null; max: number | null }
  tokens: { in: number; out: number }
  feedback: { up: number; down: number; helpful_rate: number | null; coverage: number | null }
  corpus: { documents_by_source: Record<string, number>; documents: number }
  daily: DailyMetrics[]
  llm: { models: string[]; fallback: string }
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}
