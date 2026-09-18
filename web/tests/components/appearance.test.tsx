import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'

import { CommitBox } from '../../src/components/changes/commit-box'
import { ROW_HEIGHT } from '../../src/components/graph/lanes'
import { Tabs } from '../../src/components/tabs'
import { applySnapshot } from '../../src/state/repo'
import { makeSnapshot, resetState } from '../helpers'

// jsdom does not apply the stylesheet, so the rules themselves are the thing
// under test here: this file pins the *model* (where colour and font come
// from), not pixel values, which only a human in iTerm2 can judge.
const css = readFileSync(resolve(__dirname, '../../src/styles.css'), 'utf8')

describe('colour model', () => {
  it('owns its surfaces instead of taking them from the profile', () => {
    // The profile's background/foreground/selection and its 16 ANSI colours
    // used to be the panel's surface system. Nothing may reference them.
    expect(css).not.toMatch(/--ansi-/)
    expect(css).not.toMatch(/var\(--bg\)/)
    expect(css).not.toMatch(/var\(--fg\)/)
    expect(css).toMatch(/background:\s*var\(--surface\)/)
  })

  it('resolves light and dark from the system appearance, not from a snapshot', () => {
    expect(css).toMatch(/@media \(prefers-color-scheme: dark\)/)
    const dark = css.slice(css.indexOf('@media (prefers-color-scheme: dark)'))
    // Both the profile-derived aliases and the neutral surfaces flip here.
    for (const rule of [
      '--accent: var(--accent-dark)',
      '--add: var(--added-dark)',
      '--del: var(--removed-dark)',
      '--surface:',
      '--text:',
      '--separator:',
    ]) {
      expect(dark).toContain(rule)
    }
  })

  it('keeps the profile colours only where they carry meaning', () => {
    // Diff added/removed and the branch/ref accent — and nowhere else.
    expect(css).toMatch(/\.diff-add\s*\{[^}]*var\(--add\)/)
    expect(css).toMatch(/\.diff-del\s*\{[^}]*var\(--del\)/)
    expect(css).toMatch(/\.header \.branch\s*\{[^}]*var\(--accent\)/)
    // Graph lanes are decoration and use the panel's own token set.
    expect(css).toMatch(/--lane-0:/)
  })
})

describe('typography', () => {
  it('uses the system font for UI text', () => {
    expect(css).toMatch(/--font-ui:\s*\n?\s*-apple-system/)
    expect(css).toMatch(/body\s*\{[^}]*font-family:\s*var\(--font-ui\)/)
  })

  it('reserves the profile monospace font for repository text', () => {
    const rule = /((?:^|\n)(?:\.[a-z-]+,\n)*\.[a-z-]+\s*\{[^}]*font-family:\s*var\(--font-mono\))/
    const monoBlock = css.slice(css.indexOf('.mono,'), css.indexOf('/* --- Controls'))
    expect(css).toMatch(rule)
    for (const selector of ['.branch', '.sha', '.path', '.diff-line', '.commit-body']) {
      expect(monoBlock).toContain(selector)
    }
    // Buttons and inputs are UI chrome: they must not inherit the mono font
    // from a parent row that happens to be monospaced.
    expect(css).toMatch(/button\s*\{[^}]*font-family:\s*var\(--font-ui\)/)
    expect(css).toMatch(/textarea\s*\{[^}]*font-family:\s*var\(--font-ui\)/)
  })
})

describe('controls', () => {
  beforeEach(resetState)

  it('renders the tabs as one segmented control', () => {
    render(<Tabs />)
    const list = screen.getByRole('tablist')
    expect(list).toHaveClass('tabs')
    const tabs = screen.getAllByRole('tab')
    expect(tabs).toHaveLength(4)
    // One container, four segments: no per-tab wrapper, so the segments can
    // share the track and split the width evenly at 240px.
    expect(tabs.every((tab) => tab.parentElement === list)).toBe(true)
    expect(tabs.filter((tab) => tab.getAttribute('aria-selected') === 'true')).toHaveLength(1)
    expect(css).toMatch(/\.tabs button\s*\{[^}]*flex: 1 1 0/)
    expect(css).toMatch(/\.tabs button\[aria-selected='true'\]/)
  })

  it('makes Commit the accented default button, disabled until it can run', async () => {
    applySnapshot(makeSnapshot({ staged: [{ path: 'a.txt', orig_path: null, status: 'A' }] }))
    render(<CommitBox />)
    const commit = screen.getByRole('button', { name: 'Commit' })

    expect(commit).toHaveClass('btn', 'btn-primary')
    expect(commit).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Commit message'), 'a message')
    expect(commit).toBeEnabled()
    expect(css).toMatch(/\.btn-primary\s*\{[^}]*background: var\(--accent\)/)
  })

  it('keeps Commit disabled with a message but nothing staged', async () => {
    applySnapshot(makeSnapshot())
    render(<CommitBox />)

    await userEvent.type(screen.getByLabelText('Commit message'), 'a message')

    expect(screen.getByRole('button', { name: 'Commit' })).toBeDisabled()
  })

  it('shows a focus ring for keyboard navigation', () => {
    expect(css).toMatch(/:focus-visible\s*\{[^}]*outline: 2px solid var\(--focus-ring\)/)
  })

  it('keeps the graph row height in step with the density token', () => {
    // The virtual list places rows by multiplying ROW_HEIGHT, so a stylesheet
    // that renders them taller silently drifts the list. The new 26px density
    // would have done exactly that against the old 22px constant.
    const token = /--row-height:\s*(\d+)px/.exec(css)
    expect(token?.[1]).toBe(String(ROW_HEIGHT))
    expect(css).toMatch(/\.graph-row\s*\{[^}]*height: var\(--row-height\)/)
  })
})
