import { ThumbsDown, ThumbsUp } from 'lucide-react'
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
import { Mark, Skeleton } from './Layout'
import { CrisisCard, EmergencyCard, SafetyBanner } from './SafetyCards'
import ShinyText from './reactbits/ShinyText'

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
      <div className="flex animate-rise justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 font-medium text-accent-ink shadow-[0_10px_30px_-14px_rgb(94_234_212/0.6)]">
          {turn.text}
        </p>
      </div>
    )
  }
  const refused = turn.status === 'refused' || turn.status === 'error'
  return (
    <div className="flex animate-rise gap-3">
      <span aria-hidden className="glass mt-0.5 grid size-8 shrink-0 place-items-center rounded-xl text-accent">
        <Mark className="size-4" />
      </span>
      <div className="min-w-0 max-w-[92%] flex-1 space-y-2">
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
          className={`rounded-2xl rounded-tl-md px-4 py-3.5 ${
            refused ? 'border border-dashed border-line bg-white/[0.02] text-muted' : 'glass text-fg'
          }`}
        >
          {turn.text || turn.medicines ? (
            <p className="leading-relaxed">
              <WithMarkers text={turn.text} />
            </p>
          ) : (
            <AnswerPending stage={turn.stage} />
          )}
          {turn.medicines ? (
            <div className="mt-3">
              <MedicineCards data={turn.medicines} />
            </div>
          ) : null}
          <Citations items={turn.citations} />
          {turn.disclaimer ? <p className="mt-3 text-[11px] text-faint">{turn.disclaimer}</p> : null}
        </div>
      ) : null}
      {turn.messageId && turn.status === 'complete' ? <Feedback messageId={turn.messageId} /> : null}
      </div>
    </div>
  )
}

/** Before the first sentence lands: the pipeline stage, shimmering, over skeleton lines. */
function AnswerPending({ stage }: { stage?: string }) {
  return (
    <div aria-live="polite" className="space-y-2.5 py-0.5">
      <p className="font-mono text-xs">
        <ShinyText text={`${stage ?? 'Thinking'}…`} color="#5f767c" shineColor="#5eead4" speed={1.8} />
      </p>
      <Skeleton className="h-3 w-[92%]" />
      <Skeleton className="h-3 w-[78%]" />
      <Skeleton className="h-3 w-[55%]" />
    </div>
  )
}

/** Placeholder conversation while a saved chat loads. */
export function TurnSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading conversation" className="space-y-6">
      {[0, 1].map((i) => (
        <div key={i} className="space-y-5">
          <div className="flex justify-end">
            <Skeleton className="h-10 w-2/5 rounded-2xl" />
          </div>
          <div className="flex gap-3">
            <Skeleton className="size-8 shrink-0 rounded-xl" />
            <div className="glass flex-1 space-y-2.5 rounded-2xl p-4">
              <Skeleton className="h-3 w-11/12" />
              <Skeleton className="h-3 w-4/5" />
              <Skeleton className="h-3 w-3/5" />
              <Skeleton className="mt-4 h-2.5 w-1/3" />
            </div>
          </div>
        </div>
      ))}
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
    <div className="flex items-center gap-1 pl-1 text-xs text-faint">
      <span className="mr-1">{sent ? 'Thanks for the feedback' : 'Was this helpful?'}</span>
      <button
        type="button"
        aria-label="Helpful"
        onClick={() => send(1)}
        className={`grid size-8 place-items-center rounded-lg transition hover:bg-white/5 hover:text-fg ${sent === 1 ? 'bg-accent/15 text-accent' : ''}`}
      >
        <ThumbsUp className="size-3.5" />
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        onClick={() => send(-1)}
        className={`grid size-8 place-items-center rounded-lg transition hover:bg-white/5 hover:text-fg ${sent === -1 ? 'bg-danger/15 text-danger' : ''}`}
      >
        <ThumbsDown className="size-3.5" />
      </button>
    </div>
  )
}
