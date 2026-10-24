import { t } from '@/i18n'

/** Rule-based opponents (search over the rules, no learned model); the rest are trained networks. */
const RULES = ['greedy', 'beam_2x3', 'beam_3x8']
/** Networks by difficulty, easiest first. run4_70M was Normal before M10 and only appears in old games. */
const MODELS = ['run5_13M', 'maps10_s0_1B_ema', 'long_s0_1B']

/** How sentences name the opponent ("AI's zoo", "AI wins"); the difficulty itself shows as "vs Normal". */
export function aiName(): string {
  return t('playerPanel.ai', 'AI')
}

const bare = (checkpoint: string) => checkpoint.replace(/\.pt$/, '')

export function isRuleBased(checkpoint: string): boolean {
  return RULES.includes(bare(checkpoint))
}

/** Display labels only (a difficulty, or the kind of search); file names remain the API and save identifiers. */
export function networkLabel(checkpoint: string): string {
  switch (bare(checkpoint)) {
    case 'greedy':
      return t('newGame.greedySearch', 'Greedy search')
    case 'beam_2x3':
      return t('newGame.beamSearch', 'Beam search')
    case 'beam_3x8':
      return t('newGame.beamSearchPlus', 'Beam search +')
    case 'run5_13M':
      return t('newGame.easy', 'Easy')
    case 'maps10_s0_1B_ema':
    case 'run4_70M':
      return t('newGame.normal', 'Normal')
    case 'long_s0_1B':
      return t('newGame.hard', 'Hard')
    default:
      return bare(checkpoint)
  }
}

/** Models first by difficulty, then the rule-based opponents from the lightest search up. */
export function networkOrder(checkpoint: string): number {
  const order = [...MODELS, ...RULES]
  const index = order.indexOf(bare(checkpoint))
  return index < 0 ? order.length : index
}

export function networkDescription(checkpoint: string): string | null {
  switch (bare(checkpoint)) {
    case 'greedy':
      return t('newGame.greedyHint', 'A rule-based opponent focused on the current turn. Hints come from a separate analysis model.')
    case 'beam_2x3':
      return t('newGame.lightBeamHint', 'Searches 2 of its own turns, keeping 3 plans. Hints come from a separate analysis model.')
    case 'beam_3x8':
      return t('newGame.standardBeamHint', 'Searches 3 of its own turns, keeping 8 plans. Moves can take longer; hints come from a separate analysis model.')
    case 'maps10_s0_1B_ema':
      return t('newGame.normalHint', 'Trained on all 10 maps.')
    default:
      return null
  }
}
