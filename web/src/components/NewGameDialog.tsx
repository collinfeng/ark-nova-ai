import { useEffect, useState } from 'react'
import { api } from '@/api/client'
import type { NewGameParams } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@/components/ui/select'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { mapName, mapRule } from '@/lib/maps'
import { isRuleBased, networkDescription, networkLabel, networkOrder } from '@/lib/networks'

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  onStart: (params: NewGameParams) => void
  busy: boolean
  /** Just signed in: nothing is being discarded, and Cancel carries on with the saved game. */
  first?: boolean
  onSignOut?: () => void
}

export function NewGameDialog({ open, onOpenChange, onStart, busy, first = false, onSignOut }: Props) {
  const [seed, setSeed] = useState('')
  const [human, setHuman] = useState<0 | 1>(0)
  const [checkpoint, setCheckpoint] = useState('')
  const [checkpoints, setCheckpoints] = useState<string[]>([])
  const [note, setNote] = useState<string | null>(null)
  const [maps, setMaps] = useState<string[]>(['map0'])
  const [map, setMap] = useState('map0')
  const [anyMap, setAnyMap] = useState<string[]>([])
  const [mapDefault, setMapDefault] = useState<string | null>(null)
  // Off Map 0 only the opponents that play every map (rule policies and networks trained on all maps).
  const offered = map === 'map0' ? checkpoints : checkpoints.filter((c) => anyMap.includes(c))

  useEffect(() => {
    if (!open) return
    let cancelled = false
    api
      .checkpoints()
      .then((c) => {
        if (cancelled) return
        setCheckpoints([...c.checkpoints].sort((a, b) => networkOrder(a) - networkOrder(b) || a.localeCompare(b)))
        // Easy is the starting choice; the server's own default only when there is no easy network.
        const easy = c.checkpoints.find((x) => x.replace(/\.pt$/, '') === 'run5_13M')
        setCheckpoint((cur) => cur || easy || c.default)
        setNote(c.remote ? t('newGame.networkRunsOn', 'Network runs on {url}', { url: c.remote }) : null)
        if (c.maps?.length) setMaps(c.maps)
        setAnyMap(c.any_map ?? [])
        setMapDefault(c.map_default ?? null)
      })
      .catch((e: unknown) => {
        if (!cancelled) setNote(t('newGame.checkpointLoadFailed', 'Could not load the checkpoint list: {message}', { message: e instanceof Error ? e.message : String(e) }))
      })
    return () => {
      cancelled = true
    }
  }, [open])

  const chooseMap = (m: string) => {
    setMap(m)
    // The chosen opponent may not play the new map: then the strongest one that does.
    if (m !== 'map0' && !anyMap.includes(checkpoint)) setCheckpoint(mapDefault ?? anyMap[0] ?? '')
  }

  const submit = () => {
    const params: NewGameParams = { human, map }
    if (seed.trim() !== '' && Number.isFinite(Number(seed))) params.seed = Math.trunc(Number(seed))
    if (checkpoint) params.checkpoint = checkpoint
    onStart(params)
  }

  return (
    <Dialog open={open} onOpenChange={(o) => (o || !first) && onOpenChange(o)}>
      <DialogContent showCloseButton={!first}>
        <DialogHeader>
          <DialogTitle>{t('newGame.title', 'New game')}</DialogTitle>
          <DialogDescription>
            {first
              ? t('newGame.chooseFirst', 'Choose your opponent, then start.')
              : t('newGame.discardWarning', 'The current game is discarded unless you saved it.')}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <label className="block space-y-1">
            <span className="text-xs font-medium text-muted-foreground">{t('newGame.seed', 'Seed (optional)')}</span>
            <input
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              inputMode="numeric"
              placeholder={t('common.random', 'random')}
              className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </label>
          <div className="space-y-1">
            <span className="text-xs font-medium text-muted-foreground">{t('newGame.youPlay', 'You play')}</span>
            <div className="grid grid-cols-2 gap-2">
              {([0, 1] as const).map((h) => (
                <button
                  key={h}
                  type="button"
                  onClick={() => setHuman(h)}
                  className={cn(
                    'h-8 rounded-lg border text-sm transition',
                    human === h ? 'border-sky-500 bg-sky-50 font-medium text-sky-900' : 'bg-background hover:bg-muted',
                  )}
                >
                  {h === 0 ? t('newGame.first', 'First') : t('newGame.second', 'Second')}
                </button>
              ))}
            </div>
          </div>
          {maps.length > 1 && (
            <div className="space-y-1">
              <span className="text-xs font-medium text-muted-foreground">{t('newGame.map', 'Map')}</span>
              <Select value={map} items={maps.map((value) => ({ value, label: mapName(value) }))} onValueChange={(v) => chooseMap(v ?? 'map0')}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false}>
                  {maps.map((m) => (
                    <SelectItem key={m} value={m}>
                      {mapName(m)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">{mapRule(map)}</p>
            </div>
          )}
          <div className="space-y-1">
            <span className="text-xs font-medium text-muted-foreground">{t('newGame.opponentDifficulty', 'Opponent difficulty')}</span>
            <Select value={checkpoint} items={offered.map((value) => ({ value, label: networkLabel(value) }))} onValueChange={(v) => setCheckpoint(v ?? '')}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder={t('common.default', 'Default')} />
              </SelectTrigger>
              <SelectContent alignItemWithTrigger={false}>
                {[
                  { label: t('newGame.modelsGroup', 'AI models'), items: offered.filter((c) => !isRuleBased(c)) },
                  { label: t('newGame.rulesGroup', 'Rule-based'), items: offered.filter(isRuleBased) },
                ]
                  .filter((g) => g.items.length > 0)
                  .map((g) => (
                    <SelectGroup key={g.label}>
                      <SelectLabel>{g.label}</SelectLabel>
                      {g.items.map((c) => (
                        <SelectItem key={c} value={c}>
                          {networkLabel(c)}
                        </SelectItem>
                      ))}
                    </SelectGroup>
                  ))}
              </SelectContent>
            </Select>
            {networkDescription(checkpoint) && <p className="text-xs text-muted-foreground">{networkDescription(checkpoint)}</p>}
            {map !== 'map0' && <p className="text-xs text-muted-foreground">{t('newGame.otherMapOpponents', 'On this map: Normal and the rule-based opponents. Easy and Hard learned Map 0 only.')}</p>}
            {note && <p className="text-xs text-muted-foreground">{note}</p>}
          </div>
        </div>
        <DialogFooter>
          {first && onSignOut && (
            <Button variant="outline" onClick={onSignOut}>
              {t('login.signOut', 'Sign out')}
            </Button>
          )}
          {!first && (
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              {t('common.cancel', 'Cancel')}
            </Button>
          )}
          <Button onClick={submit} disabled={busy}>
            {t('newGame.start', 'Start')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
