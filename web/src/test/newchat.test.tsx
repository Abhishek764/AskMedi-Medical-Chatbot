import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import type { ChatEvent } from '../api/types'

// The first question in a new chat creates the conversation and changes the URL. The server
// copy of that conversation is still empty, so reloading it would wipe the streaming reply.
vi.mock('../auth/AuthContext', () => ({
  useAuth: () => ({ user: { email: 'demo@example.com', role: 'public' }, logout: vi.fn() }),
}))
vi.mock('../api/client', () => ({
  api: {
    listConversations: vi.fn(async () => []),
    createConversation: vi.fn(async () => ({ id: 'c1' })),
    getConversation: vi.fn(async () => ({ id: 'c1', messages: [] })),
    async *ask(): AsyncGenerator<ChatEvent> {
      await new Promise((r) => setTimeout(r, 20)) // let the URL change land first
      yield { type: 'sentence', data: { text: 'Dengue causes high fever.', citations: [1] } }
      yield { type: 'done', data: { message_id: 'm1', status: 'complete' } }
    },
  },
}))

Element.prototype.scrollIntoView = vi.fn() // not implemented in jsdom

const { default: Chat } = await import('../pages/Chat')
const { api } = await import('../api/client')

describe('new chat', () => {
  it('keeps the streamed reply after the URL changes to the new conversation', async () => {
    render(
      <MemoryRouter initialEntries={['/chat']}>
        <Routes>
          <Route path="/chat" element={<Chat />} />
          <Route path="/chat/:id" element={<Chat />} />
        </Routes>
      </MemoryRouter>,
    )
    const box = screen.getByLabelText('Your question')
    fireEvent.change(box, { target: { value: 'What are the symptoms of dengue?' } })
    fireEvent.keyDown(box, { key: 'Enter' })

    expect(await screen.findByText(/Dengue causes high fever\./)).toBeInTheDocument()
    // The navigation to /chat/c1 commits as a transition, possibly after the reply arrived:
    // give it time to land, then the reply must still be on screen.
    await new Promise((r) => setTimeout(r, 200))
    expect(screen.getByText(/Dengue causes high fever\./)).toBeInTheDocument()
    expect(api.getConversation).not.toHaveBeenCalled()
  })
})
