import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { AppSkeleton, LiquidFilter } from './components/Layout'
import { Consent, Forgot, Login, Register } from './pages/Auth'
import Admin from './pages/Admin'
import Chat from './pages/Chat'
import Landing from './pages/Landing'
import Policies from './pages/Policies'
import Settings from './pages/Settings'

const Loading = AppSkeleton

/** Signed-in only; migrated v1 accounts are sent to consent first. */
function Private({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  if (user.consent_required) return <Navigate to="/consent" replace />
  return children
}

/** Admins only (the API enforces this too; this just avoids showing an empty page). */
function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user?.role === 'admin' ? children : <Navigate to="/chat" replace />
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
      <LiquidFilter />
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
          <Route path="/policies" element={<Private><Policies /></Private>} />
          <Route path="/admin" element={<Private><AdminOnly><Admin /></AdminOnly></Private>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
