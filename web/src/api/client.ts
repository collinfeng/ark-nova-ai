import { getLang, t } from '@/i18n'
import type { Board, Checkpoints, NewGameParams } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** The server is full: this browser is waiting, `position` is its place in the line (1 = next; 0 = the line is full too). */
export class QueueError extends ApiError {
  position: number
  constructor(position: number) {
    super(503, 'The server is full')
    this.position = position
  }
}

/** The server's error texts are English; the ones the board can cause are shown in its language. */
function serverError(detail: string): string {
  switch (detail) {
    case 'not your decision':
      return t('errors.notYourDecision', detail)
    case 'your turn is not over':
      return t('errors.yourTurnNotOver', detail)
    case 'nothing to undo':
      return t('errors.nothingToUndo', detail)
    case 'nothing to redo':
      return t('errors.nothingToRedo', detail)
    case 'no such option':
      return t('errors.noSuchOption', detail)
    case 'saving is not allowed for this account':
      return t('errors.savingNotAllowed', 'Saving is not available for this account.')
    case 'wrong id or password':
      return t('login.wrong', 'Wrong id or password.')
    case 'no decision to take back in this turn':
      return t('errors.noGameToRestart', detail)
    default:
      return detail
  }
}

const TOKEN_KEY = 'arknova.token'
const SLOT_KEY = 'arknova.slot'

/** Names this browser's game on the server: people sharing one account each keep their own game. */
function getSlot(): string {
  try {
    let slot = localStorage.getItem(SLOT_KEY)
    if (!slot) {
      slot = Array.from(crypto.getRandomValues(new Uint8Array(12)), (b) => b.toString(16).padStart(2, '0')).join('')
      localStorage.setItem(SLOT_KEY, slot)
    }
    return slot
  } catch {
    return 'main'
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* not kept: the login lasts until reload */
  }
}

/** Sent when the server no longer accepts the login (expired token, account gone); the board shows the login page. */
export const SIGNED_OUT = 'arknova:signedout'

export function signOut() {
  setToken(null)
  window.dispatchEvent(new Event(SIGNED_OUT))
}

/** API calls are relative to the page ("api/state"), so the board also works under a path such as /ark-nova-ai/. */
const rel = (path: string) => path.replace(/^\//, '')

async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  let res: Response
  const token = getToken()
  try {
    res = await fetch(rel(path), {
      method,
      headers: {
        'X-Lang': getLang(),
        'X-Slot': getSlot(),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, t('errors.cannotReachGameServer', 'Cannot reach the game server (is it running on port 8765?)'))
  }
  if (res.status === 401 && path !== '/api/login' && path !== '/api/guest') {
    signOut()
    throw new ApiError(401, t('login.signedOut', 'Please sign in again.'))
  }
  if (res.status === 503) {
    const j = (await res.json().catch(() => ({}))) as { detail?: { queued?: number; full?: boolean } }
    if (j.detail?.full) throw new QueueError(0)
    if (typeof j.detail?.queued === 'number') throw new QueueError(j.detail.queued)
  }
  if (!res.ok) {
    let message = t('errors.serverStatus', 'Server returned {status} {text}', { status: res.status, text: res.statusText })
    try {
      const j = (await res.json()) as { detail?: unknown }
      if (typeof j.detail === 'string') message = serverError(j.detail)
    } catch {
      /* keep the status text */
    }
    throw new ApiError(res.status, message)
  }
  return (await res.json()) as T
}

export interface Session {
  token: string
  user: string
  hints: boolean
}

export const api = {
  /** True when the server signs this browser in by itself (local server with "skip_login" in its settings). */
  autoSignedIn: async () => {
    try {
      return (await fetch(rel('/api/me'), { headers: { 'X-Slot': getSlot() } })).ok
    } catch {
      return false
    }
  },
  login: async (user: string, password: string) => {
    const session = await request<Session>('/api/login', 'POST', { user, password })
    setToken(session.token)
    return session
  },
  /** Whether the login page offers "Play as a guest". */
  guestOpen: async () => (await request<{ open: boolean }>('/api/guest')).open,
  guest: async () => {
    const session = await request<Session>('/api/guest', 'POST')
    setToken(session.token)
    return session
  },
  state: () => request<Board>('/api/state'),
  newGame: (params: NewGameParams) => request<Board>('/api/new', 'POST', params),
  move: (index: number) => request<Board>('/api/move', 'POST', { index }),
  endTurn: () => request<Board>('/api/end_turn', 'POST'),
  undo: () => request<Board>('/api/undo', 'POST'),
  redo: () => request<Board>('/api/redo', 'POST'),
  restartTurn: () => request<Board>('/api/restart_turn', 'POST'),
  save: () => request<{ path: string }>('/api/save', 'POST'),
  quit: () => request<{ ok: boolean }>('/api/quit', 'POST'),
  setHintModel: (name: string) => request<Board>('/api/hint_model', 'POST', { name }),
  checkpoints: () => request<Checkpoints>('/api/checkpoints'),
}
