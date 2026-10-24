import type { Board } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { ScaledCard, CARD_W, useMeasure } from './ScaledCard'
import { Reward, Tip } from './TracksPanel'

const GAP = 8

/**
 * The display as on the printed board: six folders in one row, the reputation track under them. Each folder
 * sits over the reputation spaces that bring it into reach, so the markers show at a glance which folders
 * each player can take or play from (paying the folder number in money); the rest only a Snap takes.
 */
export function DisplayPanel({ board }: { board: Board }) {
  const display = board.display
  const [ref, width] = useMeasure<HTMLDivElement>()
  const cols = display.length || 6
  const colW = width ? (width - GAP * (cols - 1)) / cols : 110
  const scale = Math.max(0.45, Math.min(0.9, colW / CARD_W))

  const tracks = board.tracks
  const meIdx = board.players.find((p) => p.you)!.idx
  const you = tracks.players.find((p) => p.idx === meIdx)!
  const ai = tracks.players.find((p) => p.idx !== meIdx)!
  const max = tracks.reputation.max
  const gate = tracks.reputation.gate
  const bonus = new Map(tracks.reputation.stops.map((s) => [s.at, s]))
  // The reputation spaces under each folder: from its reach up to the next folder's.
  const starts = display.map((d, i) => (i === 0 ? Math.min(1, d.reach_reputation ?? 1) : (d.reach_reputation ?? 0)))
  const spaces = display.map((_, i) => {
    const end = i + 1 < starts.length ? starts[i + 1] - 1 : max
    return Array.from({ length: Math.max(0, end - starts[i] + 1) }, (_, k) => starts[i] + k)
  })
  const yourRep = Math.max(1, you.reputation)
  const aiRep = Math.max(1, ai.reputation)

  return (
    <section className="rounded-xl border bg-white p-2 shadow-xs" aria-label={t('tabs.display', 'Display')}>
      <Tip side="top" tip={t('display.titleTip', 'Six folders of cards. The reputation track below shows which folders each player reaches: take those with Cards II, or play them with the upgraded actions for the folder number in money. Further folders: Snap only.')} className="mb-1.5 block w-fit cursor-help text-sm font-semibold">{t('tabs.display', 'Display')}</Tip>
      <div ref={ref} className="grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, columnGap: GAP }}>
        {display.map((d) => (
          <div key={d.folder} className="flex min-w-0 flex-col items-center gap-1">
            <Tip side="top" tip={d.in_reach ? t('display.inReachTip', 'Your reputation reaches this folder: take it with Cards II, or play it with Animals II, Sponsors II or Association II (projects) for {cost} extra money.', { cost: d.folder }) : t('display.snapOnlyTip', 'Out of reach: needs reputation {rep} to take or play. Until then only a Snap (Cards at strength 5, or Cards II at 3+) can take it.', { rep: d.reach_reputation ?? '' })}
              className={cn('cursor-help text-xs font-black tabular-nums', d.in_reach ? 'text-slate-900' : 'text-slate-400')}>
              {d.folder}
            </Tip>
            {d.card ? (
              <ScaledCard card={d.card} status={d.status ?? d.card.status} scale={scale} dim={!d.in_reach} />
            ) : (
              <div className="flex items-center justify-center rounded-lg border border-dashed text-xs text-muted-foreground" style={{ width: CARD_W * scale, height: 236 * scale }}>
                {t('display.emptyFolder', 'empty')}
              </div>
            )}
          </div>
        ))}
        {spaces.map((cells, i) => (
          <div key={`rep-${i}`} className="mt-1.5 flex min-w-0 gap-px" aria-label={t('display.repForFolder', 'Reputation for folder {n}', { n: i + 1 })}>
            {cells.map((n) => {
              const locked = n > gate && !you.cards_ii
              const s = bonus.get(n)
              return (
                <div key={n} className="relative flex min-w-0 flex-1 flex-col items-center">
                <Tip side="bottom" className="w-full cursor-help" tip={<>
                  {s && <span className="font-semibold">{t('display.bonusHere', 'Bonus here: {label} (each player once, on reaching it)', { label: s.label })}</span>}
                  <span>{t('display.trackTip', 'Reputation {n} reaches folders 1–{folder}: take those cards with Cards II, or play them with Animals II, Sponsors II or Association II for the folder number in money. Further folders: Snap only.', { n, folder: i + 1 })}</span>
                  {n > gate && <span className="text-red-700">{t('display.cardsIIGate', 'Past {gate} only with Cards II', { gate })}</span>}
                  <span className="text-[10px] opacity-75">{t('display.trackWho', 'You {you} · AI {ai}', { you: you.reputation, ai: ai.reputation })}</span>
                </>}>
                  <span
                    className={cn(
                      'relative flex h-6 w-full items-center justify-center text-[11px] font-bold tabular-nums',
                      n <= gate ? 'bg-teal-600/85 text-white' : 'bg-rose-400/80 text-white',
                      n === starts[i] && 'rounded-l-md',
                      n === cells[cells.length - 1] && 'rounded-r-md',
                    )}
                  >
                    {n}
                    {n === yourRep && <i className="absolute -top-1 left-1/2 size-2.5 -translate-x-1/2 rounded-full bg-sky-500 ring-2 ring-white" />}
                    {n === aiRep && <i className="absolute -bottom-1 left-1/2 size-2.5 -translate-x-1/2 rounded-full bg-orange-500 ring-2 ring-white" />}
                  </span>
                  </Tip>
                  {s && (
                    <span aria-hidden className={cn('pointer-events-none mt-1 scale-75', locked && 'opacity-50 grayscale')}>
                      <Reward kind={s.kind} />
                    </span>
                  )}
                  {n === gate + 1 && !you.cards_ii && <i aria-hidden className="absolute top-0 h-6 border-l-2 border-dashed border-red-600" style={{ left: -(GAP / 2) - 1 }} />}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </section>
  )
}
