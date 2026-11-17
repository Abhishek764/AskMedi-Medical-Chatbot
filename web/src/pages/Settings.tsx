import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ErrorText, Field, Logo } from '../components/Layout'

export default function Settings() {
  const { user, setUser } = useAuth()
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  const download = async () => {
    const data = await api.exportData()
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
    const a = Object.assign(document.createElement('a'), { href: url, download: 'askmedi-data.json' })
    a.click()
    URL.revokeObjectURL(url)
  }

  const remove = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await api.deleteAccount(password)
      setUser(null)
      navigate('/')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not delete the account.')
    }
  }

  return (
    <div className="min-h-dvh bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <Logo />
        <Link to="/chat" className="text-sm text-teal-700 hover:underline">
          Back to chat
        </Link>
      </header>
      <main className="mx-auto max-w-xl space-y-6 px-4 py-8">
        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <h1 className="text-xl font-semibold">Account</h1>
          <dl className="mt-3 space-y-1 text-sm">
            <div className="flex gap-2">
              <dt className="text-slate-500">Email</dt>
              <dd>{user?.email}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="text-slate-500">Role</dt>
              <dd>{user?.role}</dd>
            </div>
          </dl>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <h2 className="font-semibold">Your data</h2>
          <p className="mt-1 text-sm text-slate-600">Download every conversation and message we hold for you.</p>
          <button onClick={download} className="mt-3 rounded-lg border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50">
            Download my data (JSON)
          </button>
        </section>

        <section className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-rose-200">
          <h2 className="font-semibold text-rose-800">Delete account</h2>
          <p className="mt-1 text-sm text-slate-600">
            Permanently deletes your account and all conversations. This cannot be undone.
          </p>
          <form onSubmit={remove} className="mt-3 space-y-3">
            <Field label="Confirm with your password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
            <ErrorText error={error} />
            <button className="rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700">
              Delete my account
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}
