import { useCallback, useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError, type Conversation } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { DISCLAIMER, Logo } from '../components/Layout'
import { Turn, type TurnModel } from '../components/Turn'
import { applyEvent, pendingAssistant, turnsFromMessages, userTurn } from '../components/turns'

const EXAMPLES = [
  'What are the symptoms of dengue?',
  'What are the common side effects of metformin?',
  'How is tuberculosis spread?',
  'Is there evidence that vitamin D supplements help?',
]

export default function Chat() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [turns, setTurns] = useState<TurnModel[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)

  const loadList = useCallback(() => api.listConversations().then(setConversations).catch(() => {}), [])
  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    setError(null)
    if (!id) return setTurns([])
    api
      .getConversation(id)
      .then((c) => setTurns(turnsFromMessages(c.messages)))
      .catch(() => navigate('/chat', { replace: true }))
  }, [id, navigate])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  const ask = async (question: string, answer?: { step: number; choices: string[] }) => {
    const q = question.trim()
    if (!q || busy) return
    setBusy(true)
    setError(null)
    setInput('')
    let convId = id
    try {
      if (!convId) {
        convId = (await api.createConversation()).id
        navigate(`/chat/${convId}`, { replace: true })
      }
      const key = crypto.randomUUID()
      setTurns((t) => [...t, userTurn(`${key}-q`, q), pendingAssistant(key)])
      abort.current = new AbortController()
      for await (const ev of api.ask(convId, answer ?? q, abort.current.signal)) {
        setTurns((t) => t.map((turn) => (turn.key === key ? applyEvent(turn, ev) : turn)))
      }
      loadList()
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError(err instanceof ApiError ? err.message : 'Connection problem. Please try again.')
        setTurns((t) => t.filter((turn) => turn.status !== 'streaming'))
      }
    } finally {
      setBusy(false)
      abort.current = null
    }
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    void ask(input)
  }
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void ask(input)
    }
  }

  const remove = async (convId: string) => {
    await api.deleteConversation(convId)
    if (convId === id) navigate('/chat')
    loadList()
  }

  return (
    <div className="flex h-dvh bg-slate-50 text-slate-900">
      <aside
        className={`${menuOpen ? 'flex' : 'hidden'} fixed inset-y-0 left-0 z-20 w-72 flex-col border-r border-slate-200 bg-white md:static md:flex`}
      >
        <div className="flex items-center justify-between p-4">
          <Logo />
          <button className="md:hidden" onClick={() => setMenuOpen(false)} aria-label="Close menu">
            ✕
          </button>
        </div>
        <Link
          to="/chat"
          onClick={() => setMenuOpen(false)}
          className="mx-4 rounded-lg border border-teal-700 px-3 py-2 text-center text-sm font-semibold text-teal-800 hover:bg-teal-50"
        >
          + New chat
        </Link>
        <nav className="mt-3 flex-1 overflow-y-auto px-2" aria-label="Conversations">
          {conversations.map((c) => (
            <div
              key={c.id}
              className={`group flex items-center rounded-lg ${c.id === id ? 'bg-teal-50' : 'hover:bg-slate-100'}`}
            >
              <Link
                to={`/chat/${c.id}`}
                onClick={() => setMenuOpen(false)}
                className="flex-1 truncate px-3 py-2 text-sm"
                title={c.title}
              >
                {c.title}
              </Link>
              <button
                onClick={() => remove(c.id)}
                aria-label={`Delete ${c.title}`}
                className="px-2 text-slate-400 opacity-0 hover:text-rose-600 group-hover:opacity-100"
              >
                🗑
              </button>
            </div>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-4 text-sm">
          <p className="truncate text-slate-600" title={user?.email}>
            {user?.email}
            {user?.role === 'provider' ? (
              <span className="ml-1 rounded bg-teal-100 px-1.5 text-xs text-teal-800">provider</span>
            ) : null}
          </p>
          <div className="mt-2 flex gap-3">
            <Link to="/settings" className="text-teal-700 hover:underline">
              Settings
            </Link>
            <button onClick={() => logout().then(() => navigate('/'))} className="text-slate-600 hover:underline">
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <button onClick={() => setMenuOpen(true)} aria-label="Open menu">
            ☰
          </button>
          <Logo />
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-4 px-4 py-6">
            {turns.length === 0 ? (
              <div className="pt-10 text-center">
                <h1 className="text-2xl font-semibold">What would you like to know?</h1>
                <p className="mt-2 text-sm text-slate-500">
                  Ask about a condition, a symptom or a medicine. Answers cite their sources.
                </p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {EXAMPLES.map((q) => (
                    <button
                      key={q}
                      onClick={() => ask(q)}
                      className="rounded-xl bg-white px-4 py-3 text-left text-sm shadow-sm ring-1 ring-slate-200 hover:ring-teal-400"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              turns.map((t, i) => (
                <Turn
                  key={t.key}
                  turn={t}
                  active={!busy && i === turns.length - 1}
                  onAnswer={(step, choices, labels) => ask(labels.join(', '), { step, choices })}
                />
              ))
            )}
            <div ref={bottom} />
          </div>
        </div>

        <form onSubmit={submit} className="border-t border-slate-200 bg-white px-4 py-3">
          <div className="mx-auto max-w-3xl">
            {error ? (
              <p role="alert" className="mb-2 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">
                {error}
              </p>
            ) : null}
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
                maxLength={1000}
                placeholder="Ask a health or medicine question…"
                aria-label="Your question"
                className="max-h-40 min-h-11 flex-1 resize-y rounded-xl border border-slate-300 px-3 py-2.5 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              />
              {busy ? (
                <button
                  type="button"
                  onClick={() => abort.current?.abort()}
                  className="rounded-xl bg-slate-200 px-4 py-2.5 font-semibold text-slate-800"
                >
                  Stop
                </button>
              ) : (
                <button
                  disabled={!input.trim()}
                  className="rounded-xl bg-teal-700 px-4 py-2.5 font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
                >
                  Send
                </button>
              )}
            </div>
            <p className="mt-2 text-center text-[11px] text-slate-500">{DISCLAIMER}</p>
          </div>
        </form>
      </main>
    </div>
  )
}
