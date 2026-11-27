import {
  ArrowUp,
  FileSearch,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  MessageSquarePlus,
  Pill,
  Settings as SettingsIcon,
  Square,
  Stethoscope,
  Trash2,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError, type Conversation } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { Ambient, DISCLAIMER, Logo, Mark, Skeleton, TopProgress } from '../components/Layout'
import { gsap, MOTION_OK, useGSAP, useTilt } from '../lib/motion'
import { Turn, TurnSkeleton, type TurnModel } from '../components/Turn'
import { applyEvent, pendingAssistant, turnsFromMessages, userTurn } from '../components/turns'

// Grouped by kind so people scan four labelled choices, not four sentences.
const EXAMPLES = [
  { icon: Stethoscope, kind: 'Condition', q: 'What are the symptoms of dengue?' },
  { icon: Pill, kind: 'Medicine', q: 'What are the common side effects of metformin?' },
  { icon: FileSearch, kind: 'How it spreads', q: 'How is tuberculosis spread?' },
  { icon: FlaskConical, kind: 'Evidence', q: 'Is there evidence that vitamin D supplements help?' },
]

const MAX = 1000

export default function Chat() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState<Conversation[] | null>(null)
  const [turns, setTurns] = useState<TurnModel[]>([])
  const [loadingConv, setLoadingConv] = useState(false)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const abort = useRef<AbortController | null>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const box = useRef<HTMLTextAreaElement>(null)
  // A conversation this page just created and is streaming into: its URL change must not
  // reload it from the server, or the empty server copy would replace the live reply.
  const justCreated = useRef<string | null>(null)

  const loadList = useCallback(
    () =>
      api
        .listConversations()
        .then(setConversations)
        .catch(() => setConversations((c) => c ?? [])),
    [],
  )
  useEffect(() => {
    loadList()
  }, [loadList])

  useEffect(() => {
    setError(null)
    if (!id) return setTurns([])
    if (id === justCreated.current) {
      justCreated.current = null
      return
    }
    setLoadingConv(true)
    api
      .getConversation(id)
      .then((c) => setTurns(turnsFromMessages(c.messages)))
      .catch(() => navigate('/chat', { replace: true }))
      .finally(() => setLoadingConv(false))
  }, [id, navigate])

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns])

  // Grow the composer with its content, up to a cap.
  useLayoutEffect(() => {
    const el = box.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [input])

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
        justCreated.current = convId
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
        setError(err instanceof ApiError ? err.message : 'Connection problem. Check your network and send again.')
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

  const close = () => setMenuOpen(false)
  const initial = (user?.email ?? '?').charAt(0).toUpperCase()

  return (
    <div className="flex h-dvh text-fg">
      <Ambient />
      <TopProgress active={busy || loadingConv || conversations === null} />

      {menuOpen ? (
        <button
          aria-label="Close menu"
          onClick={close}
          className="fixed inset-0 z-20 bg-ink/70 backdrop-blur-sm md:hidden"
        />
      ) : null}

      <aside
        className={`${menuOpen ? 'translate-x-0' : '-translate-x-full'} glass glass-strong fixed inset-y-0 left-0 z-30 flex w-72 flex-col rounded-none border-y-0 border-l-0 transition-transform duration-300 md:static md:translate-x-0 md:bg-none md:bg-white/[0.025]`}
      >
        <div className="flex items-center justify-between p-4">
          <Logo to="/chat" />
          <button className="btn min-h-10 px-2 text-muted hover:text-fg md:hidden" onClick={close} aria-label="Close menu">
            <X className="size-5" />
          </button>
        </div>
        <Link to="/chat" onClick={close} className="btn btn-ghost mx-4 justify-start">
          <MessageSquarePlus className="size-4 text-accent" aria-hidden />
          New chat
        </Link>

        <p className="eyebrow mt-6 px-5 text-faint">Recent</p>
        <nav className="mt-2 flex-1 space-y-0.5 overflow-y-auto px-2 pb-2" aria-label="Conversations">
          {conversations === null ? (
            Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="mx-2 my-2 h-5" />)
          ) : conversations.length === 0 ? (
            <p className="px-3 py-2 text-sm text-faint">Your questions will appear here.</p>
          ) : (
            conversations.map((c) => {
              const current = c.id === id
              return (
                <div
                  key={c.id}
                  className={`group relative flex items-center rounded-xl transition-colors ${
                    current ? 'bg-accent/10 text-fg' : 'text-muted hover:bg-white/5 hover:text-fg'
                  }`}
                >
                  {current ? <span aria-hidden className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-accent" /> : null}
                  <Link
                    to={`/chat/${c.id}`}
                    onClick={close}
                    aria-current={current ? 'page' : undefined}
                    className="flex-1 truncate px-3 py-2.5 text-sm"
                    title={c.title}
                  >
                    {c.title}
                  </Link>
                  <button
                    onClick={() => remove(c.id)}
                    aria-label={`Delete ${c.title}`}
                    className="mr-1 grid size-8 shrink-0 place-items-center rounded-lg text-faint transition hover:bg-danger/15 hover:text-danger focus-visible:opacity-100 md:opacity-0 md:group-hover:opacity-100"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              )
            })
          )}
        </nav>

        <div className="border-t border-line p-3">
          <div className="flex items-center gap-3 px-2 py-2">
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent to-lime font-semibold text-accent-ink">
              {initial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm text-fg" title={user?.email}>
                {user?.email}
              </p>
              <p className="text-xs capitalize text-faint">{user?.role ?? 'member'}</p>
            </div>
          </div>
          <div className="mt-1 grid gap-0.5 text-sm">
            <SideLink to="/settings" icon={SettingsIcon} label="Settings" onClick={close} />
            <SideLink to="/policies" icon={FileSearch} label="Policy demo" onClick={close} />
            {user?.role === 'admin' ? (
              <SideLink to="/admin" icon={LayoutDashboard} label="Dashboard" onClick={close} />
            ) : null}
            <button
              onClick={() => logout().then(() => navigate('/'))}
              className="flex items-center gap-3 rounded-lg px-2 py-2 text-left text-muted transition hover:bg-white/5 hover:text-fg"
            >
              <LogOut className="size-4" aria-hidden />
              Sign out
            </button>
          </div>
        </div>
      </aside>

      <main className="relative flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-line px-3 py-2.5 md:hidden">
          <button className="btn min-h-10 px-2" onClick={() => setMenuOpen(true)} aria-label="Open menu">
            <Menu className="size-5" />
          </button>
          <Logo to="/chat" />
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl space-y-5 px-4 pb-40 pt-8">
            {loadingConv ? (
              <TurnSkeleton />
            ) : turns.length === 0 ? (
              <EmptyState onAsk={(q) => void ask(q)} />
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

        <form
          onSubmit={submit}
          className="pointer-events-none absolute inset-x-0 bottom-0 bg-gradient-to-t from-ink via-ink/90 to-transparent px-3 pb-3 pt-10 sm:px-4"
        >
          <div className="pointer-events-auto mx-auto max-w-3xl">
            {error ? (
              <p role="alert" className="mb-2 rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-rose-200">
                {error}
              </p>
            ) : null}
            <div className="glass glass-liquid flex items-end gap-2 rounded-2xl p-2 transition focus-within:border-accent/40 focus-within:shadow-[0_0_0_4px_rgb(74_222_128/0.08)]">
              <textarea
                ref={box}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
                maxLength={MAX}
                placeholder="Ask a health or medicine question…"
                aria-label="Your question"
                className="max-h-[200px] min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 text-[0.9375rem] text-fg outline-none placeholder:text-faint"
              />
              {busy ? (
                <button
                  type="button"
                  onClick={() => abort.current?.abort()}
                  aria-label="Stop answering"
                  className="btn btn-ghost size-11 shrink-0 p-0"
                >
                  <Square className="size-4 fill-current" />
                </button>
              ) : (
                <button disabled={!input.trim()} aria-label="Send" className="btn btn-primary size-11 shrink-0 p-0">
                  <ArrowUp className="size-5" strokeWidth={2.5} />
                </button>
              )}
            </div>
            <p className="mt-2 flex justify-between gap-4 px-1 text-[11px] text-faint">
              <span>{DISCLAIMER}</span>
              {input.length > MAX * 0.8 ? (
                <span className="shrink-0 font-mono tabular-nums">
                  {input.length}/{MAX}
                </span>
              ) : null}
            </p>
          </div>
        </form>
      </main>
    </div>
  )
}

function SideLink(props: { to: string; icon: typeof SettingsIcon; label: string; onClick: () => void }) {
  const Icon = props.icon
  return (
    <Link
      to={props.to}
      onClick={props.onClick}
      className="flex items-center gap-3 rounded-lg px-2 py-2 text-muted transition hover:bg-white/5 hover:text-fg"
    >
      <Icon className="size-4" aria-hidden />
      {props.label}
    </Link>
  )
}

function EmptyState({ onAsk }: { onAsk: (q: string) => void }) {
  const root = useRef<HTMLDivElement>(null)
  useGSAP(
    () => {
      const mm = gsap.matchMedia()
      mm.add(MOTION_OK, () => {
        gsap
          .timeline({ defaults: { ease: 'power3.out' } })
          .from('.es-mark', { scale: 0.6, rotationY: -120, transformPerspective: 600, autoAlpha: 0, duration: 1, ease: 'expo.out' })
          .from('.es-title, .es-copy', { y: 16, autoAlpha: 0, duration: 0.6, stagger: 0.08 }, '-=0.6')
          .from('.es-card', { y: 30, rotationX: -20, transformPerspective: 800, autoAlpha: 0, duration: 0.8, stagger: 0.07 }, '-=0.4')
        gsap.to('.es-mark', { y: -6, rotationY: 12, duration: 2.8, ease: 'sine.inOut', repeat: -1, yoyo: true, delay: 1.2 })
      })
      return () => mm.revert()
    },
    { scope: root },
  )
  return (
    <div ref={root} className="pt-[8vh] text-center">
      <span className="es-mark glass glass-liquid mx-auto grid size-16 place-items-center rounded-2xl text-accent shadow-[0_0_60px_-10px_rgb(74_222_128/0.55)]">
        <Mark className="size-8" />
      </span>
      <h1 className="es-title mt-6 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
        What would you like to know?
      </h1>
      <p className="es-copy mx-auto mt-2 max-w-md text-sm text-muted">
        Ask about a condition, a symptom or a medicine. Every answer cites its sources.
      </p>
      <div className="mt-9 grid gap-3 text-left [perspective:1000px] sm:grid-cols-2">
        {EXAMPLES.map((ex) => (
          <ExampleCard key={ex.q} {...ex} onAsk={onAsk} />
        ))}
      </div>
    </div>
  )
}

function ExampleCard({ icon: Icon, kind, q, onAsk }: (typeof EXAMPLES)[number] & { onAsk: (q: string) => void }) {
  const ref = useRef<HTMLButtonElement>(null)
  useTilt(ref, { max: 6 })
  return (
    <button
      ref={ref}
      onClick={() => onAsk(q)}
      className="es-card glass group rounded-2xl px-4 py-3.5 text-left will-change-transform hover:border-accent/30"
    >
      <span className="eyebrow flex items-center gap-1.5 text-faint transition-colors group-hover:text-accent">
        <Icon className="size-3.5" aria-hidden />
        {kind}
      </span>
      <span className="mt-1.5 block text-sm text-fg">{q}</span>
    </button>
  )
}
