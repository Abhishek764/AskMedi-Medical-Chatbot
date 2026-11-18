import { useState } from 'react'
import { api } from '../api/client'
import type {
  Citation,
  CrisisPayload,
  EmergencyPayload,
  MedicinesPayload,
  MessageStatus,
  TriageQuestion,
} from '../api/types'
import { Citations, WithMarkers } from './Citations'
import { MedicineCards, TriageCard } from './MedicineCheck'
import { CrisisCard, EmergencyCard, SafetyBanner } from './SafetyCards'

/** One chat turn as the UI shows it, built from saved messages or live stream events. */
export interface TurnModel {
  key: string
  role: 'user' | 'assistant'
  text: string
  status?: MessageStatus | 'streaming'
  stage?: string
  messageId?: string
  citations: Citation[]
  disclaimer?: string
  crisis?: CrisisPayload
  emergency?: EmergencyPayload
  banners: { kind: 'crisis' | 'emergency'; phone?: string }[]
  refusalReason?: string
  triage?: TriageQuestion
  medicines?: MedicinesPayload
}

export type AnswerHandler = (step: number, choices: string[], labels: string[]) => void

export function Turn({
  turn,
  active = false,
  onAnswer,
}: {
  turn: TurnModel
  active?: boolean
  onAnswer?: AnswerHandler
}) {
  if (turn.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-teal-700 px-4 py-2 text-white">
          {turn.text}
        </p>
      </div>
    )
  }
  const refused = turn.status === 'refused' || turn.status === 'error'
  return (
    <div className="max-w-[92%] space-y-2">
      {turn.banners.map((b) => (
        <SafetyBanner key={b.kind} kind={b.kind} phone={b.phone} />
      ))}
      {turn.triage ? (
        <TriageCard q={turn.triage} active={active && !!onAnswer} onAnswer={onAnswer ?? (() => {})} />
      ) : null}
      {turn.crisis ? <CrisisCard data={turn.crisis} /> : null}
      {turn.emergency ? <EmergencyCard data={turn.emergency} /> : null}
      {!turn.crisis && !turn.emergency && !turn.triage && (turn.text || turn.medicines || turn.status === 'streaming') ? (
        <div
          className={`rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm ${
            refused ? 'border border-slate-300 bg-slate-50 text-slate-700' : 'bg-white text-slate-900'
          }`}
        >
          {turn.text || turn.medicines ? (
            <p className="leading-relaxed">
              <WithMarkers text={turn.text} />
            </p>
          ) : (
            <p className="animate-pulse text-sm text-slate-500">{turn.stage ?? 'Thinking'}…</p>
          )}
          {turn.medicines ? (
            <div className="mt-3">
              <MedicineCards data={turn.medicines} />
            </div>
          ) : null}
          <Citations items={turn.citations} />
          {turn.disclaimer ? <p className="mt-2 text-[11px] text-slate-500">{turn.disclaimer}</p> : null}
        </div>
      ) : null}
      {turn.messageId && turn.status === 'complete' ? <Feedback messageId={turn.messageId} /> : null}
    </div>
  )
}

function Feedback({ messageId }: { messageId: string }) {
  const [sent, setSent] = useState<1 | -1 | null>(null)
  const send = async (rating: 1 | -1) => {
    setSent(rating)
    try {
      await api.sendFeedback(messageId, rating)
    } catch {
      setSent(null)
    }
  }
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span>{sent ? 'Thanks for the feedback' : 'Was this helpful?'}</span>
      <button
        type="button"
        aria-label="Helpful"
        onClick={() => send(1)}
        className={`rounded px-1.5 py-0.5 hover:bg-slate-200 ${sent === 1 ? 'bg-teal-100 text-teal-800' : ''}`}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        onClick={() => send(-1)}
        className={`rounded px-1.5 py-0.5 hover:bg-slate-200 ${sent === -1 ? 'bg-rose-100 text-rose-800' : ''}`}
      >
        👎
      </button>
    </div>
  )
}
