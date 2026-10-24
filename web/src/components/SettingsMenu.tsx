import { Popover } from '@base-ui/react/popover'
import { useEffect, useState } from 'react'
import { LogOut, Settings } from 'lucide-react'
import { api } from '@/api/client'
import { LANGS, t } from '@/i18n'
import { isRuleBased, networkLabel, networkOrder } from '@/lib/networks'
import { useSettings } from '@/lib/settings'
import { cn } from '@/lib/utils'
import { Switch } from '@/components/ui/switch'


function Row({ label, hint, checked, onChange }: { label: string; hint: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-muted">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground">{hint}</span>
      </span>
      <Switch checked={checked} onCheckedChange={onChange} size="sm" className="mt-0.5" />
    </label>
  )
}

/** Gear button at the top right: language, AI hints and the hint model. */
export function SettingsMenu({
  hints,
  canHint,
  hintModel,
  map = 'map0',
  user,
  onHints,
  onHintModel,
  onSignOut,
}: {
  hints: boolean
  canHint: boolean
  hintModel?: string
  /** The game's map: off Map 0 only the models that know every map are offered. */
  map?: string
  user?: string
  onHints: (on: boolean) => void
  onHintModel: (name: string) => void
  onSignOut: () => void
}) {
  const [all, setAll] = useState<string[]>([])
  const [anyMap, setAnyMap] = useState<string[] | null>(null)
  useEffect(() => {
    if (!canHint) return
    api.checkpoints().then(
      (c) => {
        setAll([...c.checkpoints].sort((a, b) => networkOrder(a) - networkOrder(b) || a.localeCompare(b)))
        setAnyMap(c.any_map ?? null)
      },
      () => undefined,
    )
  }, [canHint])
  const models = map === 'map0' || anyMap === null ? all : all.filter((m) => anyMap.includes(m))
  const { lang, setLang } = useSettings()
  return (
    <Popover.Root>
      <Popover.Trigger
        aria-label={t('settings.title', 'Settings')}
        title={t('settings.title', 'Settings')}
        className="grid size-7 place-items-center rounded-md border bg-background hover:bg-muted aria-expanded:bg-muted"
      >
        <Settings className="size-4" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="bottom" align="end" sideOffset={6} className="z-50">
          <Popover.Popup className="w-72 rounded-xl bg-popover p-1.5 text-popover-foreground shadow-xl ring-1 ring-foreground/10 outline-none">
            <div className="px-2 pt-1 pb-0.5 text-xs font-semibold text-muted-foreground">{t('settings.title', 'Settings')}</div>
            <div className="px-2 py-1.5">
              <div className="text-sm font-medium">{t('settings.language', 'Language')}</div>
              <div className="text-xs text-muted-foreground">{t('settings.languageHint', 'Language of the interface and the game text')}</div>
              <div className="mt-1.5 inline-flex rounded-lg bg-muted p-0.5 text-sm">
                {LANGS.map((l) => (
                  <button
                    key={l.code}
                    type="button"
                    onClick={() => setLang(l.code)}
                    className={cn('rounded-md px-3 py-0.5 font-medium', lang === l.code ? 'bg-white shadow-sm' : 'text-muted-foreground hover:text-foreground')}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>
            {canHint && <Row label={t('settings.aiHints', 'AI hints')} hint={t('settings.aiHintsHint', "Show the AI's preferred moves and win chance")} checked={hints} onChange={onHints} />}
            {canHint && (
              <div className="px-2 py-1.5">
                <div className="text-sm font-medium">{t('settings.hintModel', 'Hint model')}</div>
                <div className="text-xs text-muted-foreground">{t('settings.hintModelHint', 'Who gives the hints. A rule policy puts 100% on its move and gives no win chance.')}</div>
                <select
                  value={hintModel ?? 'default'}
                  onChange={(e) => onHintModel(e.target.value)}
                  className="mt-1.5 h-8 w-full rounded-lg border bg-white px-2 text-sm outline-none focus-visible:border-sky-500"
                >
                  <option value="default">{t('settings.hintDefault', "Same as the opponent's network")}</option>
                  {[
                    { label: t('newGame.modelsGroup', 'AI models'), items: models.filter((m) => !isRuleBased(m)) },
                    { label: t('newGame.rulesGroup', 'Rule-based'), items: models.filter(isRuleBased) },
                  ]
                    .filter((g) => g.items.length > 0)
                    .map((g) => (
                      <optgroup key={g.label} label={g.label}>
                        {g.items.map((m) => (
                          <option key={m} value={m}>
                            {networkLabel(m)}
                            {isRuleBased(m) ? ` · ${t('settings.ruleNoOdds', 'rule: 100% on its move')}` : ''}
                          </option>
                        ))}
                      </optgroup>
                    ))}
                </select>
              </div>
            )}
            <div className="mt-1 flex items-center justify-between gap-2 border-t px-2 pt-2 pb-1">
              <span className="min-w-0 truncate text-xs text-muted-foreground">{user ? t('login.signedInAs', 'Signed in as {user}', { user }) : ''}</span>
              <button type="button" onClick={onSignOut} className="inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium hover:bg-muted">
                <LogOut className="size-3" /> {t('login.signOut', 'Sign out')}
              </button>
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}
