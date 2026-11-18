import { describe, expect, it } from 'vitest'
import { fillDays } from '../pages/adminData'

describe('fillDays', () => {
  it('returns one row per day with zeros for empty days', () => {
    const rows = fillDays(
      [{ date: '2026-11-17', answers: 3, by_status: { complete: 3 }, avg_latency_ms: 900, safety_events: 1 }],
      3,
      new Date('2026-11-18T10:00:00Z'),
    )
    expect(rows.map((r) => r.date)).toEqual(['2026-11-16', '2026-11-17', '2026-11-18'])
    expect(rows.map((r) => r.answers)).toEqual([0, 3, 0])
  })
})
