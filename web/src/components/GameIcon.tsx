/** Game icons drawn for this board, in the style of the printed cards: continents as dark
 * silhouettes on a pale circle; animal categories and the other icons as white silhouettes on a
 * saturated circle. Drawn on a 24x24 grid. */
import { ICON_META } from '@/lib/game'

const CONTINENT_PATHS: Record<string, string> = {
  africa: 'M9 3.5 L13.5 3.2 L15.5 5 L18.8 5.6 L20.2 8.8 L18.4 11.8 L17.6 14.6 L15.6 17.6 L13.6 20.8 L11.6 21 L10.6 17.4 L9.8 13.6 L7.6 12.4 L4.4 11.6 L3.4 8.4 L5.2 5.4 Z M18.6 15.6 L19.6 16.4 L18.8 19 L17.9 18.2 Z',
  americas: 'M2.6 4 L7 2.6 L11.6 2.4 L14.4 3.4 L13.4 5.6 L11.6 7.2 L10.6 9.6 L9.2 11.2 L7.4 10.8 L6.2 9 L4.4 7.8 L2.8 6.2 Z M10.6 12.4 L13.6 12.6 L16.6 14.2 L17.2 16 L15.6 18.2 L13.6 20.4 L12.4 22.6 L11.4 20.2 L10.8 17 L9.8 14.4 Z',
  asia: 'M2.4 8.2 L5.8 5.2 L9.6 5.8 L12.6 3.2 L17.4 3.6 L21.6 5.6 L21.2 9.4 L19 11.6 L19.8 14.6 L17.4 14.8 L16.2 17.6 L14.2 15.8 L12.6 18.4 L10.6 14.2 L7.6 14.4 L5.4 12.2 L2.6 11.2 Z M19.6 17.6 L21.4 18.6 L20 20.4 Z',
  australia: 'M3.4 11.4 L5.6 8.6 L8.4 7.6 L9.8 5.6 L11.8 5.8 L12.6 7.8 L14.6 4.6 L16 7.8 L18.8 10 L20.4 13 L18.8 16.6 L15.8 17.8 L13.4 16.2 L10.6 16.2 L7.4 17.2 L4.4 15.4 Z M15.2 19.6 L17 19.4 L16.4 21.2 Z',
  europe: 'M3.4 15.6 L7.2 15 L8.2 13.2 L7.4 11.8 L9.2 10.8 L11 10.4 L11.8 8.8 L12.8 10 L14.6 9.8 L17.2 9 L20.6 9.4 L21.4 12.2 L20.4 15 L18.2 15.6 L17.2 17.6 L16.4 19.8 L15.4 18.4 L14.6 16.6 L13.6 16 L15 18.6 L15.4 20.6 L14.2 20.4 L12.2 17.4 L10.8 16 L9.4 16.4 L8.2 16.6 L7.8 19.2 L5 19.8 L3 18.6 Z M10.8 8.4 L11.4 5.2 L13.6 2.6 L16.4 2 L15.2 4.2 L14.8 6.6 L13.6 8.4 L12.4 7.2 Z M16.6 3.2 L18.6 3.4 L18.4 7.2 L16.8 7.8 L16.2 5.6 Z M5.4 7.6 L7 5.6 L7.8 7.8 L7.4 10.4 L5.8 10.8 L6.4 9.2 Z M3.2 9.2 L4.6 8.8 L4.8 10.6 L3.4 11 Z',
}

function Glyph({ name, bg }: { name: string; bg: string }) {
  switch (name) {
    case 'bird':
      return <><path d="M3 9 C6 8 8.5 9 11 12 C12.5 9 15 6.5 20.5 6 C18 8 16 10.5 14.5 13.5 C13.5 15.5 11.5 17 9 17.5 L6.5 19.5 L7.2 16.8 C5.4 15.6 4.6 13.6 5.6 11.4 C4.8 10.4 4 9.8 3 9 Z" fill="#fff"/></>
    case 'predator':
      return <><ellipse cx="12" cy="15.6" rx="4.6" ry="3.8" fill="#fff"/><ellipse cx="6.2" cy="10.4" rx="1.9" ry="2.4" fill="#fff"/><ellipse cx="9.6" cy="6.8" rx="2" ry="2.6" fill="#fff"/><ellipse cx="14.4" cy="6.8" rx="2" ry="2.6" fill="#fff"/><ellipse cx="17.8" cy="10.4" rx="1.9" ry="2.4" fill="#fff"/></>
    case 'herbivore':
      return <><path d="M7 4 L8.6 8 M8.6 8 L6 6.6 M17 4 L15.4 8 M15.4 8 L18 6.6" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" fill="none"/><path d="M8.2 8.4 C9.6 7.6 14.4 7.6 15.8 8.4 L15.2 13 L13.4 19.4 C12.6 20.4 11.4 20.4 10.6 19.4 L8.8 13 Z" fill="#fff"/><path d="M8.6 9.6 L5.4 9.4 L7 11.4 Z M15.4 9.6 L18.6 9.4 L17 11.4 Z" fill="#fff"/></>
    case 'reptile':
      return <><path d="M12 3.2 C13.4 3.2 14 4.6 13.6 6 L13.4 7.4 C14.4 9 14.6 11.6 13.8 13.6 C13.4 15.4 13.4 17 14.4 18.4 C15.4 19.8 14.8 21.2 13.4 20.8 C12 19.6 11 17.4 11 15.2 C10.6 12.6 9.6 10 10.6 7.4 L10.4 6 C10 4.6 10.6 3.2 12 3.2 Z" fill="#fff"/><path d="M10.4 8.6 L7 7 M13.6 8.6 L17 7 M10.6 13 L7.2 15 M13.4 13 L16.8 15" stroke="#fff" strokeWidth="1.5" strokeLinecap="round"/></>
    case 'primate':
      return <><circle cx="12" cy="11" r="6.4" fill="#fff"/><circle cx="5.2" cy="10.6" r="2.2" fill="#fff"/><circle cx="18.8" cy="10.6" r="2.2" fill="#fff"/><path d="M9 10.4 C9 8.6 10.6 8.4 12 9.6 C13.4 8.4 15 8.6 15 10.4 C15.6 12 15 14.2 12 14.8 C9 14.2 8.4 12 9 10.4 Z" fill={bg}/><circle cx="10.6" cy="10.8" r=".8" fill="#fff"/><circle cx="13.4" cy="10.8" r=".8" fill="#fff"/><path d="M8.6 17 L9.6 20 L14.4 20 L15.4 17" fill="#fff"/></>
    case 'bear':
      return <><circle cx="12" cy="13" r="6.6" fill="#fff"/><circle cx="6.4" cy="7.2" r="2.6" fill="#fff"/><circle cx="17.6" cy="7.2" r="2.6" fill="#fff"/><ellipse cx="12" cy="15.4" rx="2.8" ry="2.2" fill={bg}/><ellipse cx="12" cy="14.6" rx="1.1" ry=".8" fill="#fff"/><circle cx="9.6" cy="11.4" r=".9" fill={bg}/><circle cx="14.4" cy="11.4" r=".9" fill={bg}/></>
    case 'pet':
      return <><path d="M7 8 C5 6 4 4 6 3.4 C8 3 9 6 9.6 7.6 M17 8 C19 6 20 4 18 3.4 C16 3 15 6 14.4 7.6" stroke="#fff" strokeWidth="1.8" fill="none" strokeLinecap="round"/><path d="M6.6 9.4 C8.4 7.4 15.6 7.4 17.4 9.4 C18.6 12.6 16.6 17.6 12 19.6 C7.4 17.6 5.4 12.6 6.6 9.4 Z" fill="#fff"/><circle cx="9.8" cy="12" r=".9" fill={bg}/><circle cx="14.2" cy="12" r=".9" fill={bg}/><ellipse cx="12" cy="15.6" rx="1.4" ry="1" fill={bg}/></>
    case 'science':
      return <><path d="M10 3.6 L14 3.6 M11 3.8 L11 9.4 L6.4 17.6 C5.8 18.8 6.6 20.2 8 20.2 L16 20.2 C17.4 20.2 18.2 18.8 17.6 17.6 L13 9.4 L13 3.8" stroke="#fff" strokeWidth="1.6" fill="none" strokeLinejoin="round"/><path d="M8.4 15 L15.6 15 L17 17.8 C17.4 18.6 16.8 19.4 16 19.4 L8 19.4 C7.2 19.4 6.6 18.6 7 17.8 Z" fill="#fff"/></>
    case 'rock':
      return <><path d="M3.4 18.6 L9 8 L12 12.4 L14.4 9.2 L20.6 18.6 Z" fill="#fff"/><path d="M9 8 L10.6 11 L9.4 10.4 L8.2 11.6 Z" fill={bg}/></>
    case 'water':
      return <><path d="M12 3.6 C14.6 7.6 17.6 11 17.6 14.4 C17.6 17.6 15.2 20 12 20 C8.8 20 6.4 17.6 6.4 14.4 C6.4 11 9.4 7.6 12 3.6 Z" fill="#fff"/></>
    default:
      return null
  }
}

export const ICON_BG: Record<string, string> = {
  africa: '#f5d020',
  americas: '#f6b27a',
  asia: '#9fd3a8',
  australia: '#e85a50',
  europe: '#8cc2ef',
  bird: '#2aa3e0',
  predator: '#b0302e',
  herbivore: '#2f7d3c',
  reptile: '#7449a6',
  primate: '#e3a21a',
  bear: '#7a4e2d',
  pet: '#d9719a',
  science: '#2f9c95',
  rock: '#8b8b8b',
  water: '#3d86d6',
}

/** A round game icon. Unknown names fall back to a grey circle with their first letters. */
export function GameIcon({ name, size = 20, title, className }: { name: string; size?: number; title?: string; className?: string }) {
  const key = name.toLowerCase()
  const bg = ICON_BG[key] ?? '#9ca3af'
  const label = title ?? ICON_META[key]?.label ?? name
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className={className} role="img" aria-label={label}>
      <title>{label}</title>
      <circle cx="12" cy="12" r="11.6" fill={bg} />
      {CONTINENT_PATHS[key] ? (
        <path d={CONTINENT_PATHS[key]} fill="#1a1a1a" />
      ) : key in ICON_BG ? (
        <Glyph name={key} bg={bg} />
      ) : (
        <text x="12" y="16" textAnchor="middle" fontSize="10" fontWeight="700" fill="#fff">{name.slice(0, 2)}</text>
      )}
    </svg>
  )
}
