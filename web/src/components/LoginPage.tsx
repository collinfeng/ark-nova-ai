import { useEffect, useState, type FormEvent } from 'react'
import { Loader2, LogIn, Play } from 'lucide-react'
import { api } from '@/api/client'
import { LANGS, t } from '@/i18n'
import { useSettings } from '@/lib/settings'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

const FIELD = 'h-9 w-full rounded-lg border bg-white px-3 text-sm outline-none focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/30'

function Credit({ href, children }: { href: string; children: string }) {
  return (
    <a href={href} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-foreground">
      {children}
    </a>
  )
}

/** The first page: play as a guest, or sign in with an id and password. Each browser has its own game. */
export function LoginPage({ onSignedIn }: { onSignedIn: () => void }) {
  const { lang, setLang } = useSettings()
  const [user, setUser] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<'guest' | 'login' | null>(null)
  // Guest play is normally open: show the button at once rather than pop it in when the server answers.
  const [guestOpen, setGuestOpen] = useState(true)
  useEffect(() => {
    api.guestOpen().then(setGuestOpen, () => setGuestOpen(false))
  }, [])

  const enter = async (which: 'guest' | 'login', signIn: () => Promise<unknown>) => {
    if (busy) return
    setBusy(which)
    setError(null)
    try {
      await signIn()
      onSignedIn()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }
  const submit = (e: FormEvent) => {
    e.preventDefault()
    void enter('login', () => api.login(user.trim(), password))
  }

  return (
    <div className="relative flex min-h-screen flex-col items-center bg-slate-50 px-4 py-6">
      <div className="flex w-full flex-1 items-center justify-center">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl border bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Ark Nova AI</h1>
            <p className="text-sm text-muted-foreground">
              {guestOpen ? t('login.subtitleGuest', 'Play against the AI') : t('login.subtitle', 'Sign in to your game')}
            </p>
          </div>
          <div className="inline-flex shrink-0 rounded-lg bg-muted p-0.5 text-xs whitespace-nowrap">
            {LANGS.map((l) => (
              <button
                key={l.code}
                type="button"
                onClick={() => setLang(l.code)}
                className={cn('rounded-md px-2 py-0.5 font-medium', lang === l.code ? 'bg-white shadow-sm' : 'text-muted-foreground hover:text-foreground')}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
        {guestOpen && (
          <>
            <Button type="button" className="w-full" disabled={busy !== null} onClick={() => void enter('guest', api.guest)}>
              {busy === 'guest' ? <Loader2 className="animate-spin" /> : <Play />} {t('login.guest', 'Play as a guest')}
            </Button>
            <div className="flex items-center gap-3 text-xs text-muted-foreground">
              <span className="h-px flex-1 bg-slate-200" />
              {t('login.orSignIn', 'or sign in')}
              <span className="h-px flex-1 bg-slate-200" />
            </div>
          </>
        )}
        <label className="block space-y-1 text-sm font-medium">
          {t('login.id', 'Id')}
          <input className={FIELD} value={user} onChange={(e) => setUser(e.target.value)} autoComplete="username" autoCapitalize="none" autoCorrect="off" spellCheck={false} />
        </label>
        <label className="block space-y-1 text-sm font-medium">
          {t('login.password', 'Password')}
          <input className={FIELD} type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
        </label>
        {error && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm text-red-800">
            {error}
          </p>
        )}
        <Button type="submit" variant={guestOpen ? 'outline' : 'default'} className="w-full" disabled={busy !== null || !user.trim() || !password}>
          {busy === 'login' ? <Loader2 className="animate-spin" /> : <LogIn />} {t('login.signIn', 'Sign in')}
        </Button>
      </form>
      </div>
      <footer className="mt-8 w-full max-w-5xl space-y-1.5 border-t border-slate-200 pt-4 text-center text-xs text-muted-foreground">
        <p>
          {t('login.creditDesign', 'Ark Nova is designed by Mathias Wigge and published by')} <Credit href="https://www.feuerland-spiele.de/spiele/arche-nova/">Feuerland Spiele</Credit>.{' '}
          {t('login.creditPlay', 'Play the official online version on')} <Credit href="https://boardgamearena.com/gamepanel?game=arknova">Board Game Arena</Credit>,{' '}
          {t('login.creditRead', 'or read more on')} <Credit href="https://boardgamegeek.com/boardgame/342942/ark-nova">BoardGameGeek</Credit>.
        </p>
        <p>
          {t('login.disclaimer', 'Unofficial fan project, not affiliated with the publishers of Ark Nova.')}
          <span className="mx-2">·</span>
          <Credit href="https://github.com/collinfeng/ark-nova-ai">{t('login.source', 'Source code on GitHub')}</Credit>
        </p>
      </footer>
    </div>
  )
}
