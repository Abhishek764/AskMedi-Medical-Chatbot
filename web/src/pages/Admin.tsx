import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError, type AdminMetrics, type DailyMetrics } from '../api/types'
import { Logo } from '../components/Layout'
import { fillDays } from './adminData'

const WINDOWS = [7, 30, 90] as const
const REFRESH_MS = 30_000

const LABELS: Record<string, string> = {
  complete: 'Answered',
  refused: 'Refused',
  crisis: 'Crisis',
  emergency: 'Emergency',
  triage: 'Medicine check',
  error: 'Error',
  aborted: 'Stopped',
}
const label = (key: string) => LABELS[key] ?? key.replaceAll('_', ' ')
const pct = (v: number | null) => (v == null ? '—' : `${Math.round(v * 100)}%`)
const ms = (v: number | null) => (v == null ? '—' : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${v} ms`)
const num = (v: number) => v.toLocaleString()

/** Admin observability dashboard: product health from GET /v1/admin/metrics. */
export default function Admin() {
  const [days, setDays] = useState<number>(7)
  const [data, setData] = useState<AdminMetrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [auto, setAuto] = useState(true)
  const [updated, setUpdated] = useState<Date | null>(null)

  const load = useCallback(async () => {
    try {
      setData(await api.adminMetrics(days))
      setUpdated(new Date())
      setError(null)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not load metrics.')
    }
  }, [days])

  useEffect(() => {
    void load()
    if (!auto) return
    const t = setInterval(() => void load(), REFRESH_MS)
    return () => clearInterval(t)
  }, [load, auto])

  const daily = data ? fillDays(data.daily, days) : []
  const safetyTotal = data ? Object.values(data.safety_events).reduce((a, b) => a + b, 0) : 0

  return (
    <div className="min-h-dvh bg-slate-50 text-slate-900">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <Logo />
        <Link to="/chat" className="text-sm text-teal-700 hover:underline">
          Back to chat
        </Link>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6">
        <section className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">Dashboard</h1>
            <p className="mt-1 text-sm text-slate-600">
              How the assistant behaves with real users. Counts only: no message text is shown.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <div role="group" aria-label="Time range" className="flex rounded-lg ring-1 ring-slate-300">
              {WINDOWS.map((w) => (
                <button
                  key={w}
                  onClick={() => setDays(w)}
                  aria-pressed={days === w}
                  className={`px-3 py-1.5 first:rounded-l-lg last:rounded-r-lg ${
                    days === w ? 'bg-teal-700 text-white' : 'bg-white text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  {w} days
                </button>
              ))}
            </div>
            <label className="flex items-center gap-1.5 text-slate-600">
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} />
              Auto-refresh
            </label>
            <button
              onClick={() => void load()}
              className="rounded-lg bg-white px-3 py-1.5 text-slate-700 ring-1 ring-slate-300 hover:bg-slate-50"
            >
              Refresh
            </button>
          </div>
        </section>

        {error ? (
          <p role="alert" className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {error}
          </p>
        ) : null}

        {!data ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Tile label="Answers" value={num(data.usage.answers)} note={`${num(data.usage.active_conversations)} conversations`} />
              <Tile label="Answer rate" value={pct(data.answer_rate)} note="answered, not refused" />
              <Tile label="Latency p50 / p95" value={`${ms(data.latency_ms.p50)} / ${ms(data.latency_ms.p95)}`} note={`max ${ms(data.latency_ms.max)}`} />
              <Tile label="Helpful rate" value={pct(data.feedback.helpful_rate)} note={`👍 ${data.feedback.up} · 👎 ${data.feedback.down}`} />
              <Tile label="Safety events" value={num(safetyTotal)} note="crisis, emergency, refusals" />
              <Tile label="Users" value={num(data.usage.users_total)} note={`${num(data.usage.new_users)} new`} />
              <Tile label="LLM tokens" value={num(data.tokens.in + data.tokens.out)} note={`${num(data.tokens.in)} in · ${num(data.tokens.out)} out`} />
              <Tile label="Corpus" value={num(data.corpus.documents)} note="documents indexed" />
            </section>

            <div className="grid gap-6 lg:grid-cols-2">
              <Panel title="Answers per day">
                <BarChart
                  points={daily.map((d) => ({ key: d.date, value: d.answers, detail: dayDetail(d) }))}
                  unit="answers"
                />
              </Panel>
              <Panel title="Safety events per day">
                <BarChart
                  points={daily.map((d) => ({ key: d.date, value: d.safety_events, detail: `${d.safety_events} events` }))}
                  unit="events"
                />
              </Panel>
              <Panel title="Refusals by reason">
                <HBars rows={data.refusals_by_reason} empty="No refusals in this window." />
              </Panel>
              <Panel title="Safety events by kind">
                <HBars rows={data.safety_events} empty="No safety events in this window." />
              </Panel>
              <Panel title="Answers by outcome">
                <HBars rows={data.answers_by_status} empty="No answers in this window." />
              </Panel>
              <Panel title="System">
                <dl className="space-y-2 text-sm">
                  <Row k="Answer model" v={data.llm.models.length ? data.llm.models.join(' → ') : 'none (extractive)'} />
                  <Row k="If the model fails" v={data.llm.fallback} />
                  {Object.entries(data.corpus.documents_by_source).map(([k, v]) => (
                    <Row key={k} k={`Corpus · ${k}`} v={num(v)} />
                  ))}
                  <Row k="Feedback coverage" v={pct(data.feedback.coverage)} />
                </dl>
                <p className="mt-3 text-xs text-slate-500">
                  Live request rates, errors and model latency: Prometheus at <code>/metrics</code>, Grafana dashboard in{' '}
                  <code>deploy/observability</code>.
                </p>
              </Panel>
            </div>

            <p className="text-xs text-slate-500">
              Last {data.window_days} days · updated {updated?.toLocaleTimeString() ?? '—'}
              {auto ? ' · refreshes every 30 s' : ''}
            </p>
          </>
        )}
      </main>
    </div>
  )
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {note ? <p className="mt-0.5 text-xs text-slate-500">{note}</p> : null}
    </div>
  )
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
      <h2 className="mb-3 font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-right font-medium text-slate-800">{v}</dd>
    </div>
  )
}

interface Point {
  key: string
  value: number
  detail: string
}

/** Single-series column chart with a hover tooltip and a table view. */
function BarChart({ points, unit }: { points: Point[]; unit: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 600
  const H = 180
  const pad = { l: 32, r: 8, t: 8, b: 22 }
  const max = Math.max(1, ...points.map((p) => p.value))
  const ticks = niceTicks(max)
  const top = ticks[ticks.length - 1]
  const n = Math.max(points.length, 1)
  const slot = (W - pad.l - pad.r) / n
  const bw = Math.max(2, Math.min(28, slot - 2))
  const y = (v: number) => pad.t + (H - pad.t - pad.b) * (1 - v / top)
  const every = Math.ceil(n / 7)
  const total = points.reduce((a, p) => a + p.value, 0)

  if (total === 0) return <p className="py-10 text-center text-sm text-slate-500">No {unit} in this window.</p>

  return (
    <div>
      <div className="relative">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${unit} per day, total ${total}`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={pad.l} x2={W - pad.r} y1={y(t)} y2={y(t)} stroke="#e2e8f0" strokeWidth={1} />
              <text x={pad.l - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="#64748b">
                {t}
              </text>
            </g>
          ))}
          {points.map((p, i) => {
            const x = pad.l + i * slot + (slot - bw) / 2
            const h = Math.max(0, H - pad.b - y(p.value))
            return (
              <g key={p.key} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={pad.l + i * slot} y={pad.t} width={slot} height={H - pad.t - pad.b} fill="transparent" />
                {h > 0 ? (
                  <path d={roundedTop(x, H - pad.b - h, bw, h, Math.min(4, bw / 2, h))} fill={hover === i ? '#115e59' : '#0f766e'} />
                ) : null}
                {i % every === 0 ? (
                  <text x={x + bw / 2} y={H - 6} textAnchor="middle" fontSize={11} fill="#64748b">
                    {p.key.slice(5)}
                  </text>
                ) : null}
              </g>
            )
          })}
        </svg>
        {hover != null ? (
          <div
            className="pointer-events-none absolute top-0 rounded-lg bg-slate-900 px-2 py-1 text-xs text-white shadow"
            style={{ left: `${((pad.l + hover * slot + slot / 2) / W) * 100}%`, transform: 'translateX(-50%)' }}
          >
            <span className="font-semibold">{points[hover].key}</span> · {points[hover].detail}
          </div>
        ) : null}
      </div>
      <details className="mt-2 text-xs text-slate-600">
        <summary className="cursor-pointer">Table</summary>
        <table className="mt-2 w-full">
          <tbody>
            {points
              .filter((p) => p.value > 0)
              .map((p) => (
                <tr key={p.key} className="border-t border-slate-100">
                  <td className="py-1">{p.key}</td>
                  <td className="py-1 text-right tabular-nums">{p.value}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </div>
  )
}

/** Ranked horizontal bars: label and value in text ink, the bar carries magnitude only. */
function HBars({ rows, empty }: { rows: Record<string, number>; empty: string }) {
  const items = Object.entries(rows).sort((a, b) => b[1] - a[1])
  if (!items.length) return <p className="py-6 text-center text-sm text-slate-500">{empty}</p>
  const max = Math.max(...items.map(([, v]) => v))
  return (
    <ul className="space-y-2">
      {items.map(([k, v]) => (
        <li key={k} title={`${label(k)}: ${v}`}>
          <div className="flex justify-between text-sm">
            <span className="capitalize text-slate-700">{label(k)}</span>
            <span className="tabular-nums text-slate-900">{num(v)}</span>
          </div>
          <div className="mt-1 h-2 rounded bg-slate-100">
            <div className="h-2 rounded bg-teal-700" style={{ width: `${(v / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function dayDetail(d: DailyMetrics): string {
  const parts = Object.entries(d.by_status).map(([k, v]) => `${label(k)} ${v}`)
  return `${d.answers} answers${parts.length ? ` (${parts.join(', ')})` : ''}${
    d.avg_latency_ms != null ? ` · avg ${ms(d.avg_latency_ms)}` : ''
  }`
}

function niceTicks(max: number): number[] {
  const step = max <= 5 ? 1 : 10 ** Math.floor(Math.log10(max / 4)) * ([1, 2, 5].find((m) => (max / 4) / (10 ** Math.floor(Math.log10(max / 4)) * m) <= 1) ?? 10)
  const ticks: number[] = []
  for (let t = 0; t <= max + step - 1e-9; t += step) ticks.push(Math.round(t))
  if (ticks[ticks.length - 1] < max) ticks.push(ticks[ticks.length - 1] + step)
  return ticks
}

function roundedTop(x: number, y: number, w: number, h: number, r: number): string {
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`
}
