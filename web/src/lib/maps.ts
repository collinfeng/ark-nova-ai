import { t } from '@/i18n'

/** A map's name as the board shows it ("map0", "plan1" ... "plan8", "plana" are the server's ids). */
export function mapName(id: string): string {
  switch (id) {
    case 'map0':
      return t('maps.map0', 'Map 0: Standard')
    case 'plan1':
      return t('maps.plan1', 'Map 1: Observation Tower')
    case 'plan2':
      return t('maps.plan2', 'Map 2: Outdoor Areas')
    case 'plan3':
      return t('maps.plan3', 'Map 3: Silver Lake')
    case 'plan4':
      return t('maps.plan4', 'Map 4: Commercial Harbour')
    case 'plan5':
      return t('maps.plan5', 'Map 5: Park Restaurant')
    case 'plan6':
      return t('maps.plan6', 'Map 6: Research Institute')
    case 'plan7':
      return t('maps.plan7', 'Map 7: Ice Cream Parlours')
    case 'plan8':
      return t('maps.plan8', 'Map 8: Hollywood Hills')
    case 'plana':
      return t('maps.plana', 'Map A: Starter')
    default:
      return id
  }
}

/** The map's special rule in one sentence. */
export function mapRule(id: string): string {
  switch (id) {
    case 'map0':
      return t('maps.map0Rule', 'The open standard map, with no special rule.')
    case 'plan1':
      return t('maps.plan1Rule', '+2 appeal each time an animal moves into an empty standard enclosure next to the tower.')
    case 'plan2':
      return t('maps.plan2Rule', 'Standard enclosures next to the outdoor area count as 2 spaces larger.')
    case 'plan3':
      return t('maps.plan3Rule', 'No special rule: only its own layout and bonuses.')
    case 'plan4':
      return t('maps.plan4Rule', 'Once a building covers the harbour space: once per turn you may discard a hand card for 3 money.')
    case 'plan5':
      return t('maps.plan5Rule', 'Break income: +1 money for each covered space next to the restaurant.')
    case 'plan6':
      return t('maps.plan6Rule', 'Once a building covers the institute space: you may ignore 1 condition when playing an animal.')
    case 'plan7':
      return t('maps.plan7Rule', 'Once all three ice cream spaces are covered: +1 money break income for each of your kiosks.')
    case 'plan8':
      return t('maps.plan8Rule', 'Covering an H space reveals cards until a sponsor, which you take. All three covered: sponsors are 1 level cheaper.')
    case 'plana':
      return t('maps.planaRule', 'The map for a first game: starts with a kiosk and a size-3 enclosure already built.')
    default:
      return ''
  }
}

/** The short word printed on a special site, and what it does. */
export function siteLabel(site: string): string {
  switch (site) {
    case 'tower':
      return t('maps.siteTower', 'Tower')
    case 'outdoor':
      return t('maps.siteOutdoor', 'Outdoor')
    case 'harbour':
      return t('maps.siteHarbour', 'Harbour')
    case 'restaurant':
      return t('maps.siteRestaurant', 'Restaurant')
    case 'institute':
      return t('maps.siteInstitute', 'Institute')
    case 'ice_cream':
      return t('maps.siteIceCream', 'Ice cream')
    case 'hollywood':
      return 'H'
    default:
      return site
  }
}

export function siteRule(site: string): string {
  switch (site) {
    case 'tower':
      return t('maps.siteTowerRule', 'Observation tower: +2 appeal each time an animal moves into an empty standard enclosure next to it.')
    case 'outdoor':
      return t('maps.siteOutdoorRule', 'Outdoor area: standard enclosures next to it count as 2 spaces larger.')
    case 'harbour':
      return t('maps.siteHarbourRule', 'Harbour connection: once a building covers this space, you may once per turn discard a hand card for 3 money.')
    case 'restaurant':
      return t('maps.siteRestaurantRule', 'Park restaurant: break income +1 money for each covered space next to it.')
    case 'institute':
      return t('maps.siteInstituteRule', 'Research institute connection: once a building covers this space, you may ignore 1 condition when playing an animal.')
    case 'ice_cream':
      return t('maps.siteIceCreamRule', 'Ice cream parlour: once all three are covered, +1 money break income for each of your kiosks.')
    case 'hollywood':
      return t('maps.siteHollywoodRule', 'Hollywood Hills: covering this space reveals cards until a sponsor, which you take. All three covered: sponsors are 1 level cheaper.')
    default:
      return ''
  }
}
