import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { Card, Player } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { ScaledCard } from './ScaledCard'

const SCALE = 0.6
const FOLD_KEY = 'ark.playedFolded'

function loadFolded() {
  try {
    return localStorage.getItem(FOLD_KEY) === '1'
  } catch {
    return false
  }
}

/** A player's played cards in one row that scrolls sideways: animals, then sponsors, then anything else. */
export function ZooCards({ p, title }: { p: Player; title: string }) {
  const [folded, setFolded] = useState(loadFolded)
  const toggle = () =>
    setFolded((v) => {
      try {
        localStorage.setItem(FOLD_KEY, v ? '0' : '1')
      } catch {
        /* per-browser convenience only */
      }
      return !v
    })
  const cards = p.zoo_cards
  const animals = cards.filter((c) => c.type === 'animal')
  const sponsors = cards.filter((c) => c.type === 'sponsor')
  const other = cards.filter((c) => c.type !== 'animal' && c.type !== 'sponsor')
  const groups: [string, Card[]][] = [
    [t('played.animals', 'Animals'), animals],
    [t('played.sponsors', 'Sponsors'), sponsors],
    [t('played.other', 'Other'), other],
  ]
  return (
    <div className="flex flex-col gap-1">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs">
        <button type="button" onClick={toggle} className="flex items-center gap-0.5 text-sm font-semibold hover:text-sky-800" aria-expanded={!folded}>
          {folded ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
          {title}
        </button>
        <span className="text-muted-foreground">{t('played.counts', '{animals} animals · {sponsors} sponsors', { animals: animals.length, sponsors: sponsors.length })}</span>
        <span className="text-muted-foreground" title={t('played.bySizeTip', 'Played animals by size, as some final scoring cards count them')}>
          {t('played.bySize', 'Animals by size: ≤2: {small} · 3: {mid} · 4+: {large}', {
            small: animals.filter((c) => (c.size ?? 0) <= 2).length,
            mid: animals.filter((c) => c.size === 3).length,
            large: animals.filter((c) => (c.size ?? 0) >= 4).length,
          })}
        </span>
        <span className="text-muted-foreground">{t('played.projectsSupported', 'Projects supported: {count}', { count: p.projects_supported })}</span>
      </div>
      {!folded && (
        <div className="scroll-area flex items-start gap-1.5 overflow-x-auto pb-1.5">
          {cards.length === 0 && <div className="py-3 text-xs text-muted-foreground">{t('played.noneYet', 'none yet')}</div>}
          {groups
            .filter(([, list]) => list.length > 0)
            .map(([label, list], gi) => (
              <div key={label} className={cn('flex shrink-0 items-start gap-1.5', gi > 0 && 'border-l pl-1.5')}>
                <span className="w-3 shrink-0 text-[10px] font-semibold text-muted-foreground [writing-mode:vertical-rl]">{label}</span>
                {list.map((c) => (
                  <ScaledCard key={c.id} card={c} scale={SCALE} />
                ))}
              </div>
            ))}
        </div>
      )}
    </div>
  )
}
