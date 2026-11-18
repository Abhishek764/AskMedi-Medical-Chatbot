import type { DailyMetrics } from '../api/types'

/** One entry per calendar day in the window, zeros where nothing happened. */
export function fillDays(daily: DailyMetrics[], days: number, today = new Date()): DailyMetrics[] {
  const byDate = new Map(daily.map((d) => [d.date, d]))
  const out: DailyMetrics[] = []
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - i))
    const key = d.toISOString().slice(0, 10)
    out.push(byDate.get(key) ?? { date: key, answers: 0, by_status: {}, avg_latency_ms: null, safety_events: 0 })
  }
  return out
}
