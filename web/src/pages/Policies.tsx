import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { ApiError, type Comparison, type PolicyAnswer, type PolicySummary, type SectionDiff } from '../api/types'
import { PageHeader, Skeleton, TopProgress } from '../components/Layout'

const SECTIONS = ['Property not insured', 'Deductibles', 'Coinsurance', 'General conditions']

/** Insurance policy demo: compare exclusions across policies and ask questions with page citations. */
export default function Policies() {
  const [policies, setPolicies] = useState<PolicySummary[] | null>(null)
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
      .catch(() => {
        setPolicies([])
        setError('Could not load policies. Run "python -m app.policies build" on the server.')
      })
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
  const name = (id: string) => policies?.find((p) => p.id === id)?.form ?? id

  return (
    <div className="min-h-dvh text-fg">
      <PageHeader />
      <TopProgress active={busy || policies === null} />
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6">
        <section>
          <h1 className="font-display text-2xl font-semibold tracking-tight">Policy comparison</h1>
          <p className="mt-1 max-w-3xl text-sm text-muted">
            Compare what insurance policies exclude, clause by clause, with the page for every finding. Demo
            documents: the three FEMA Standard Flood Insurance Policy forms from the Code of Federal Regulations.
          </p>
        </section>

        <section className="glass rounded-2xl p-5">
          <h2 className="font-semibold">Policies</h2>
          <div className="mt-3 flex flex-wrap gap-2">
            {policies === null
              ? [0, 1, 2].map((i) => <Skeleton key={i} className="h-14 w-44 rounded-xl" />)
              : null}
            {(policies ?? []).map((p) => (
              <label
                key={p.id}
                className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                  picked.includes(p.id) ? 'border-accent/60 bg-accent/10' : 'border-line bg-white/[0.03] hover:border-accent/30'
                }`}
              >
                <input type="checkbox" checked={picked.includes(p.id)} onChange={() => toggle(p.id)} />
                <span>
                  <strong className="font-semibold">{p.form}</strong>
                  <span className="block text-xs text-muted">{p.edition}</span>
                </span>
              </label>
            ))}
          </div>
          <button
            onClick={() => run(() => api.comparePolicies(picked), setTable)}
            disabled={busy || picked.length < 1}
            className="btn btn-primary mt-4 text-sm"
          >
            Compare exclusions
          </button>
          {error ? <p className="mt-3 rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-rose-200">{error}</p> : null}
        </section>

        {table ? (
          <section className="glass rounded-2xl p-5">
            <h2 className="font-semibold">Exclusions</h2>
            <p className="mt-1 text-sm text-muted">
              {table.differences.length
                ? `Differences: ${table.differences.join('; ')}.`
                : 'No differences in these exclusion categories.'}
            </p>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="text-left">
                    <th className="border-b border-line py-2 pr-3 font-semibold">Exclusion</th>
                    {table.policies.map((p) => (
                      <th key={p.id} className="border-b border-line px-3 py-2 font-semibold">
                        {p.form}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((r) => (
                    <tr key={r.key} className={r.differs ? 'bg-warn/[0.06]' : ''}>
                      <td className="border-b border-line py-2 pr-3 align-top">
                        {r.label}
                        {r.differs ? (
                          <span className="ml-2 rounded-md bg-warn/20 px-1.5 font-mono text-[10px] uppercase text-amber-200">differs</span>
                        ) : null}
                      </td>
                      {table.policies.map((p) => {
                        const c = r.cells[p.id]
                        return (
                          <td key={p.id} className="border-b border-line px-3 py-2 align-top">
                            {c.status === 'excluded' ? (
                              <details>
                                <summary className="cursor-pointer">
                                  <span className="font-semibold text-rose-300">Excluded</span>{' '}
                                  <span className="text-xs text-muted">
                                    {c.clause} · {c.page_label} {c.page}
                                  </span>
                                </summary>
                                <p className="mt-1 text-xs leading-relaxed text-fg/85">{c.quote}</p>
                              </details>
                            ) : (
                              <span className="text-muted">Not found in exclusions</span>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-muted">{table.note}</p>
          </section>
        ) : null}

        <section className="glass rounded-2xl p-5">
          <h2 className="font-semibold">Clauses only some policies have</h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <select
              value={section}
              onChange={(e) => setSection(e.target.value)}
              aria-label="Section"
              className="input w-auto text-sm"
            >
              {SECTIONS.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
            <button
              onClick={() => run(() => api.diffPolicies(picked, section), setDiff)}
              disabled={busy || picked.length < 2}
              className="btn btn-ghost text-sm"
            >
              Find differences
            </button>
          </div>
          {diff ? (
            <ul className="mt-3 space-y-2 text-sm">
              {diff.rows.filter((r) => !r.in_all).length === 0 ? (
                <li className="text-muted">Every clause in this section appears in all selected policies.</li>
              ) : null}
              {diff.rows
                .filter((r) => !r.in_all)
                .map((r, i) => (
                  <li key={i} className="rounded-xl border border-line bg-white/[0.03] p-3">
                    <p className="text-xs font-semibold text-accent">
                      Only in: {Object.keys(r.cells).map(name).join(', ')}
                    </p>
                    {Object.entries(r.cells).map(([id, c]) => (
                      <p key={id} className="mt-1 text-fg/85">
                        <span className="text-xs text-muted">
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

        <section className="glass rounded-2xl p-5">
          <h2 className="font-semibold">Ask the policies</h2>
          <form onSubmit={ask} className="mt-3 flex gap-2">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Does the policy cover damage from a landslide?"
              aria-label="Question about the policies"
              maxLength={1000}
              className="input flex-1 text-sm"
            />
            <button
              disabled={busy}
              className="btn btn-primary text-sm"
            >
              Ask
            </button>
          </form>
          {answer ? (
            answer.refused ? (
              <p className="mt-3 rounded-xl border border-line bg-white/[0.03] px-3 py-2 text-sm text-muted">{answer.message}</p>
            ) : (
              <div className="mt-3 space-y-2 text-sm">
                <p className="leading-relaxed">
                  {answer.answer.map((s, i) => (
                    <span key={i}>
                      {s.text}{' '}
                      {s.citations.map((n) => (
                        <sup key={n} className="font-semibold text-accent">
                          [{n}]
                        </sup>
                      ))}{' '}
                    </span>
                  ))}
                </p>
                <ol className="space-y-1 border-t border-line pt-2 text-xs text-muted">
                  {answer.citations.map((c) => (
                    <li key={c.position}>
                      <span className="font-semibold text-accent">[{c.position}]</span> {c.policy} › {c.clause}
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
