import { mapName, mapRule } from '@/lib/maps'
import { aiName, networkLabel } from '@/lib/networks'
import { useState } from 'react'
import { Loader2, Save, Plus, X } from 'lucide-react'
import type { Board } from '@/api/types'
import { t } from '@/i18n'
import { raceProgress } from '@/lib/game'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { SettingsMenu } from './SettingsMenu'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

interface Props {
  board: Board | null
  busy: boolean
  turn?: 'you' | 'ai' | 'over' | null
  hints: boolean
  canHint: boolean
  user?: string
  onHints: (on: boolean) => void
  onHintModel: (name: string) => void
  onSignOut: () => void
  onNewGame: () => void
  onQuit: () => void
  onSave: () => void
}

function RaceMeter({ board }: { board: Board }) {
  const race = raceProgress(board.players)
  const leader = board.players.find((p) => p.idx === race.leader)
  const p = { appeal: race.appeal, conservation: race.conservation, remaining: race.remaining }
  const detail = race.remaining === 0
    ? leader?.you
      ? t('topBar.crossedYou', 'You have crossed — appeal {appeal}, conservation {conservation}.', p)
      : t('topBar.crossedAi', '{name} has crossed — appeal {appeal}, conservation {conservation}.', { ...p, name: aiName() })
    : race.tied
      ? t('topBar.tied', 'Level on the score. Appeal {appeal}, conservation {conservation}; the markers cross in {remaining}.', p)
      : leader?.you
        ? t('topBar.leaderYou', 'You lead with appeal {appeal} and conservation {conservation}. The markers cross in {remaining}.', p)
        : t('topBar.leaderAi', '{name} leads with appeal {appeal} and conservation {conservation}. The markers cross in {remaining}.', { ...p, name: aiName() })
  return (
    <Tooltip>
      <TooltipTrigger
        render={<span />}
        className="flex items-center gap-2"
        aria-label={t('topBar.gameProgressAria', 'Game {percent} percent. {detail}', { percent: race.percent, detail })}
      >
        {t('topBar.gameProgress', 'game')}
        <span className="relative h-2 w-24 overflow-hidden rounded-full bg-slate-200" aria-hidden>
          <span className="absolute inset-y-0 left-0 rounded-full bg-slate-700 transition-all" style={{ width: `${race.percent}%` }} />
        </span>
        <span className="font-medium text-foreground tabular-nums">{race.percent}%</span>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-64">
        {t('topBar.percentToEnd', "{percent}% of the way to the end, from the leader's appeal and conservation. {detail}", { percent: race.percent, detail })}
      </TooltipContent>
    </Tooltip>
  )
}

export function TopBar({ board, busy, turn, hints, canHint, user, onHints, onHintModel, onSignOut, onNewGame, onQuit, onSave }: Props) {
  const [confirmQuit, setConfirmQuit] = useState(false)
  const brk = board?.break
  return (
    <header className="flex flex-wrap items-center gap-x-5 gap-y-2 shrink-0 border-b bg-white px-4 py-1.5">
      <h1 className="text-base font-semibold tracking-tight">Ark Nova AI</h1>
      {board && (
        <>
          <div className="scroll-area flex max-w-full min-w-0 items-center gap-4 overflow-x-auto text-xs whitespace-nowrap text-muted-foreground">
            <RaceMeter board={board} />
            <span>
              {t('topBar.versusLabel', 'vs')} <span className="font-medium text-foreground">{networkLabel(board.ai_name)}</span>
            </span>
            <Tooltip>
              <TooltipTrigger render={<span />} className="cursor-help font-medium text-violet-700">
                {mapName(board.map)}
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-64">
                {mapRule(board.map)}
              </TooltipContent>
            </Tooltip>
            <span>
              {t('topBar.seed', 'seed')} <span className="font-medium text-foreground tabular-nums">{board.seed}</span>
            </span>
            {brk && (
              <span className="flex items-center gap-2" title={t('topBar.breakTrack', 'Break track')}>
                {t('topBar.break', 'break')}
                <span className="relative h-2 w-24 overflow-hidden rounded-full bg-muted">
                  <span
                    className="absolute inset-y-0 left-0 rounded-full bg-amber-500 transition-all"
                    style={{ width: `${Math.min(100, (brk.pos / Math.max(1, brk.max)) * 100)}%` }}
                  />
                </span>
                <span className="font-medium text-foreground tabular-nums">
                  {brk.pos}/{brk.max}
                </span>
              </span>
            )}
            <span>
              {t('topBar.deck', 'deck')} <span className="font-medium text-foreground tabular-nums">{board.deck}</span>
            </span>
            {board.discard !== undefined && (
              <span>
                {t('topBar.discard', 'discard')} <span className="font-medium text-foreground tabular-nums">{board.discard}</span>
              </span>
            )}
          </div>
        </>
      )}
      <div className="ml-auto flex items-center gap-3">
        {turn && (
          <span
            className={
              'rounded-full px-3 py-0.5 text-xs font-semibold ' +
              (turn === 'you' ? 'bg-sky-500 text-white' : turn === 'ai' ? 'animate-pulse bg-orange-500 text-white' : 'bg-slate-300 text-slate-800')
            }
          >
            {turn === 'you' ? t('app.yourTurn', 'Your turn') : turn === 'ai' ? t('topBar.aiTurn', "{name}'s turn", { name: aiName() }) : t('topBar.gameOver', 'Game over')}
          </span>
        )}
        {busy && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label={t('topBar.working', 'Working')} />}
        {board?.can_save !== false && (
          <Button variant="outline" size="sm" onClick={onSave} disabled={busy || !board}>
            <Save /> {t('topBar.save', 'Save')}
          </Button>
        )}
        <Button size="sm" onClick={onNewGame} disabled={busy}>
          <Plus /> {t('topBar.newGame', 'New game')}
        </Button>
        <Button variant="outline" size="sm" onClick={() => setConfirmQuit(true)} disabled={busy || !board}>
          <X /> {t('topBar.quit', 'Quit')}
        </Button>
        <Dialog open={confirmQuit} onOpenChange={setConfirmQuit}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('topBar.quitTitle', 'Quit this game?')}</DialogTitle>
              <DialogDescription>{t('topBar.quitText', 'The game is deleted and cannot be resumed, and you are signed out. Your place goes to the next player.')}</DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setConfirmQuit(false)}>
                {t('common.cancel', 'Cancel')}
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  setConfirmQuit(false)
                  onQuit()
                }}
              >
                {t('topBar.quitConfirm', 'Quit game')}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        <SettingsMenu hints={hints} canHint={canHint} hintModel={board?.hint_model} map={board?.map} user={user} onHints={onHints} onHintModel={onHintModel} onSignOut={onSignOut} />
      </div>
    </header>
  )
}
