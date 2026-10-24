import type { ActionName, Slot } from '@/api/types'
import { t } from '@/i18n'
import { ACTIONS } from '@/lib/game'
import { cn } from '@/lib/utils'
import { TokenRules } from './ActionTokens'

const ANIMAL_COUNTS = {
  I: [0, 1, 1, 1, 2],
  II: [1, 1, 2, 2, 2],
}

const CARD_ROWS = {
  I: [
    [1, 1, false],
    [1, 0, false],
    [2, 1, false],
    [2, 0, false],
    [3, 1, true],
  ],
  II: [
    [1, 0, false],
    [2, 1, false],
    [2, 0, true],
    [3, 1, true],
    [4, 1, true],
  ],
} as const

function actionText(action: ActionName, strength: number, side: 'I' | 'II') {
  const index = Math.min(5, Math.max(1, strength)) - 1
  switch (action) {
    case 'animals': {
      const count = ANIMAL_COUNTS[side][index]
      return side === 'I'
        ? t('actionRules.animalsI', 'Play up to {count} animal card(s).', { count })
        : t(
            'actionRules.animalsII',
            'Play up to {count} animal card(s). At strength 5, gain 1 reputation first. You may also play a card from the display by paying extra equal to its slot number.',
            { count },
          )
    }
    case 'build':
      return side === 'I'
        ? t('actionRules.buildI', 'Build one building of size {strength} or less; pay 2 money per covered hex.', { strength })
        : t(
            'actionRules.buildII',
            'Build multiple different buildings with total size up to {strength}; pay 2 money per hex. Build II spaces, reptile houses and aviaries are available.',
            { strength },
          )
    case 'cards': {
      const [draw, discard, snap] = CARD_ROWS[side][index]
      const cardText = discard
        ? t('actionRules.cardsDrawDiscard', 'Draw {draw}; discard {discard}.', { draw, discard })
        : t('actionRules.cardsDraw', 'Draw {draw}.', { draw })
      return snap
        ? `${cardText} ${t('actionRules.cardsSnap', 'You may snap 1 display card instead.')}`
        : `${cardText} ${side === 'II' ? t('actionRules.cardsMix', 'Draws may mix the deck and display.') : ''}`
    }
    case 'association':
      return side === 'I'
        ? t(
            'actionRules.associationI',
            'Use one association task whose required strength is no more than {strength}. Repeating the same task this turn needs 2 workers.',
            { strength },
          )
        : t(
            'actionRules.associationII',
            'Split strength across different tasks. After completing a task, you may donate once, pay the leftmost empty space and gain 1 conservation.',
          )
    case 'sponsors':
      return side === 'I'
        ? t(
            'actionRules.sponsorsI',
            'Play one sponsor with level {strength} or less, or break {strength} spaces and gain {strength} money.',
            { strength },
          )
        : t(
            'actionRules.sponsorsII',
            'Play sponsors whose total level is at most {budget}, from your hand or display. Taking money on a break is doubled, and Sponsors II cards are available.',
            { budget: strength + 1 },
          )
  }
}

export function ActionRuleInfo({
  action,
  strength,
  upgraded,
  xToken = false,
  reason,
  slot,
  slots = [],
}: {
  action: ActionName
  strength: number
  upgraded: boolean
  xToken?: boolean
  reason?: string
  /** The card as it lies (its tokens), and all of its owner's cards (for Venom). */
  slot?: Slot
  slots?: Slot[]
}) {
  const meta = ACTIONS[action]
  return (
    <div className="overflow-hidden text-left">
      <div className="flex items-center gap-2 border-b bg-slate-50 px-4 py-3">
        <span className={cn('size-2.5 rounded-full', meta.color)} />
        <span className="text-sm font-semibold text-slate-900">{meta.label}</span>
        <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600">
          {t('actionRules.strength', 'Strength {strength}', { strength })}
        </span>
        <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-900">
          {upgraded ? 'II' : 'I'} · {t('actionRules.current', 'Current')}
        </span>
      </div>
      <div className="space-y-3 p-4">
        {xToken ? (
          <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs leading-relaxed text-slate-700">
            {t('actionRules.xToken', 'Return the chosen action card to strength 1 and gain 1 X-token without performing its action.')}
          </p>
        ) : (
          <div className="grid gap-2 md:grid-cols-2">
            {(['I', 'II'] as const).map((side) => {
              const active = (upgraded ? 'II' : 'I') === side
              return (
                <div
                  key={side}
                  className={cn(
                    'min-w-0 rounded-lg border p-3',
                    active ? 'border-sky-300 bg-sky-50/70 shadow-[inset_3px_0_0_#0ea5e9]' : 'border-slate-200 bg-white',
                  )}
                >
                  <div className="mb-1.5 flex items-center gap-1.5">
                    <span className={cn('grid size-5 place-items-center rounded-md text-[10px] font-black', active ? 'bg-sky-600 text-white' : 'bg-slate-100 text-slate-500')}>
                      {side}
                    </span>
                    <span className={cn('text-[10px] font-semibold', active ? 'text-sky-800' : 'text-slate-500')}>
                      {active ? t('actionRules.currentFace', 'Current face') : t('actionRules.alternateFace', 'Other face')}
                    </span>
                  </div>
                  <p className="text-xs leading-relaxed text-slate-700">{actionText(action, strength, side)}</p>
                </div>
              )
            })}
          </div>
        )}
        {slot && <TokenRules slot={slot} slots={slots} />}
        {reason && (
          <p className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs leading-relaxed text-rose-800">
            {reason}
          </p>
        )}
      </div>
    </div>
  )
}
