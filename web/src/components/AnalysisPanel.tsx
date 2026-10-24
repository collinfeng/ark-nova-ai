import { AlertTriangle, Bot } from 'lucide-react'
import type { ActivityTurn, AiMove, Board, FeedLine, MoveRecord } from '@/api/types'
import { t } from '@/i18n'
import { pct } from '@/lib/game'
import { networkLabel } from '@/lib/networks'
import { cn } from '@/lib/utils'
import { CardChip } from '@/components/CardTile'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { useSettings } from '@/lib/settings'

const SURPRISE = 0.1

function AiFeedDetails({ lines, actor }: { lines: FeedLine[]; actor: ActivityTurn['actor'] }) {
  if (lines.length === 0) return null
  return (
    <ul className={cn('mt-1 space-y-0.5 border-t pt-1', actor === 'you' ? 'border-sky-100' : 'border-orange-100')}>
      {lines.map((line, i) => (
        <li key={i} className={cn('flex min-w-0 items-start gap-1.5 text-[10px] leading-snug', 'note' in line && line.note === 'break' && 'my-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1.5 text-[11px]')}>
          <span className={cn('mt-1 size-1.5 shrink-0 rounded-full', 'amount' in line ? (line.amount < 0 ? 'bg-rose-500' : 'bg-emerald-500') : 'bg-amber-500')} />
          <span className="min-w-0 flex-1">
            {'note' in line && line.note === 'break' && <span className="mb-0.5 block text-[9px] font-bold text-amber-700">{t('analysis.keyEvent', 'Key event')}</span>}
            <span className={cn('font-medium', 'note' in line ? 'text-amber-950' : 'text-slate-800')}>
              {'amount' in line && (line.amount < 0 ? '−' : '+')}{line.text}
            </span>
            {'why' in line && line.why && <span className="ml-1 text-muted-foreground">· {line.why}</span>}
          </span>
        </li>
      ))}
    </ul>
  )
}

/** An on-demand preview only: never opens automatically or dismisses on a timer. */
export function AiTurnDetails({ board }: { board: Board }) {
  const latest = board.ai_history?.at(-1)
  return <ActivityTurnDetails turn={{ turn: latest?.turn ?? 0, actor: 'ai', moves: latest?.moves ?? board.ai_moves }} />
}

function ActivityTurnDetails({ turn }: { turn: ActivityTurn }) {
  const { moves, actor } = turn
  return (
    <section>
      <div className={cn('border-b px-3 py-2 text-xs font-semibold', actor === 'you' ? 'bg-sky-50 text-sky-950' : 'bg-orange-50 text-orange-950')}>
        {actor === 'you' ? t('analysis.yourTurnNumber', 'Your turn {turn}', { turn: turn.turn }) : t('analysis.turnNumber', 'AI turn {turn}', { turn: turn.turn })}
      </div>
      <div className="scroll-area max-h-[min(32rem,70vh)] overflow-y-auto p-2">
        {moves.length ? (
          <ol className="space-y-1.5">{moves.map((move, i) => <AiMoveRow key={i} move={move} index={i} actor={actor} />)}</ol>
        ) : <p className="p-2 text-xs text-muted-foreground">{t('analysis.nothingYet', 'Nothing yet.')}</p>}
      </div>
    </section>
  )
}

function AiMoveRow({ move, index, actor = 'ai' }: { move: AiMove; index: number; actor?: ActivityTurn['actor'] }) {
  return (
    <li className={cn('rounded-lg border px-2.5 py-2 text-xs', actor === 'you' ? 'border-sky-100 bg-sky-50/45' : 'border-orange-100 bg-orange-50/45')}>
      <div className="flex items-start gap-2">
        <span className={cn('grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold', actor === 'you' ? 'bg-sky-200 text-sky-950' : 'bg-orange-200 text-orange-950')}>{index + 1}</span>
        <div className="min-w-0 flex-1">
          {move.kind !== 'turn' && <div className={cn('text-[10px]', actor === 'you' ? 'text-sky-700/80' : 'text-orange-700/80')}>{move.title ?? move.kind.replace(/_/g, ' ')}</div>}
          <div className="font-medium text-slate-900">{move.label}</div>
          {!!move.cards?.length && (
            <div className="mt-1 flex flex-wrap gap-1">
              {move.cards.map((c) => (
                <CardChip key={c.id} id={String(c.id)} card={c} />
              ))}
            </div>
          )}
        </div>
        {move.prob !== null && (
          <span
            className="shrink-0 rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-sky-800 tabular-nums"
            title={t('analysis.aiChoiceOdds', 'AI chose this move with {chance} probability', { chance: pct(move.prob) })}
          >
            {t('analysis.choiceProbability', 'Choice probability')} {pct(move.prob)}
          </span>
        )}
      </div>
      {move.feed && <AiFeedDetails lines={move.feed} actor={actor} />}
    </li>
  )
}

/** Both sides' actions, grouped by turn with the newest first. */
export function AiPlayedBox({ board, handedOver }: { board: Board; handedOver?: boolean }) {
  const { activityPreview } = useSettings()
  const aiHistory = board.ai_history?.length
    ? board.ai_history
    : board.ai_moves.length
      ? [{ turn: 1, moves: board.ai_moves }]
      : []
  const history: ActivityTurn[] = board.activity_history ?? aiHistory.map((turn) => ({ ...turn, actor: 'ai' }))
  const moveCount = history.reduce((total, turn) => total + turn.moves.length, 0)
  return (
    <section className="p-2">
      <div className="mb-2 flex items-center gap-1.5 rounded-lg bg-slate-50 px-2.5 py-2 text-xs font-semibold text-slate-900">
        <Bot className="size-3.5" /> {t('analysis.activityHistoryTitle', 'Activity history')}
        {history.length > 0 && (
          <span className="ml-auto font-normal text-slate-500">
            {t('analysis.historyCount', '{turns} turns · {moves} moves', { turns: history.length, moves: moveCount })}
          </span>
        )}
      </div>
      {history.some((turn) => turn.moves.some((move) => move.prob !== null)) && (
        <p className="mb-2 px-1 text-[10px] leading-relaxed text-muted-foreground">
          {t('analysis.choiceProbabilityHelp', 'Percentages show the probability the AI assigned to that action among the available choices at the time.')}
        </p>
      )}
      {history.length === 0 ? (
        <p className="rounded-lg border border-dashed px-3 py-4 text-center text-[11px] text-muted-foreground">{t('analysis.nothingYet', 'Nothing yet.')}</p>
      ) : (
        <div className="space-y-2" aria-label={t('analysis.activityHistoryTitle', 'Activity history')}>
          {[...history].reverse().map((turn, turnIndex) => (
            <HoverCard key={`${turn.actor}-${turn.turn}-${turnIndex}-${activityPreview}`} open={activityPreview ? undefined : false}>
            <HoverCardTrigger delay={250} closeDelay={200} render={<section />} tabIndex={activityPreview ? 0 : undefined}
              className={cn('block rounded-lg border bg-white text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-sky-400', turn.actor === 'you' ? 'border-sky-100 hover:border-sky-300' : 'border-orange-100 hover:border-orange-300')}>
              <div className={cn('flex items-center gap-2 border-b px-2.5 py-1.5', turn.actor === 'you' ? 'bg-sky-50/70' : 'bg-orange-50/70')}>
                <span className={cn('text-[11px] font-semibold', turn.actor === 'you' ? 'text-sky-950' : 'text-orange-950')}>
                  {turn.actor === 'you' ? t('analysis.yourTurnNumber', 'Your turn {turn}', { turn: turn.turn }) : t('analysis.turnNumber', 'AI turn {turn}', { turn: turn.turn })}
                </span>
                {turnIndex === 0 && handedOver && turn.actor === 'ai' && <span className="rounded-full bg-orange-500 px-1.5 py-0.5 text-[9px] font-bold text-white">{t('analysis.latest', 'Latest')}</span>}
                <span className={cn('ml-auto text-[10px]', turn.actor === 'you' ? 'text-sky-800/70' : 'text-orange-800/70')}>{t('analysis.moveCount', '{count} moves', { count: turn.moves.length })}</span>
              </div>
              <ol className="space-y-1.5 p-1.5">
                {turn.moves.map((move, i) => <AiMoveRow key={i} move={move} index={i} actor={turn.actor} />)}
              </ol>
            </HoverCardTrigger>
            <HoverCardContent side="right" align="start" className="w-[360px] max-w-[calc(100vw-2rem)] p-0">
              <ActivityTurnDetails turn={turn} />
            </HoverCardContent>
            </HoverCard>
          ))}
        </div>
      )}
    </section>
  )
}

/** Your moves are judged by whichever hint model was on at the time: summarise each model on its own. */
function modelSummary(recs: MoveRecord[]) {
  const agree = recs.filter((r) => r.rank === 1).length
  const percent = Math.round((agree / recs.length) * 100)
  if (recs.some((r) => r.rule)) {
    return t('analysis.ruleSummary', '{total} moves: you matched the rule policy {agree} times ({percent}%).', { total: recs.length, agree, percent })
  }
  const surprising = recs.filter((r) => r.prob < SURPRISE).length
  return t('analysis.summary', '{total} moves: top choice of the AI {agree} times ({percent}%), {surprising} below {threshold}.', {
    total: recs.length,
    agree,
    percent,
    surprising,
    threshold: pct(SURPRISE),
  })
}

export function AnalysisPanel({ board }: { board: Board }) {
  const recs = board.records
  const modelOf = (r: MoveRecord) => r.hint ?? ''
  const models = [...new Set(recs.map(modelOf))]
  const several = models.length > 1
  return (
    <div className="space-y-2 p-2">
      {recs.length > 0 ? (
        <div className="space-y-0.5 text-xs text-muted-foreground">
          {models.map((m) => (
            <div key={m}>
              {several && m && <b className="font-semibold text-foreground">{networkLabel(m)}: </b>}
              {modelSummary(recs.filter((r) => modelOf(r) === m))}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{t('analysis.noComparisonYet', "Your moves will be compared with the AI's preferences here.")}</p>
      )}
      <ol className="space-y-1.5">
        {[...recs].reverse().map((r) => {
          const odd = !r.rule && r.prob < SURPRISE // a rule policy's other moves are 0% by definition: not worth a warning
          return (
            <li key={r.move} className={cn('rounded-lg border p-2 text-xs', odd ? 'border-amber-300 bg-amber-50' : 'bg-white')}>
              <div className="flex items-start justify-between gap-2">
                <span className="font-medium">
                  <span className="text-muted-foreground">#{r.move + 1}</span> {r.chose}
                </span>
                <span className={cn('shrink-0 tabular-nums', odd ? 'font-semibold text-amber-800' : 'text-muted-foreground')}>
                  {odd && <AlertTriangle className="mr-0.5 inline size-3" />}
                  {t('analysis.rankOf', '{prob} / rank {rank} of {total}', { prob: pct(r.prob), rank: r.rank, total: r.options })}
                </span>
              </div>
              {r.rank !== 1 && (
                <div className="mt-0.5 text-muted-foreground">
                  {r.rule ? t('analysis.rulePreferred', 'Rule policy chose:') : t('analysis.aiPreferred', 'AI preferred:')} <span className="text-foreground">{r.ai_best}</span>
                  {!r.rule && ` (${pct(r.ai_best_prob)})`}
                </div>
              )}
              {several && r.hint && <div className="mt-0.5 text-[10px] text-muted-foreground/80">{networkLabel(r.hint)}</div>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export function LogPanel({ board }: { board: Board }) {
  return (
    <ol className="space-y-0.5 p-2 font-mono text-[11px] leading-snug">
      {[...board.log].reverse().map((l, i) => (
        <li key={i} className={cn('rounded px-1 py-0.5', l.startsWith(`P${board.human}`) ? 'bg-sky-50' : l.startsWith('P') ? 'bg-orange-50' : '')}>
          {l}
        </li>
      ))}
    </ol>
  )
}
