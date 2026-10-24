import { t } from '@/i18n'
import type { PlaceGain } from '@/api/types'

/** What a kind of building does, in one or two sentences (the rules, not a particular placement). */
export function buildingEffect(kind: string, size?: number | null): string {
  switch (kind) {
    case 'kiosk':
      return t('buildings.kiosk', 'Each break: +1 money for every adjacent pavilion, special enclosure, sponsor building or occupied enclosure. Kiosks must be at least 3 spaces apart.')
    case 'pavilion':
      return t('buildings.pavilion', '+1 appeal when built. Feeds adjacent kiosks.')
    case 'enclosure':
      return t('buildings.enclosure', 'Houses one animal of size up to {size}, with its rock or water needs next to it. Feeds adjacent kiosks once occupied.', { size: size ?? '' })
    case 'petting_zoo':
      return t('buildings.pettingZoo', 'Houses petting zoo animals. One per zoo. Feeds adjacent kiosks.')
    case 'reptile_house':
      return t('buildings.reptileHouse', 'Build II only, one per zoo. Houses reptiles in fewer spaces (the smaller number on the card). When you build it, you may move reptiles in from standard enclosures, freeing them. Feeds adjacent kiosks.')
    case 'aviary':
      return t('buildings.aviary', 'Build II only, one per zoo. Houses birds in fewer spaces (the smaller number on the card). When you build it, you may move birds in from standard enclosures, freeing them. Feeds adjacent kiosks.')
    case 'unique':
      return t('buildings.unique', "The sponsor card's own building: its effect is on the card. Feeds adjacent kiosks.")
    default:
      return ''
  }
}

function bonusGain(bonus: string): string {
  switch (bonus) {
    case 'card':
      return t('buildings.gainCard', '+1 card')
    case 'money2':
      return t('buildings.gainMoney', '+{n} money', { n: 2 })
    case 'money5':
      return t('buildings.gainMoney', '+{n} money', { n: 5 })
    case 'money10':
      return t('buildings.gainMoney', '+{n} money', { n: 10 })
    case 'xtoken':
      return t('buildings.gainXToken', '+1 X-token')
    case 'rep1':
      return t('buildings.gainReputation', '+{n} reputation', { n: 1 })
    case 'rep2':
      return t('buildings.gainReputation', '+{n} reputation', { n: 2 })
    case 'clever':
      return t('buildings.gainClever', 'move an action card to slot 1')
    case 'kiosk':
      return t('buildings.gainKiosk', 'a free kiosk')
    case 'worker1':
      return t('buildings.gainWorker', '+1 association worker')
    case 'partner_zoo':
      return t('buildings.gainPartnerZoo', 'a partner zoo')
    case 'university':
      return t('buildings.gainUniversity', 'a university')
    case 'multiplier':
      return t('buildings.gainMultiplier', 'the x2 token')
    case 'sponsor_for_money':
      return t('buildings.gainSponsor', 'play a sponsor for money')
    default:
      return bonus
  }
}

/** One thing a placement brings, as a short phrase ("+2 reputation", "+1 money each break (kiosk)"). */
export function gainText(g: PlaceGain): string {
  if (g.k.startsWith('bonus:')) {
    const text = bonusGain(g.k.slice(6))
    return g.n > 1 ? t('buildings.twice', '{text} (twice: Archaeologist)', { text }) : text
  }
  switch (g.k) {
    case 'appeal':
      return t('buildings.gainAppeal', '+{n} appeal', { n: g.n })
    case 'full_cover':
      return t('buildings.fullCover', '+{n} appeal: the zoo is fully built', { n: g.n })
    case 'kiosk_income':
      return t('buildings.kioskIncome', '+{n} money each break (kiosk)', { n: g.n })
    case 'next_to_water':
      return t('buildings.nextToWater', '+{n} money (sponsor: spaces next to water)', { n: g.n })
    case 'next_to_rock':
      return t('buildings.nextToRock', '+{n} money (sponsor: spaces next to rock)', { n: g.n })
    case 'tower':
      return t('buildings.tower', 'next to the tower: +{n} appeal when an animal moves in', { n: g.n })
    case 'outdoor':
      return t('buildings.outdoor', 'next to the outdoor area: counts as {n} spaces larger', { n: g.n })
    case 'harbour':
      return t('buildings.harbour', 'connects the harbour: discard a card for {n} money once per turn', { n: g.n })
    case 'restaurant_income':
      return t('buildings.restaurantIncome', '+{n} money each break (restaurant)', { n: g.n })
    case 'institute':
      return t('buildings.institute', 'connects the institute: ignore 1 animal condition')
    case 'ice_cream_income':
      return t('buildings.iceCreamIncome', '+{n} money each break (ice cream)', { n: g.n })
    case 'hollywood':
      return g.n > 1
        ? t('buildings.hollywoodMany', 'reveal cards until a sponsor, {n} times', { n: g.n })
        : t('buildings.hollywood', 'reveal cards until a sponsor, and take it')
    case 'hollywood_all':
      return t('buildings.hollywoodAll', 'all H spaces covered: sponsors 1 level cheaper')
    default:
      return g.k
  }
}
