import type { CrisisPayload, EmergencyPayload } from '../api/types'

const tel = (phone: string) => `tel:${phone.replace(/[^\d+]/g, '')}`

/** Shown instead of an answer when someone may be at risk. Copy is fixed server-side. */
export function CrisisCard({ data }: { data: CrisisPayload }) {
  return (
    <section role="alert" className="rounded-xl border-2 border-rose-300 bg-rose-50 p-4 text-rose-950">
      <h3 className="font-semibold">You don't have to go through this alone</h3>
      <p className="mt-1 text-sm leading-relaxed">{data.message}</p>
      <ul className="mt-3 space-y-2">
        {data.helplines.map((h) => (
          <li key={h.phone} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <a
              href={tel(h.phone)}
              className="rounded-lg bg-rose-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-rose-700"
            >
              Call {h.phone}
            </a>
            <span className="text-sm">
              {h.name}
              {h.note ? <span className="text-rose-800"> · {h.note}</span> : null}
            </span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs">
        Other countries:{' '}
        <a className="underline" href={data.directory} target="_blank" rel="noreferrer">
          find a helpline
        </a>
      </p>
    </section>
  )
}

export function EmergencyCard({ data }: { data: EmergencyPayload }) {
  return (
    <section role="alert" className="rounded-xl border-2 border-amber-400 bg-amber-50 p-4 text-amber-950">
      <h3 className="font-semibold">This may be a medical emergency</h3>
      <p className="mt-1 text-sm leading-relaxed">{data.message}</p>
      <a
        href={tel(data.number)}
        className="mt-3 inline-block rounded-lg bg-amber-600 px-4 py-2 font-semibold text-white hover:bg-amber-700"
      >
        Call {data.number}
      </a>
    </section>
  )
}

/** Small reminder attached to an ordinary answer on a sensitive topic. */
export function SafetyBanner({ kind, phone }: { kind: 'crisis' | 'emergency'; phone?: string }) {
  const text =
    kind === 'crisis'
      ? 'If you are struggling, free, confidential help is available'
      : 'If symptoms are sudden or severe, call emergency services'
  return (
    <p className="rounded-lg bg-slate-100 px-3 py-2 text-xs text-slate-700">
      {text}
      {phone ? (
        <>
          {' — '}
          <a className="font-semibold underline" href={tel(phone)}>
            {phone}
          </a>
        </>
      ) : null}
      .
    </p>
  )
}
