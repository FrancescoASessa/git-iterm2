import type { Theme } from './api/types'

export const FALLBACK_THEME: Theme = {
  background: '#1c1c1c',
  foreground: '#d8d8d8',
  selection: '#33414e',
  ansi: [
    '#3b3b3b',
    '#e06c75',
    '#98c379',
    '#e5c07b',
    '#61afef',
    '#c678dd',
    '#56b6c2',
    '#abb2bf',
    '#5c6370',
    '#ff7b86',
    '#b5e890',
    '#ffd694',
    '#84c9ff',
    '#e2a8f5',
    '#7fdbe0',
    '#ffffff',
  ],
  font_family: 'Menlo, monospace',
  font_size: 12,
}

export function applyTheme(
  theme: Theme | null,
  root: HTMLElement = document.documentElement,
): void {
  const applied = theme ?? FALLBACK_THEME
  root.style.setProperty('--bg', applied.background)
  root.style.setProperty('--fg', applied.foreground)
  root.style.setProperty('--selection', applied.selection)
  applied.ansi.forEach((color, index) => root.style.setProperty(`--ansi-${index}`, color))
  root.style.setProperty('--font', applied.font_family)
  root.style.setProperty('--font-size', `${applied.font_size}px`)
}
