import { createContext, useContext, useState, type ReactNode } from 'react'
import { getLang, setLang as applyLang, type Lang } from '@/i18n'

/** Board preferences kept in this browser. */
interface Settings {
  activityPreview: boolean
  setActivityPreview: (on: boolean) => void
  /** A card preview stays open while the pointer moves onto it; off: it closes when the pointer leaves the card. */
  keepPreview: boolean
  setKeepPreview: (on: boolean) => void
  /** Interface and game text language. Changing it makes the board fetch its text again. */
  lang: Lang
  setLang: (lang: Lang) => void
}

const KEY = 'ark.keepPreview'
const SettingsContext = createContext<Settings>({ activityPreview: false, setActivityPreview: () => undefined, keepPreview: true, setKeepPreview: () => undefined, lang: 'en', setLang: () => undefined })

function load(): boolean {
  try {
    return localStorage.getItem(KEY) !== '0'
  } catch {
    return true
  }
}

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [activityPreview, setActivityPreviewState] = useState(() => {
    try {
      return localStorage.getItem('ark.activityPreview') === '1'
    } catch {
      return false
    }
  })
  const setActivityPreview = (on: boolean) => {
    setActivityPreviewState(on)
    try {
      localStorage.setItem('ark.activityPreview', on ? '1' : '0')
    } catch {
      /* still applies until reload */
    }
  }
  const [keepPreview, set] = useState(load)
  const setKeepPreview = (on: boolean) => {
    set(on)
    try {
      localStorage.setItem(KEY, on ? '1' : '0')
    } catch {
      /* not kept: still applies until reload */
    }
  }
  const [lang, setLangState] = useState<Lang>(getLang)
  const setLang = (next: Lang) => {
    applyLang(next)  // before the state change, so the components that re-render already read the new language
    setLangState(next)
  }
  return <SettingsContext.Provider value={{ activityPreview, setActivityPreview, keepPreview, setKeepPreview, lang, setLang }}>{children}</SettingsContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSettings() {
  return useContext(SettingsContext)
}
