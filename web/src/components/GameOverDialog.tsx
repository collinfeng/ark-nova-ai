import { aiName, networkLabel } from '@/lib/networks'
import { Trophy } from 'lucide-react'
import type { Board } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

interface Props {
  board: Board
  open: boolean
  onClose: () => void
  onNewGame: () => void
}

export function GameOverDialog({ board, open, onClose, onNewGame }: Props) {
  const scores = board.scores ?? board.players.map((p) => p.points)
  const winners = board.winners ?? []
  const youWon = winners.includes(board.human)
  const tie = winners.length > 1
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base">
            <Trophy className="size-5 text-amber-500" />
            {tie ? t('gameOver.titleDraw', 'Draw') : youWon ? t('gameOver.titleYouWin', 'You win') : t('gameOver.titleAiWins', '{name} wins', { name: aiName() })}
          </DialogTitle>
          <DialogDescription>{t('gameOver.finalScores', 'Final scores after the last turn.')}</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3">
          {board.players.map((p) => (
            <div
              key={p.idx}
              className={cn(
                'rounded-lg border p-3 text-center',
                winners.includes(p.idx) ? 'border-amber-400 bg-amber-50' : 'bg-muted/40',
              )}
            >
              <div className="text-xs text-muted-foreground">{p.you ? t('playerPanel.you', 'You') : networkLabel(board.ai_name)}</div>
              <div className="text-3xl font-semibold tabular-nums">{scores[p.idx]}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">
                {t('gameOver.appealConservation', 'appeal {appeal} / conservation {conservation}', { appeal: p.appeal, conservation: p.conservation })}
              </div>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('gameOver.lookAtBoard', 'Look at the board')}
          </Button>
          <Button onClick={onNewGame}>{t('gameOver.newGame', 'New game')}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
