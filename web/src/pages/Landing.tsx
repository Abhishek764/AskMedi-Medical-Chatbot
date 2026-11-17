import { Link } from 'react-router-dom'
import { DISCLAIMER, Logo } from '../components/Layout'

const POINTS = [
  ['Answers from trusted sources', 'MedlinePlus, FDA drug labels and peer-reviewed research reviews.'],
  ['Every sentence is cited', 'Tap a number to see exactly where the information came from.'],
  ['Says "I don\'t know"', 'If the sources don\'t cover your question, AskMedi refuses instead of guessing.'],
  ['Safety first', 'Emergencies and crisis messages get helpline numbers, not chat.'],
]

export default function Landing() {
  return (
    <div className="min-h-dvh bg-gradient-to-b from-teal-50 to-white">
      <header className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
        <Logo />
        <nav className="flex gap-2 text-sm">
          <Link to="/login" className="rounded-lg px-3 py-2 font-medium text-slate-700 hover:bg-white">
            Sign in
          </Link>
          <Link to="/register" className="rounded-lg bg-teal-700 px-3 py-2 font-semibold text-white hover:bg-teal-800">
            Get started
          </Link>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 pb-16 pt-10">
        <h1 className="max-w-2xl text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
          Health and medicine questions, answered with sources.
        </h1>
        <p className="mt-4 max-w-xl text-lg text-slate-600">
          AskMedi explains conditions, symptoms and medicines in plain language, using only trusted medical
          sources, and shows you where every answer comes from.
        </p>
        <Link
          to="/register"
          className="mt-8 inline-block rounded-xl bg-teal-700 px-6 py-3 font-semibold text-white hover:bg-teal-800"
        >
          Ask your first question
        </Link>
        <ul className="mt-14 grid gap-4 sm:grid-cols-2">
          {POINTS.map(([title, body]) => (
            <li key={title} className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
              <h2 className="font-semibold text-slate-900">{title}</h2>
              <p className="mt-1 text-sm text-slate-600">{body}</p>
            </li>
          ))}
        </ul>
        <section className="mt-10 rounded-2xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-950">
          <h2 className="font-semibold">What AskMedi is not</h2>
          <p className="mt-1">
            It does not diagnose you, prescribe medicine or recommend a dose for you. It is not a therapist or a
            replacement for your doctor or pharmacist. {DISCLAIMER}
          </p>
        </section>
      </main>
    </div>
  )
}
