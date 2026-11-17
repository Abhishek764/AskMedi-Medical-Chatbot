import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
  setUser: (user: User | null) => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.onSessionExpired = () => setUser(null)
    api.restoreSession().then((u) => {
      setUser(u)
      setLoading(false)
    })
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setUser(await api.login(email, password))
  }, [])
  const register = useCallback(async (email: string, password: string) => {
    setUser(await api.register(email, password))
  }, [])
  const logout = useCallback(async () => {
    await api.logout()
    setUser(null)
  }, [])
  const refreshUser = useCallback(async () => {
    setUser(await api.me())
  }, [])

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refreshUser, setUser }),
    [user, loading, login, register, logout, refreshUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
