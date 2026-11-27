import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ApiError } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { ErrorText, Field, PageHeader } from '../components/Layout'

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
    <div className="min-h-dvh">
      <PageHeader />
      <main className="mx-auto max-w-xl animate-rise space-y-5 px-4 py-10">
        <section className="glass rounded-2xl p-6">
          <h1 className="font-display text-xl font-semibold">Account</h1>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex gap-2">
              <dt className="w-14 text-muted">Email</dt>
              <dd>{user?.email}</dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-14 text-muted">Role</dt>
              <dd className="capitalize">{user?.role}</dd>
            </div>
          </dl>
        </section>

        <section className="glass rounded-2xl p-6">
          <h2 className="font-semibold">Your data</h2>
          <p className="mt-1 text-sm text-muted">Download every conversation and message we hold for you.</p>
          <button onClick={download} className="btn btn-ghost mt-4 text-sm">
            Download my data (JSON)
          </button>
        </section>

        <section className="glass rounded-2xl border-danger/30 p-6">
          <h2 className="font-semibold text-rose-300">Delete account</h2>
          <p className="mt-1 text-sm text-muted">
            Permanently deletes your account and all conversations. This cannot be undone.
          </p>
          <form onSubmit={remove} className="mt-3 space-y-3">
            <Field label="Confirm with your password" type="password" value={password} onChange={setPassword} autoComplete="current-password" />
            <ErrorText error={error} />
            <button className="btn btn-danger text-sm">
              Delete my account
            </button>
          </form>
        </section>
      </main>
    </div>
  )
}
