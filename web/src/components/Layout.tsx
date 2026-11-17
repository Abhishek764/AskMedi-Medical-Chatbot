import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

export const DISCLAIMER =
  'AskMedi gives general health information from cited sources. It is not medical advice, a diagnosis or a prescription. In an emergency, call your local emergency number.'

export function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2 font-semibold text-teal-800">
      <span aria-hidden className="grid size-7 place-items-center rounded-lg bg-teal-700 text-white">
        +
      </span>
      AskMedi
    </Link>
  )
}

/** Centered card page used by sign-in, sign-up and consent screens. */
export function CardPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="grid min-h-dvh place-items-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
          <div className="mt-4">{children}</div>
        </section>
        <p className="mt-6 text-center text-xs text-slate-500">{DISCLAIMER}</p>
      </div>
    </main>
  )
}

export function Field(props: {
  label: string
  type?: string
  value: string
  onChange: (v: string) => void
  autoComplete?: string
  minLength?: number
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-slate-700">{props.label}</span>
      <input
        required
        type={props.type ?? 'text'}
        value={props.value}
        autoComplete={props.autoComplete}
        minLength={props.minLength}
        onChange={(e) => props.onChange(e.target.value)}
        className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
      />
    </label>
  )
}

export function ErrorText({ error }: { error: string | null }) {
  return error ? (
    <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
      {error}
    </p>
  ) : null
}

export const primaryButton =
  'w-full rounded-lg bg-teal-700 px-4 py-2.5 font-semibold text-white hover:bg-teal-800 disabled:opacity-60'
