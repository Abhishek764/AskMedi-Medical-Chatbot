import { useState } from 'react'
import type { MedicineCard, MedicinesPayload, TriageQuestion } from '../api/types'

/** One medicine-check question. Single-choice options send on tap; multi-choice uses Continue. */
export function TriageCard(props: {
  q: TriageQuestion
  active: boolean
  onAnswer: (step: number, choices: string[], labels: string[]) => void
}) {
  const { q, active, onAnswer } = props
  const [picked, setPicked] = useState<string[]>([])
  const label = (id: string) => q.options.find((o) => o.id === id)?.label ?? id

  const toggle = (id: string) => {
    if (!q.multi) return onAnswer(q.step, [id], [label(id)])
    setPicked((p) => {
      if (id === 'none') return p.includes('none') ? [] : ['none']
      const rest = p.filter((x) => x !== 'none')
      return rest.includes(id) ? rest.filter((x) => x !== id) : [...rest, id]
    })
  }

  return (
    <section className="glass rounded-2xl rounded-tl-md px-4 py-4">
      {q.intro ? <p className="mb-3 text-sm text-muted">{q.intro}</p> : null}
      <div className="flex items-center gap-3">
        <p className="eyebrow shrink-0">
          Question {q.step} of {q.total}
        </p>
        <div aria-hidden className="h-1 flex-1 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent to-lime transition-[width] duration-500"
            style={{ width: `${(q.step / q.total) * 100}%` }}
          />
        </div>
      </div>
      <h3 className="mt-3 font-semibold text-fg">{q.question}</h3>
      {q.error ? <p className="mt-2 rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-rose-200">{q.error}</p> : null}
      <div className="mt-3 flex flex-col gap-2" role={q.multi ? 'group' : 'radiogroup'} aria-label={q.question}>
        {q.options.map((o) => {
          const on = picked.includes(o.id)
          return (
            <button
              key={o.id}
              type="button"
              disabled={!active}
              aria-pressed={q.multi ? on : undefined}
              onClick={() => toggle(o.id)}
              className={`flex min-h-11 items-center rounded-xl border px-3.5 py-2 text-left text-sm transition disabled:cursor-default disabled:opacity-50 ${
                on
                  ? 'border-accent/60 bg-accent/10 text-fg'
                  : 'border-line bg-white/[0.03] text-fg/90 hover:border-accent/40 hover:bg-white/[0.06]'
              }`}
            >
              {q.multi ? (
                <span
                  aria-hidden
                  className={`mr-2.5 grid size-4 shrink-0 place-items-center rounded border text-[10px] ${
                    on ? 'border-accent bg-accent text-accent-ink' : 'border-faint'
                  }`}
                >
                  {on ? '✓' : ''}
                </span>
              ) : null}
              {o.label}
            </button>
          )
        })}
      </div>
      {q.multi && active ? (
        <button
          type="button"
          disabled={picked.length === 0}
          onClick={() => onAnswer(q.step, picked, picked.map(label))}
          className="btn btn-primary mt-3 text-sm"
        >
          Continue
        </button>
      ) : null}
    </section>
  )
}

const FIELDS: [keyof MedicineCard, string][] = [
  ['uses', 'Uses'],
  ['do_not_use', 'Do not use'],
  ['ask_doctor', 'Ask a doctor before use'],
  ['ask_pharmacist', 'Ask a doctor or pharmacist before use'],
  ['stop_use', 'Stop use and ask a doctor'],
  ['pregnancy', 'Pregnancy or breast-feeding'],
]

function LabelText({ text }: { text: string }) {
  return <p className="whitespace-pre-line text-sm leading-relaxed text-fg/85">{text}</p>
}

/** Non-prescription options for the symptom, each copied from its FDA Drug Facts label. */
export function MedicineCards({ data }: { data: MedicinesPayload }) {
  return (
    <section className="space-y-3">
      <h3 className="font-semibold text-fg">Non-prescription options for {data.symptom}</h3>
      {data.items.map((m) => (
        <article key={m.name} className="rounded-xl border border-line bg-white/[0.03] p-4">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="font-semibold text-accent">
              {m.name}
              <a href={`#cite-${m.citation}`} className="ml-1 rounded-md bg-accent/15 px-1 align-super font-mono text-[10px] text-accent">
                [{m.citation}]
              </a>
            </h4>
            {m.active_ingredient ? <span className="font-mono text-xs text-faint">{m.active_ingredient}</span> : null}
          </header>
          {m.directions ? (
            <div className="mt-3 rounded-lg border border-accent/20 bg-accent/[0.07] p-3">
              <p className="eyebrow mb-1">Directions (from the label)</p>
              <LabelText text={m.directions} />
            </div>
          ) : null}
          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-accent">Warnings and uses</summary>
            <div className="mt-2 space-y-2">
              {FIELDS.map(([key, title]) =>
                m[key] ? (
                  <div key={key}>
                    <p className="text-xs font-semibold text-muted">{title}</p>
                    <LabelText text={String(m[key])} />
                  </div>
                ) : null,
              )}
            </div>
          </details>
        </article>
      ))}
      {data.excluded.length ? (
        <ul className="space-y-1 text-sm text-muted">
          {data.excluded.map((e) => (
            <li key={e.name}>
              <strong className="font-semibold">{e.name}</strong> is not shown because {e.reason}.
            </li>
          ))}
        </ul>
      ) : null}
      {data.check_interactions ? (
        <p className="rounded-xl border border-warn/30 bg-warn/10 px-3 py-2 text-sm text-amber-100">
          You take other regular medicines: ask a pharmacist to check for interactions before taking any of these.
        </p>
      ) : null}
      <p className="text-sm text-fg/85">
        <strong className="font-semibold">See a doctor if:</strong> {data.see_doctor_if}
      </p>
    </section>
  )
}
