import { aiName } from '@/lib/networks'
import { useEffect, useState } from 'react'
import { AlertTriangle, ArrowRight, Flag, Redo2, RotateCcw, Undo2 } from 'lucide-react'
import type { Board } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

interface Props {
  board: Board
  busy: boolean
  /** Picks on the page not yet confirmed: Undo clears them first, without leaving the turn. */
  picking: boolean
  onUndo: () => void
  onRedo: () => void
  onRestart: () => void
  onEndTurn: () => void
}

/**
 * Undo, redo, restart the turn and end the turn: the top row of the action panel. An Undo that would
 * leave the current turn (and take back the AI's) needs a second click: the first one turns the button
 * amber and shows a warning under the row, which goes away by itself after a few seconds, on Cancel, or
 * as soon as anything else changes the game.
 */
export function TurnControls({ board, busy, picking, onUndo, onRedo, onRestart, onEndTurn }: Props) {
  const done = board.phase === 'end_turn'
  const sig = `${board.seed}:${board.records.length}:${board.phase}:${board.can_redo}`
  const [armedSig, setArmedSig] = useState<string | null>(null)
  const armed = armedSig === sig && board.undo_leaves_turn
  useEffect(() => {
    if (armedSig === null) return
    const timer = window.setTimeout(() => setArmedSig(null), 6000)
    return () => window.clearTimeout(timer)
  }, [armedSig])
  const undo = () => {
    if (board.undo_leaves_turn && !armed && !picking) setArmedSig(sig)
    else {
      setArmedSig(null)
      onUndo()
    }
  }
  const moves = board.ai_moves.length
  // A break happened in this turn: ending the turn is the moment to take it in, so the button says so
  const breakTurn = done && (board.turn_feed ?? []).some((l) => 'note' in l && l.note === 'break')
  return (
    <>
    <div className={cn('flex shrink-0 flex-wrap items-center gap-1.5 border-b px-2 py-1.5', done && 'bg-sky-50')}>
      <Button
        variant="outline"
        size="sm"
        onClick={undo}
        disabled={busy || (!board.can_undo && !picking)}
        className={cn(armed && 'border-amber-400 bg-amber-100 text-amber-950 hover:bg-amber-200')}
        title={picking ? t('turnControls.undoPicksTitle', 'Clear your picks on this decision') : board.undo_leaves_turn ? t('turnControls.undoLeavesTitle', "Back into your previous turn (also takes back {name}'s turn)", { name: aiName() }) : t('turnControls.undoTitle', 'Back to your previous decision')}
      >
        {armed ? <AlertTriangle /> : <Undo2 />} {armed ? t('turnControls.clickAgain', 'Click again to go back') : t('turnControls.undo', 'Undo')}
      </Button>
      <Button variant="outline" size="sm" onClick={onRedo} disabled={busy || !board.can_redo} title={t('turnControls.redoTitle', 'Put back what Undo took')}>
        <Redo2 /> {t('turnControls.redo', 'Redo')}
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onRestart}
        disabled={busy || !board.can_restart_turn}
        title={t('turnControls.restartTitle', 'Back to the start of this turn (Redo steps forward again)')}
      >
        <RotateCcw /> {t('turnControls.restartTurn', 'Restart turn')}
      </Button>
      <span className="ml-auto truncate px-2 text-xs text-muted-foreground">
        {!done && !board.over && t('turnControls.finishTurn', 'Finish your turn to hand over')}
      </span>
      <Button
        size="sm"
        onClick={onEndTurn}
        disabled={busy || !done}
        className={cn(breakTurn && 'bg-amber-500 text-amber-950 hover:bg-amber-400')}
        title={done ? t('turnControls.endTitle', 'Let {name} play its turn', { name: aiName() }) : t('turnControls.endDisabled', 'Your turn is not over yet')}>
        {breakTurn && <Flag />}
        {breakTurn ? t('turnControls.breakEndTurn', 'Break: end turn') : t('turnControls.endTurn', 'End turn')} <ArrowRight />
        {done && <kbd className="ml-0.5 rounded bg-white/25 px-1 text-[10px]">Enter</kbd>}
      </Button>
    </div>
    {armed && (
      <div role="alert" className="flex flex-wrap items-center gap-2 border-b border-amber-300 bg-amber-50 px-3 py-1.5 text-sm text-amber-950">
        <AlertTriangle className="size-4 shrink-0 text-amber-600" />
        <span className="min-w-0 flex-1">
          {t(
            'turnControls.warning',
            "Nothing is decided in this turn yet, so Undo reopens your last decision of the previous turn and takes back {name}'s turn{moves}. Redo brings it back.",
            { name: aiName(), moves: moves > 0 ? t('turnControls.warningMoves', moves === 1 ? ' ({count} move)' : ' ({count} moves)', { count: moves }) : '' },
          )}
        </span>
        <Button variant="ghost" size="sm" onClick={() => setArmedSig(null)}>
          {t('common.cancel', 'Cancel')}
        </Button>
      </div>
    )}
    </>
  )
}
