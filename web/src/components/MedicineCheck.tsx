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
    <section className="rounded-2xl rounded-bl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-teal-100">
      {q.intro ? <p className="mb-2 text-sm text-slate-600">{q.intro}</p> : null}
      <p className="text-xs font-semibold uppercase tracking-wide text-teal-700">
        Question {q.step} of {q.total}
      </p>
      <h3 className="mt-1 font-semibold text-slate-900">{q.question}</h3>
      {q.error ? <p className="mt-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">{q.error}</p> : null}
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
              className={`rounded-xl border px-3 py-2 text-left text-sm transition-colors disabled:cursor-default disabled:opacity-60 ${
                on ? 'border-teal-700 bg-teal-50 text-teal-900' : 'border-slate-300 bg-white text-slate-800 hover:border-teal-600'
              }`}
            >
              {q.multi ? <span aria-hidden className="mr-2">{on ? '☑' : '☐'}</span> : null}
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
          className="mt-3 rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
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
  return <p className="whitespace-pre-line text-sm leading-relaxed text-slate-700">{text}</p>
}

/** Non-prescription options for the symptom, each copied from its FDA Drug Facts label. */
export function MedicineCards({ data }: { data: MedicinesPayload }) {
  return (
    <section className="space-y-3">
      <h3 className="font-semibold text-slate-900">Non-prescription options for {data.symptom}</h3>
      {data.items.map((m) => (
        <article key={m.name} className="rounded-xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <header className="flex flex-wrap items-baseline justify-between gap-2">
            <h4 className="font-semibold text-teal-800">
              {m.name}
              <a href={`#cite-${m.citation}`} className="ml-1 align-super text-[10px] text-teal-700">
                [{m.citation}]
              </a>
            </h4>
            {m.active_ingredient ? <span className="text-xs text-slate-500">{m.active_ingredient}</span> : null}
          </header>
          {m.directions ? (
            <div className="mt-3 rounded-lg bg-teal-50 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-teal-800">Directions (from the label)</p>
              <LabelText text={m.directions} />
            </div>
          ) : null}
          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium text-teal-700">Warnings and uses</summary>
            <div className="mt-2 space-y-2">
              {FIELDS.map(([key, title]) =>
                m[key] ? (
                  <div key={key}>
                    <p className="text-xs font-semibold text-slate-600">{title}</p>
                    <LabelText text={String(m[key])} />
                  </div>
                ) : null,
              )}
            </div>
          </details>
        </article>
      ))}
      {data.excluded.length ? (
        <ul className="space-y-1 text-sm text-slate-600">
          {data.excluded.map((e) => (
            <li key={e.name}>
              <strong className="font-semibold">{e.name}</strong> is not shown because {e.reason}.
            </li>
          ))}
        </ul>
      ) : null}
      {data.check_interactions ? (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-950">
          You take other regular medicines: ask a pharmacist to check for interactions before taking any of these.
        </p>
      ) : null}
      <p className="text-sm text-slate-700">
        <strong className="font-semibold">See a doctor if:</strong> {data.see_doctor_if}
      </p>
    </section>
  )
}
