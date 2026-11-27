import type { CrisisPayload, EmergencyPayload } from '../api/types'

const tel = (phone: string) => `tel:${phone.replace(/[^\d+]/g, '')}`

/** Shown instead of an answer when someone may be at risk. Copy is fixed server-side. */
export function CrisisCard({ data }: { data: CrisisPayload }) {
  return (
    <section role="alert" className="rounded-2xl border border-danger/50 bg-[#2a0d16]/90 p-5 text-rose-50 shadow-[0_0_40px_-12px_rgb(251_113_133/0.5)]">
      <h3 className="font-semibold">You don't have to go through this alone</h3>
      <p className="mt-1 text-sm leading-relaxed">{data.message}</p>
      <ul className="mt-3 space-y-2">
        {data.helplines.map((h) => (
          <li key={h.phone} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <a
              href={tel(h.phone)}
              className="btn btn-danger min-h-10 text-sm"
            >
              Call {h.phone}
            </a>
            <span className="text-sm">
              {h.name}
              {h.note ? <span className="text-rose-200/70"> · {h.note}</span> : null}
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
    <section role="alert" className="rounded-2xl border border-warn/60 bg-[#2a1f05]/90 p-5 text-amber-50 shadow-[0_0_40px_-12px_rgb(251_191_36/0.5)]">
      <h3 className="font-semibold">This may be a medical emergency</h3>
      <p className="mt-1 text-sm leading-relaxed">{data.message}</p>
      <a
        href={tel(data.number)}
        className="btn mt-4 bg-warn text-[#2a1f05] hover:bg-amber-300"
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
    <p className="rounded-xl border border-line bg-white/[0.04] px-3 py-2 text-xs text-muted">
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
