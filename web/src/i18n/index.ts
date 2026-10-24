import zh from './zh-CN/ui.json'

/**
 * UI text in the chosen language. English lives next to the code as the default argument of t(), so a
 * missing translation shows English instead of nothing; Simplified Chinese comes from zh-CN/ui.json.
 *   t('topBar.save', 'Save')                      t('topBar.versus', 'vs {name}', { name })
 * The server writes its own text (titles, option labels, card text) in the same language, from the
 * X-Lang header the API client sends.
 */
export type Lang = 'en' | 'zh-CN'

export const LANGS: { code: Lang; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '简体中文' },
]

const KEY = 'ark.lang'

function load(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'en' || saved === 'zh-CN') return saved
  } catch {
    /* storage unavailable */
  }
  return 'en'
}

let current: Lang = load()

export function getLang(): Lang {
  return current
}

export function setLang(lang: Lang) {
  current = lang
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    /* kept for this session only */
  }
  document.documentElement.lang = lang === 'zh-CN' ? 'zh-CN' : 'en'
}

function flatten(tree: Record<string, unknown>, prefix: string, out: Map<string, string>) {
  for (const [k, v] of Object.entries(tree)) {
    if (typeof v === 'string') out.set(prefix + k, v)
    else if (v && typeof v === 'object') flatten(v as Record<string, unknown>, `${prefix}${k}.`, out)
  }
}

const zhText = new Map<string, string>()
flatten(zh.ui, '', zhText)
flatten(zh.terms, 'terms.', zhText)

export type Params = Record<string, string | number | undefined>

export function fill(text: string, params?: Params): string {
  if (!params) return text
  return text.replace(/\{(\w+)\}/g, (m, name: string) => (params[name] === undefined ? m : String(params[name])))
}

export function t(key: string, en: string, params?: Params): string {
  const text = current === 'zh-CN' ? (zhText.get(key) ?? en) : en
  return fill(text, params)
}

/** A game term from ui.json's terms section, e.g. term('actions', 'build', 'Build'). */
export function term(group: string, key: string, en: string): string {
  return t(`terms.${group}.${key}`, en)
}

document.documentElement.lang = current === 'zh-CN' ? 'zh-CN' : 'en'
