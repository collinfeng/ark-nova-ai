import { Loader2 } from 'lucide-react'
import { t } from '@/i18n'
import { Button } from '@/components/ui/button'

/** Shown while the server is full: the page asks again by itself and goes on when a place is free.
 *  Position 0: the line is full as well, so nothing is held; the player tries again later. */
export function QueuePage({ position, onRetry, onSignOut }: { position: number; onRetry: () => void; onSignOut: () => void }) {
  const full = position === 0
  return (
    <div className="grid min-h-screen place-items-center bg-slate-50 px-4">
      <div className="w-full max-w-sm space-y-4 rounded-2xl border bg-white p-6 text-center shadow-sm">
        {!full && <Loader2 className="mx-auto size-8 animate-spin text-sky-600" />}
        <h1 className="text-xl font-semibold tracking-tight">{t('queue.title', 'The server is full')}</h1>
        <p className="text-sm text-muted-foreground">
          {full
            ? t('queue.full', 'The waiting line is full too. Please try again in a few minutes.')
            : position <= 1
            ? t('queue.next', 'You are next. The game opens by itself as soon as a place is free.')
            : t('queue.ahead', '{n} players are ahead of you. The game opens by itself when it is your turn.', { n: position - 1 })}
        </p>
        <div className="flex justify-center gap-2">
          {full && (
            <Button size="sm" onClick={onRetry}>
              {t('queue.retry', 'Try again')}
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onSignOut}>
            {t('login.signOut', 'Sign out')}
          </Button>
        </div>
      </div>
    </div>
  )
}
