import { Fragment } from 'react'
import type { ActionName } from '@/api/types'
import { Award, Shield, Star } from 'lucide-react'
import { GameIcon } from './GameIcon'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { ACTIONS, ACTION_HEX, iconMeta } from '@/lib/game'


/** Round game icon (kept under its old name). */
export function IconDot({ name, size = 16, className }: { name: string; size?: number; className?: string }) {
  return <GameIcon name={name} size={size} className={className} />
}

const chip = 'mx-px inline-flex translate-y-[1px] items-center gap-px rounded-full px-1 text-[0.85em] leading-[1.35] font-bold whitespace-nowrap text-white align-baseline'

function actionOf(name: string): ActionName | null {
  const k = name.replace(/ActionCard$/, '').toLowerCase()
  return k in ACTIONS ? (k as ActionName) : null
}

/** An inline icon for a "{Name-Value}" token in card text. */
export function TokenChip({ name, value }: { name: string; value?: string }) {
  const v = value ?? ''
  switch (name) {
    case 'ConservationPoint':
      return (
        <span className={chip} style={{ background: '#2e9e57' }} title={t('playerPanel.conservation', 'Conservation point')}>
          <Shield className="size-[0.9em]" strokeWidth={2.6} />
          {v}
        </span>
      )
    case 'Money':
      return (
        <span className={cn(chip, 'rounded-md')} style={{ background: '#5f6368' }} title={t('playerPanel.money', 'Money')}>
          <span className="text-[0.75em] font-bold text-white/75">$</span>
          {v}
        </span>
      )
    case 'Appeal':
      return (
        <span className={chip} style={{ background: '#f08a24' }} title={t('playerPanel.appeal', 'Appeal')}>
          <Star className="size-[0.9em]" strokeWidth={2.6} />
          {v}
        </span>
      )
    case 'Reputation':
      return (
        <span className={chip} style={{ background: '#4a78c8' }} title={t('playerPanel.reputation', 'Reputation')}>
          <Award className="size-[0.9em]" strokeWidth={2.6} />
          {v}
        </span>
      )
    case 'XToken':
      return (
        <span className="mx-px inline-flex items-center gap-0.5 align-baseline" title={t('cards.chipXToken', 'X-token')}>
          <span className="inline-grid size-[1.3em] place-items-center bg-slate-700 text-[0.85em] leading-none font-black text-white" style={{ clipPath: 'polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)' }}>X</span>
          {v && <span className="text-[0.8em] font-semibold text-slate-700 tabular-nums">×{v}</span>}
        </span>
      )
    case 'Slot':
      return (
        <span className="mx-px inline-flex min-w-[1.2em] justify-center rounded-[3px] bg-slate-700 px-0.5 text-[0.85em] leading-[1.35] font-bold text-white" title={t('cards.chipSlot', 'Action slot {slot}', { slot: v })}>
          {v}
        </span>
      )
    case 'ActionCard':
      return (
        <span className="mx-px inline-block rounded-[3px] bg-slate-500 px-0.5 text-[0.85em] leading-[1.35] font-bold text-white" title={t('cards.chipActionCard', 'Action card')}>
          {t('cards.chipActShort', 'Act')}
        </span>
      )
    case 'MultiplierToken':
      return (
        <span className={chip} style={{ background: '#a16207' }} title={t('cards.chipMultiplier', 'Multiplier token')}>
          {v || '2'}×
        </span>
      )
    case 'Kiosk':
      return (
        <span className={chip} style={{ background: '#d9902f' }} title={t('cards.chipKiosk', 'Kiosk')}>
          {t('cards.chipKiosk', 'Kiosk')}
        </span>
      )
    case 'Size':
      return (
        <span className={chip} style={{ background: '#64748b' }} title={t('cards.chipEnclosureSize', 'Enclosure size')}>
          {t('cards.chipSizeShort', 'Size {size}', { size: v })}
        </span>
      )
    case 'LargeBirdAviary':
      return (
        <span className={chip} style={{ background: '#3fa9e0' }} title={t('cards.chipAviary', 'Large bird aviary')}>
          {t('cards.chipAviaryShort', 'Aviary')}
        </span>
      )
    case 'SizeAnimal':
      return (
        <span className={chip} style={{ background: '#2f7d3c' }}>
          {v === '2' ? t('cards.smallAnimal', 'small animal') : t('cards.largeAnimal', 'large animal')}
        </span>
      )
    case 'Marketing':
      return (
        <span className={chip} style={{ background: '#db2777' }} title={t('cards.chipMarketing', 'Marketing')}>
          {t('cards.chipMarketingShort', 'Mkt')}
        </span>
      )
    default: {
      const a = actionOf(name)
      if (a)
        return (
          <span className="mx-px inline-block rounded-[3px] px-1 text-[0.85em] whitespace-nowrap leading-[1.35] font-bold text-white" style={{ background: ACTION_HEX[a] }} title={`${ACTIONS[a].label} action card`}>
            {ACTIONS[a].label}
          </span>
        )
      const m = iconMeta(name)
      if (m) return <IconDot name={m.key} size={13} className="mx-px translate-y-[2px]" />
      return <span>{v ? `${name.toLowerCase()} ${v}` : name.toLowerCase()}</span>
    }
  }
}

/** Card text with **bold** and {Token-Value} markup. */
export function RichText({ text, className }: { text: string; className?: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*|\{[^}]+\})/g)
  return (
    <span className={className}>
      {parts.map((p, i) => {
        if (!p) return null
        if (p.startsWith('**') && p.endsWith('**')) return <b key={i}>{p.slice(2, -2)}</b>
        if (p.startsWith('{') && p.endsWith('}')) {
          const inner = p.slice(1, -1)
          const dash = inner.indexOf('-')
          return dash < 0 ? <TokenChip key={i} name={inner} /> : <TokenChip key={i} name={inner.slice(0, dash)} value={inner.slice(dash + 1)} />
        }
        return <Fragment key={i}>{p}</Fragment>
      })}
    </span>
  )
}
