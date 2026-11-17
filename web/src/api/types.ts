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

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}
