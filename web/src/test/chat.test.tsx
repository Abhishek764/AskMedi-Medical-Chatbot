import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { parseBlock, readEvents } from '../api/sse'
import type { ChatEvent } from '../api/types'
import { Turn } from '../components/Turn'
import { applyEvent, pendingAssistant } from '../components/turns'

const stream = (text: string) =>
  new ReadableStream<Uint8Array>({
    start(c) {
      // split mid-event to prove buffering across chunks works
      const bytes = new TextEncoder().encode(text)
      c.enqueue(bytes.slice(0, 17))
      c.enqueue(bytes.slice(17))
      c.close()
    },
  })

describe('SSE parsing', () => {
  it('reads events split across chunks', async () => {
    const body =
      'event: status\ndata: {"stage": "retrieving"}\n\n' +
      'event: sentence\ndata: {"text": "Dengue causes fever.", "citations": [1]}\n\n' +
      'event: done\ndata: {"message_id": "m1", "status": "complete"}\n\n'
    const events: ChatEvent[] = []
    for await (const ev of readEvents(stream(body))) events.push(ev)
    expect(events.map((e) => e.type)).toEqual(['status', 'sentence', 'done'])
  })

  it('ignores blocks without data or with bad JSON', () => {
    expect(parseBlock('event: x')).toBeNull()
    expect(parseBlock('event: x\ndata: {nope')).toBeNull()
  })
})

describe('turn building', () => {
  const run = (events: ChatEvent[]) => events.reduce(applyEvent, pendingAssistant('a'))

  it('builds a cited answer', () => {
    const t = run([
      { type: 'sentence', data: { text: 'Dengue causes fever.', citations: [1] } },
      { type: 'sentence', data: { text: 'It spreads by mosquitoes.', citations: [1, 2] } },
      {
        type: 'citations',
        data: {
          items: [{ position: 1, chunk_id: 'c', doc_id: 'd', title: 'Dengue', section: null, source: 'medlineplus', url: null, score: 1 }],
          disclaimer: 'Not medical advice.',
        },
      },
      { type: 'done', data: { message_id: 'm1', status: 'complete' } },
    ])
    expect(t.text).toBe('Dengue causes fever. [1] It spreads by mosquitoes. [1][2]')
    expect(t.status).toBe('complete')
    expect(t.messageId).toBe('m1')
  })

  it('shows the crisis card with tap-to-call helplines', () => {
    const t = run([
      {
        type: 'crisis',
        data: {
          message: 'Please reach out.',
          helplines: [{ name: 'Tele-MANAS', phone: '14416', note: '24x7' }],
          directory: 'https://findahelpline.com',
        },
      },
    ])
    render(<Turn turn={t} />)
    expect(screen.getByRole('alert')).toHaveTextContent('Please reach out.')
    expect(screen.getByRole('link', { name: 'Call 14416' })).toHaveAttribute('href', 'tel:14416')
  })

  it('renders refusals as plain notices without feedback buttons', () => {
    const t = run([
      { type: 'refusal', data: { reason: 'no_sources', message: "I don't have reliable information." } },
      { type: 'done', data: { message_id: 'm2', status: 'refused' } },
    ])
    render(<Turn turn={t} />)
    expect(screen.getByText("I don't have reliable information.")).toBeInTheDocument()
    expect(screen.queryByLabelText('Helpful')).toBeNull()
  })

  it('adds a safety banner only once per kind', () => {
    const banner: ChatEvent = { type: 'banner', data: { kind: 'emergency', number: '112' } }
    expect(run([banner, banner]).banners).toEqual([{ kind: 'emergency', phone: '112' }])
  })
})
