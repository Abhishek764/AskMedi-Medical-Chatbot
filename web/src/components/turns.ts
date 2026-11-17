import type { ChatEvent, Message } from '../api/types'
import type { TurnModel } from './Turn'

const empty = (key: string, role: TurnModel['role'], text = ''): TurnModel => ({
  key,
  role,
  text,
  citations: [],
  banners: [],
})

/** Saved messages -> turns (helpline cards aren't stored, so crisis turns show their saved text). */
export function turnsFromMessages(messages: Message[]): TurnModel[] {
  return messages.map((m) => ({
    ...empty(m.id, m.role, m.content),
    status: m.status,
    messageId: m.id,
    citations: m.citations,
    refusalReason: m.refusal_reason ?? undefined,
  }))
}

export function userTurn(key: string, text: string): TurnModel {
  return { ...empty(key, 'user', text), status: 'complete' }
}

export function pendingAssistant(key: string): TurnModel {
  return { ...empty(key, 'assistant'), status: 'streaming', stage: 'Thinking' }
}

/** Fold one streamed event into the assistant turn being built. Pure, so it is unit-tested. */
export function applyEvent(turn: TurnModel, ev: ChatEvent): TurnModel {
  switch (ev.type) {
    case 'status':
      return { ...turn, stage: ev.data.stage.charAt(0).toUpperCase() + ev.data.stage.slice(1) }
    case 'sentence': {
      const marks = ev.data.citations.map((n) => `[${n}]`).join('')
      const piece = `${ev.data.text}${marks ? ` ${marks}` : ''}`
      return { ...turn, text: turn.text ? `${turn.text} ${piece}` : piece }
    }
    case 'citations':
      return { ...turn, citations: ev.data.items, disclaimer: ev.data.disclaimer }
    case 'refusal':
      return { ...turn, text: ev.data.message, status: 'refused', refusalReason: ev.data.reason }
    case 'crisis':
      return { ...turn, crisis: ev.data, status: 'crisis' }
    case 'emergency':
      return { ...turn, emergency: ev.data, status: 'emergency' }
    case 'banner': {
      const phone = ev.data.kind === 'crisis' ? ev.data.helplines?.[0]?.phone : ev.data.number
      if (turn.banners.some((b) => b.kind === ev.data.kind)) return turn
      return { ...turn, banners: [...turn.banners, { kind: ev.data.kind, phone }] }
    }
    case 'done':
      return { ...turn, status: ev.data.status, messageId: ev.data.message_id, stage: undefined }
    case 'error':
      return { ...turn, text: ev.data.message, status: 'error' }
    default:
      return turn
  }
}
