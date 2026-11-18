import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError, type Comparison, type PolicyAnswer, type PolicySummary, type SectionDiff } from '../api/types'
import { Logo } from '../components/Layout'

const SECTIONS = ['Property not insured', 'Deductibles', 'Coinsurance', 'General conditions']

/** Insurance policy demo: compare exclusions across policies and ask questions with page citations. */
export default function Policies() {
  const [policies, setPolicies] = useState<PolicySummary[]>([])
  const [picked, setPicked] = useState<string[]>([])
  const [table, setTable] = useState<Comparison | null>(null)
  const [section, setSection] = useState(SECTIONS[0])
  const [diff, setDiff] = useState<SectionDiff | null>(null)
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState<PolicyAnswer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api
      .listPolicies()
      .then((p) => {
        setPolicies(p)
        setPicked(p.map((x) => x.id))
      })
      .catch(() => setError('Could not load policies. Run "python -m app.policies build" on the server.'))
  }, [])

  const run = async <T,>(fn: () => Promise<T>, set: (v: T) => void) => {
    setBusy(true)
    setError(null)
    try {
      set(await fn())
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  const toggle = (id: string) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))
  const ask = (e: FormEvent) => {
    e.preventDefault()
    if (question.trim().length >= 3) void run(() => api.askPolicies(question.trim(), picked), setAnswer)
  }
  const name = (id: string) => policies.find((p) => p.id === id)?.form ?? id

  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <Logo />
        <Link to="/chat" className="text-sm text-teal-700 hover:underline">
          Back to chat
        </Link>
      </header>
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6">
        <section>
          <h1 className="text-2xl font-semibold">Policy comparison</h1>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            Compare what insurance policies exclude, clause by clause, with the page for every finding. Demo
            documents: the three FEMA Standard Flood Insurance Policy forms from the Code of Federal Regulations.
          </p>
        </section>

        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="font-semibold">Policies</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {policies.map((p) => (
              <label
                key={p.id}
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                  picked.includes(p.id) ? 'border-teal-700 bg-teal-50' : 'border-slate-300'
                }`}
              >
                <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} />
                <span>
                  <strong className="font-semibold">{p.form}</strong>
                  <span className="block text-xs text-slate-500">{p.edition}</span>
                </span>
              </label>
            ))}
          </div>
          <button
            onClick={() => run(() => api.comparePolicies(picked), setTable)}
            disabled={busy || picked.length < 1}
            className="mt-3 rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
          >
            Compare exclusions
          </button>
          {error ? <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p> : null}
        </section>

        {table ? (
          <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
            <h2 className="font-semibold">Exclusions</h2>
            <p className="mt-1 text-sm text-slate-600">
              {table.differences.length
                ? `Differences: ${table.differences.join('; ')}.`
                : 'No differences in these exclusion categories.'}
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="border-b border-slate-200 py-2 pr-3 font-semibold">Exclusion</th>
                    {table.policies.map((p) => (
                      <th key={p.id} className="border-b border-slate-200 px-3 py-2 font-semibold">
                        {p.form}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((r) => (
                    <tr key={r.key} className={r.differs ? 'bg-amber-50' : ''}>
                      <td className="border-b border-slate-100 py-2 pr-3 align-top">
                        {r.label}
                        {r.differs ? (
                          <span className="ml-2 rounded bg-amber-200 px-1.5 text-xs font-semibold text-amber-950">differs</span>
                        ) : null}
                      </td>
                      {table.policies.map((p) => {
                        const c = r.cells[p.id]
                        return (
                          <td key={p.id} className="border-b border-slate-100 px-3 py-2 align-top">
                            {c.status === 'excluded' ? (
                              <details>
                                <summary className="cursor-pointer">
                                  <span className="font-semibold text-rose-800">Excluded</span>{' '}
                                  <span className="text-xs text-slate-500">
                                    {c.clause} · {c.page_label} {c.page}
                                  </span>
                                </summary>
                                <p className="mt-1 text-xs leading-relaxed text-slate-700">{c.quote}</p>
                              </details>
                            ) : (
                              <span className="text-slate-500">Not found in exclusions</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">{table.note}</p>
          </section>
        ) : null}

        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="font-semibold">Clauses only some policies have</h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              aria-label="Section"
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
            >
              {SECTIONS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              onClick={() => run(() => api.diffPolicies(picked, section), setDiff)}
              disabled={busy || picked.length < 2}
              className="rounded-xl border border-teal-700 px-3 py-2 text-sm font-semibold text-teal-800 hover:bg-teal-50 disabled:opacity-50"
            >
              Find differences
            </button>
          </div>
          {diff ? (
            <ul className="mt-3 space-y-2 text-sm">
              {diff.rows.filter((r) => !r.in_all).length === 0 ? (
                <li className="text-slate-600">Every clause in this section appears in all selected policies.</li>
              ) : null}
              {diff.rows
                .filter((r) => !r.in_all)
                .map((r, i) => (
                  <li key={i} className="rounded-lg bg-slate-50 p-3">
                    <p className="text-xs font-semibold text-teal-800">
                      Only in: {Object.keys(r.cells).map(name).join(', ')}
                    </p>
                    {Object.entries(r.cells).map(([id, c]) => (
                      <p key={id} className="mt-1 text-slate-700">
                        <span className="text-xs text-slate-500">
                          {c.clause} · {c.page_label} {c.page}:{' '}
                        </span>
                        {c.text}
                      </p>
                    ))}
                  </li>
                ))}
            </ul>
          ) : null}
        </section>

        <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
          <h2 className="font-semibold">Ask the policies</h2>
          <form onSubmit={ask} className="mt-3 flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Does the policy cover damage from a landslide?"
              aria-label="Question about the policies"
              maxLength={1000}
              className="flex-1 rounded-xl border border-slate-300 px-3 py-2 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            />
            <button
              disabled={busy}
              className="rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
            >
              Ask
            </button>
          </form>
          {answer ? (
            answer.refused ? (
              <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">{answer.message}</p>
            ) : (
              <div className="mt-3 space-y-2 text-sm">
                <p className="leading-relaxed">
                  {answer.answer.map((s, i) => (
                    <span key={i}>
                      {s.text}{' '}
                      {s.citations.map((n) => (
                        <sup key={n} className="font-semibold text-teal-700">
                          [{n}]
                        </sup>
                      ))}{' '}
                    </span>
                  ))}
                </p>
                <ol className="space-y-1 border-t border-slate-200 pt-2 text-xs text-slate-600">
                  {answer.citations.map((c) => (
                    <li key={c.position}>
                      <span className="font-semibold text-teal-700">[{c.position}]</span> {c.policy} › {c.clause}
                    </li>
                  ))}
                </ol>
              </div>
            )
          ) : null}
        </section>
      </main>
    </div>
  )
}
