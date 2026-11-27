import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { CardPage, ErrorText, Field, primaryButton } from '../components/Layout'

function message(err: unknown): string {
  return err instanceof ApiError ? err.message : 'Something went wrong. Please try again.'
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      navigate('/chat')
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <CardPage title="Welcome back" subtitle="Sign in to continue your conversations.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        <ErrorText error={error} />
        <button className={primaryButton} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <div className="mt-5 flex justify-between text-sm">
        <Link to="/forgot" className="link">
          Forgot password?
        </Link>
        <Link to="/register" className="link">
          Create an account
        </Link>
      </div>
    </CardPage>
  )
}

export function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [adult, setAdult] = useState(false)
  const [accept, setAccept] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!adult || !accept) {
      setError('Please confirm both boxes to continue.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await register(email, password)
      navigate('/chat')
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <CardPage title="Create your account" subtitle="Free. Your conversations stay private to you.">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field
          label="Password"
          hint="at least 10 characters"
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="new-password"
          minLength={10}
        />
        <ConsentBoxes adult={adult} setAdult={setAdult} accept={accept} setAccept={setAccept} />
        <ErrorText error={error} />
        <button className={primaryButton} disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="mt-5 text-sm text-muted">
        Already have an account?{' '}
        <Link to="/login" className="link">
          Sign in
        </Link>
      </p>
    </CardPage>
  )
}

export function ConsentBoxes(props: {
  adult: boolean
  setAdult: (v: boolean) => void
  accept: boolean
  setAccept: (v: boolean) => void
}) {
  return (
    <div className="space-y-3 rounded-xl border border-line bg-white/[0.03] p-3 text-sm text-muted">
      <label className="flex cursor-pointer gap-2.5 leading-snug">
        <input type="checkbox" className="mt-0.5 shrink-0" checked={props.adult} onChange={(e) => props.setAdult(e.target.checked)} />
        I am 18 or older.
      </label>
      <label className="flex cursor-pointer gap-2.5 leading-snug">
        <input type="checkbox" className="mt-0.5 shrink-0" checked={props.accept} onChange={(e) => props.setAccept(e.target.checked)} />
        I understand AskMedi gives general information only, not medical advice, diagnosis or prescriptions.
      </label>
    </div>
  )
}

/** Accounts migrated from v1 confirm age and the disclaimer once before chatting. */
export function Consent() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [adult, setAdult] = useState(false)
  const [accept, setAccept] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!adult || !accept) return setError('Please confirm both boxes to continue.')
    try {
      setUser(await api.consent())
      navigate('/chat')
    } catch (err) {
      setError(message(err))
    }
  }

  return (
    <CardPage title="Before you continue">
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-muted">AskMedi has been updated. Please confirm the following once.</p>
        <ConsentBoxes adult={adult} setAdult={setAdult} accept={accept} setAccept={setAccept} />
        <ErrorText error={error} />
        <button className={primaryButton}>Continue</button>
      </form>
    </CardPage>
  )
}

export function Forgot() {
  const [email, setEmail] = useState('')
  const [done, setDone] = useState<string | null>(null)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    try {
      setDone((await api.requestPasswordReset(email)).status)
    } catch (err) {
      setDone(message(err))
    }
  }

  return (
    <CardPage title="Reset your password">
      {done ? (
        <p className="rounded-xl border border-accent/25 bg-accent/10 px-3 py-2 text-sm text-fg">{done}</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          <button className={primaryButton}>Send reset link</button>
        </form>
      )}
      <Link to="/login" className="link mt-5 block text-sm">
        Back to sign in
      </Link>
    </CardPage>
  )
}
