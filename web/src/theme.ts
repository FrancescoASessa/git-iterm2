import type { Theme, ThemePalette } from './api/types'

/** Used until the first themed snapshot arrives, and whenever the panel runs
 * outside iTerm2 (standalone / tests). The values match the backend's
 * `FALLBACK_LIGHT` / `FALLBACK_DARK` so an unthemed panel looks themed. */
export const FALLBACK_THEME: Theme = {
  light: { accent: '#0a69da', added: '#1a7f37', removed: '#cf222e' },
  dark: { accent: '#4493f8', added: '#3fb950', removed: '#f85149' },
  mono_family: 'Menlo',
  mono_size: 12,
}

/** Appended after the profile's family so a font that fails to resolve in the
 * web view still lands on a monospace face rather than the UI font. */
const MONO_FALLBACKS = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

/** `MesloLGS NF` is a legal CSS family name only when quoted. */
function cssFamily(family: string): string {
  const trimmed = family.trim()
  if (trimmed === '') return MONO_FALLBACKS
  const quoted = /^[A-Za-z][A-Za-z0-9-]*$/.test(trimmed)
    ? trimmed
    : `"${trimmed.replace(/"/g, '')}"`
  return `${quoted}, ${MONO_FALLBACKS}`
}

function applyPalette(
  root: HTMLElement,
  appearance: 'light' | 'dark',
  palette: ThemePalette,
): void {
  root.style.setProperty(`--accent-${appearance}`, palette.accent)
  root.style.setProperty(`--added-${appearance}`, palette.added)
  root.style.setProperty(`--removed-${appearance}`, palette.removed)
}

/** Writes the profile-derived custom properties.
 *
 * Both appearances are written unconditionally and the stylesheet resolves
 * `--accent` / `--add` / `--del` from them through
 * `@media (prefers-color-scheme)`: the web view already follows the system
 * appearance, and a switch fires no iTerm2 event, so nothing here may depend
 * on knowing which appearance is current. The panel's own surfaces are never
 * written from here — they are neutral tokens owned by the stylesheet.
 */
export function applyTheme(
  theme: Theme | null,
  root: HTMLElement = document.documentElement,
): void {
  const applied = theme ?? FALLBACK_THEME
  applyPalette(root, 'light', applied.light)
  applyPalette(root, 'dark', applied.dark)
  root.style.setProperty('--font-mono', cssFamily(applied.mono_family))
  root.style.setProperty('--mono-size', `${applied.mono_size}px`)
}
