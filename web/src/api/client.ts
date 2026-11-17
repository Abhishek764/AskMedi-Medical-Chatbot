import { readEvents } from './sse'
import {
  ApiError,
  type AuthResponse,
  type ChatEvent,
  type Conversation,
  type ConversationDetail,
  type Tokens,
  type User,
} from './types'

/**
 * Thin client for the /v1 API.
 * - The access token lives only in memory (never localStorage), so XSS can't read a stored token.
 * - The refresh token is an httpOnly cookie set by the server; `restoreSession()` uses it.
 * - A 401 triggers one refresh attempt, then the request is retried once.
 */
export class ApiClient {
  private accessToken: string | null = null
  private refreshing: Promise<boolean> | null = null
  onSessionExpired: () => void = () => {}
  private readonly base: string

  constructor(base = '') {
    this.base = base
  }

  setAccessToken(token: string | null) {
    this.accessToken = token
  }

  private async raw(path: string, init: RequestInit = {}): Promise<Response> {
    const headers = new Headers(init.headers)
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    if (this.accessToken) headers.set('Authorization', `Bearer ${this.accessToken}`)
    return fetch(`${this.base}${path}`, { ...init, headers, credentials: 'same-origin' })
  }

  private async request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
    const res = await this.raw(path, init)
    if (res.status === 401 && retry && !path.startsWith('/v1/auth/')) {
      if (await this.refresh()) return this.request(path, init, false)
      this.onSessionExpired()
    }
    if (!res.ok) throw await toError(res)
    return res
  }

  private async json<T>(path: string, init: RequestInit = {}): Promise<T> {
    const res = await this.request(path, init)
    return (res.status === 204 ? undefined : await res.json()) as T
  }

  /** Exchange the refresh cookie for a new access token. Concurrent callers share one attempt. */
  refresh(): Promise<boolean> {
    this.refreshing ??= (async () => {
      try {
        const res = await this.raw('/v1/auth/refresh', { method: 'POST' })
        if (!res.ok) return false
        const tokens = (await res.json()) as Tokens
        this.accessToken = tokens.access_token
        return true
      } catch {
        return false
      } finally {
        this.refreshing = null
      }
    })()
    return this.refreshing
  }

  async restoreSession(): Promise<User | null> {
    if (!(await this.refresh())) return null
    try {
      return await this.me()
    } catch {
      return null
    }
  }

  async register(email: string, password: string): Promise<User> {
    const data = await this.json<AuthResponse>('/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, age_confirmed: true, accept_disclaimer: true }),
    })
    this.accessToken = data.tokens.access_token
    return data.user
  }

  async login(email: string, password: string): Promise<User> {
    const data = await this.json<AuthResponse>('/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
    this.accessToken = data.tokens.access_token
    return data.user
  }

  async logout(): Promise<void> {
    try {
      await this.raw('/v1/auth/logout', { method: 'POST' })
    } finally {
      this.accessToken = null
    }
  }

  me = () => this.json<User>('/v1/users/me')
  consent = () =>
    this.json<User>('/v1/users/me/consent', {
      method: 'POST',
      body: JSON.stringify({ age_confirmed: true, accept_disclaimer: true }),
    })
  exportData = () => this.json<unknown>('/v1/users/me/export')
  deleteAccount = (password: string) =>
    this.json<void>('/v1/users/me', { method: 'DELETE', body: JSON.stringify({ password }) })
  requestPasswordReset = (email: string) =>
    this.json<{ status: string }>('/v1/auth/request-password-reset', {
      method: 'POST',
      body: JSON.stringify({ email }),
    })

  listConversations = () => this.json<Conversation[]>('/v1/conversations?limit=50')
  getConversation = (id: string) => this.json<ConversationDetail>(`/v1/conversations/${id}`)
  createConversation = () =>
    this.json<Conversation>('/v1/conversations', { method: 'POST', body: '{}' })
  renameConversation = (id: string, title: string) =>
    this.json<Conversation>(`/v1/conversations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ title }),
    })
  deleteConversation = (id: string) =>
    this.json<void>(`/v1/conversations/${id}`, { method: 'DELETE' })
  sendFeedback = (messageId: string, rating: 1 | -1, reason?: string) =>
    this.json<void>(`/v1/messages/${messageId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ rating, reason }),
    })

  /** Ask a question (or answer a medicine-check question) and stream the reply's events. */
  async *ask(
    conversationId: string,
    input: string | { step: number; choices: string[] },
    signal?: AbortSignal,
  ): AsyncGenerator<ChatEvent> {
    const body = typeof input === 'string' ? { question: input } : { triage: input }
    const res = await this.request(`/v1/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(body),
      signal,
    })
    if (!res.body) throw new ApiError(500, 'no_stream', 'The server did not stream a response.')
    yield* readEvents(res.body)
  }
}

async function toError(res: Response): Promise<ApiError> {
  try {
    const body = (await res.json()) as { error?: { code?: string; message?: string } }
    return new ApiError(res.status, body.error?.code ?? 'error', body.error?.message ?? res.statusText)
  } catch {
    return new ApiError(res.status, 'error', res.statusText || 'Request failed')
  }
}

export const api = new ApiClient()
