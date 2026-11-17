import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { Consent, Forgot, Login, Register } from './pages/Auth'
import Chat from './pages/Chat'
import Landing from './pages/Landing'
import Settings from './pages/Settings'

function Loading() {
  return <div className="grid min-h-dvh place-items-center text-slate-500">Loading…</div>
}

/** Signed-in only; migrated v1 accounts are sent to consent first. */
function Private({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  if (user.consent_required) return <Navigate to="/consent" replace />
  return children
}

/** Signed-in, consent not required yet (the consent page itself). */
function SignedIn({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return user.consent_required ? children : <Navigate to="/chat" replace />
}

/** Signed-out only (landing, sign-in, sign-up). */
function Public({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  return user ? <Navigate to="/chat" replace /> : children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Public><Landing /></Public>} />
          <Route path="/login" element={<Public><Login /></Public>} />
          <Route path="/register" element={<Public><Register /></Public>} />
          <Route path="/forgot" element={<Public><Forgot /></Public>} />
          <Route path="/consent" element={<SignedIn><Consent /></SignedIn>} />
          <Route path="/chat" element={<Private><Chat /></Private>} />
          <Route path="/chat/:id" element={<Private><Chat /></Private>} />
          <Route path="/settings" element={<Private><Settings /></Private>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
