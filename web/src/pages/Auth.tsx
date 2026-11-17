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
    <CardPage title="Sign in">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field label="Password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
        <ErrorText error={error} />
        <button className={primaryButton} disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
      <div className="mt-4 flex justify-between text-sm">
        <Link to="/forgot" className="text-teal-700 hover:underline">
          Forgot password?
        </Link>
        <Link to="/register" className="text-teal-700 hover:underline">
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
    <CardPage title="Create your account">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <Field
          label="Password (at least 10 characters)"
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
      <p className="mt-4 text-sm">
        Already have an account?{' '}
        <Link to="/login" className="text-teal-700 hover:underline">
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
    <div className="space-y-2 text-sm text-slate-700">
      <label className="flex gap-2">
        <input type="checkbox" checked={props.adult} onChange={(e) => props.setAdult(e.target.checked)} />
        I am 18 or older.
      </label>
      <label className="flex gap-2">
        <input type="checkbox" checked={props.accept} onChange={(e) => props.setAccept(e.target.checked)} />
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
        <p className="text-sm text-slate-600">AskMedi has been updated. Please confirm the following once.</p>
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
        <p className="text-sm text-slate-700">{done}</p>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Email" type="email" value={email} onChange={setEmail} autoComplete="email" />
          <button className={primaryButton}>Send reset link</button>
        </form>
      )}
      <Link to="/login" className="mt-4 block text-sm text-teal-700 hover:underline">
        Back to sign in
      </Link>
    </CardPage>
  )
}
