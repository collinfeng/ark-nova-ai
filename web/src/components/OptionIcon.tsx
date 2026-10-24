import type { ReactNode } from 'react'
import {
  ArrowRight,
  Check,
  Gift,
  Layers,
  PawPrint,
  Shield,
  SkipForward,
  Trash2,
  Users,
  X,
} from 'lucide-react'
import { ResourceIcon } from './Resource'
import type { ActionName, Card, Option } from '@/api/types'
import { ACTIONS, ACTION_HEX, buildingStyle, CARD_TYPE_STYLE } from '@/lib/game'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { GameIcon } from './GameIcon'
import { Rep, UniversityChip } from './Glyphs'

function Box({ bg, fg = 'white', children, title }: { bg: string; fg?: string; children: ReactNode; title?: string }) {
  return (
    <span title={title} className="grid size-6 shrink-0 place-items-center rounded-md" style={{ background: bg, color: fg }}>
      {children}
    </span>
  )
}

function Muted({ children }: { children: ReactNode }) {
  return <span className="grid size-6 shrink-0 place-items-center rounded-md border border-dashed text-muted-foreground">{children}</span>
}

/** An action card's colour with its initial, as on the action tiles. */
export function ActionChip({ action }: { action: ActionName }) {
  return (
    <span
      title={ACTIONS[action].label}
      className="inline-flex h-6 shrink-0 items-center rounded-md px-1.5 text-[11px] font-bold text-white"
      style={{ background: ACTION_HEX[action] }}
    >
      {ACTIONS[action].label}
    </span>
  )
}

/** A card by its type colour: animal paw, sponsor, project shield, final scoring. */
function CardMark({ card }: { card: Card }) {
  const t = CARD_TYPE_STYLE[card.type] ?? CARD_TYPE_STYLE.animal
  const inner =
    card.type === 'animal' ? <PawPrint className="size-3.5" /> : card.type === 'project' ? <Shield className="size-3.5" /> : <Layers className="size-3.5" />
  return <Box bg={t.banner} title={t.label}>{inner}</Box>
}

/**
 * The icon in front of a decision option, so every choice reads at a glance: action cards in their
 * colour, continents, universities, reputation, money, buildings by their map colour, cards by type,
 * and muted marks for Skip, Finish and No.
 */
export function OptionIcon({ option, cardsById }: { option: Option; cardsById: Map<string, Card> }) {
  const type = option.type
  const k1 = option.key[1]
  const card = option.cards.length ? cardsById.get(option.cards[0]) : undefined
  const icon = ((): ReactNode => {
    if (option.action && ['act', 'upgrade', 'clever', 'boost', 'repeat', 'multiplier'].includes(type)) return <ActionChip action={option.action} />
    switch (type) {
      case 'partner_zoo':
        return typeof k1 === 'string' ? <GameIcon name={k1} size={24} /> : null
      case 'university':
        return typeof k1 === 'string' ? <UniversityChip id={k1} title={option.label} /> : null
      case 'reputation':
        return <Rep n={Number(/\+(\d+)/.exec(option.label)?.[1] ?? 1)} />
      case 'donate':
        return (
          <span className="inline-flex h-6 items-center gap-0.5 rounded-md border bg-white px-1">
            <ResourceIcon kind="money" />
            <ArrowRight className="size-3 text-muted-foreground" />
            <ResourceIcon kind="conservation" />
          </span>
        )
      case 'place':
        return <Box bg={buildingStyle(option.building ?? 'unique').fill} fg="#1f2937" title={buildingStyle(option.building ?? 'unique').label}><span className="text-[10px] font-black">{(buildingStyle(option.building ?? 'unique').label[0] ?? '?').toUpperCase()}</span></Box>
      case 'deck':
        return <Box bg="#334155" title={t('options.deck', 'Deck')}><Layers className="size-3.5" /></Box>
      case 'break':
      case 'money':
        return <Box bg="#5f6368" title={t('options.money', 'Money')}><span className="text-sm leading-none font-black">$</span></Box>
      case 'card':
        return <Box bg="#334155" title={t('options.card', 'Card')}><Layers className="size-3.5" /></Box>
      case 'tile':
        return <Box bg="#2f6b3a" title={t('options.bonusTile', 'Bonus tile')}><Gift className="size-3.5" /></Box>
      case 'worker':
        return <Box bg="#475569" title={t('options.worker', 'Worker')}><Users className="size-3.5" /></Box>
      case 'kind':
        return <Box bg={CARD_TYPE_STYLE.animal.banner}><PawPrint className={cn(k1 === 'small' ? 'size-2.5' : 'size-4')} /></Box>
      case 'discard':
      case 'discard_hand':
      case 'discard_display':
      case 'discard_final':
        return <Box bg="#9f1239" title={t('options.discard', 'Discard')}><Trash2 className="size-3.5" /></Box>
      case 'done':
        return <Muted><Check className="size-3.5" /></Muted>
      case 'skip':
        return <Muted><SkipForward className="size-3.5" /></Muted>
      case 'no':
        return <Muted><X className="size-3.5" /></Muted>
      case 'yes':
        return <Box bg="#059669"><Check className="size-3.5" /></Box>
    }
    if (['support', 'release', 'play_project', 'play_project_display', 'play_release', 'play_release_display'].includes(type))
      return <Box bg={CARD_TYPE_STYLE.project.banner} title={t('options.project', 'Conservation project')}><Shield className="size-3.5" /></Box>
    if (card) return <CardMark card={card} />
    return null
  })()
  return <span className="flex min-w-14 shrink-0 items-center justify-center">{icon}</span>
}
