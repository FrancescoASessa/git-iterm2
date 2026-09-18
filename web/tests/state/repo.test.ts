import { describe, expect, it } from 'vitest'

import { applySnapshot, changeCount, hasRepo, headLabel, snapshot } from '../../src/state/repo'
import { FALLBACK_THEME } from '../../src/theme'
import type { RepoSnapshot } from '../../src/api/types'

function makeSnapshot(overrides: Partial<RepoSnapshot> = {}): RepoSnapshot {
  return {
    root: '/r',
    head: { branch: 'main', detached_sha: null },
    upstream: null,
    state: 'clean',
    staged: [],
    unstaged: [],
    untracked: [],
    conflicted: [],
    stash_count: 0,
    theme: null,
    ...overrides,
  }
}

describe('repo state', () => {
  it('starts empty', () => {
    applySnapshot(null)
    expect(snapshot.value).toBeNull()
    expect(hasRepo.value).toBe(false)
    expect(headLabel.value).toBe('—')
    expect(changeCount.value).toBe(0)
  })

  it('derives the head label for a branch and a detached head', () => {
    applySnapshot(makeSnapshot())
    expect(headLabel.value).toBe('main')

    applySnapshot(makeSnapshot({ head: { branch: null, detached_sha: 'abcdef1234567890' } }))
    expect(headLabel.value).toBe('detached @ abcdef1')
  })

  it('counts every kind of change', () => {
    applySnapshot(
      makeSnapshot({
        staged: [{ path: 'a', orig_path: null, status: 'M' }],
        unstaged: [{ path: 'b', orig_path: null, status: 'M' }],
        untracked: ['c'],
        conflicted: [{ path: 'd', orig_path: null, status: 'U' }],
      }),
    )
    expect(changeCount.value).toBe(4)
    expect(hasRepo.value).toBe(true)
  })

  it('publishes both appearance palettes from the snapshot', () => {
    // Both must land on every snapshot: a macOS appearance switch fires no
    // iTerm2 event, so the stylesheet has to be able to pick the other one
    // at any moment without another round trip.
    const root = document.documentElement
    applySnapshot(
      makeSnapshot({
        theme: {
          light: { accent: '#0000ff', added: '#008000', removed: '#800000' },
          dark: { accent: '#88aaff', added: '#66dd88', removed: '#ff8888' },
          mono_family: 'MesloLGS NF',
          mono_size: 13,
        },
      }),
    )

    expect(root.style.getPropertyValue('--accent-light')).toBe('#0000ff')
    expect(root.style.getPropertyValue('--accent-dark')).toBe('#88aaff')
    expect(root.style.getPropertyValue('--added-light')).toBe('#008000')
    expect(root.style.getPropertyValue('--removed-dark')).toBe('#ff8888')
    expect(root.style.getPropertyValue('--font-mono')).toContain('"MesloLGS NF"')
    expect(root.style.getPropertyValue('--mono-size')).toBe('13px')
  })

  it('never lets the profile set the panel surface', () => {
    // The old model wrote the profile's own background/foreground/selection
    // and all 16 ANSI colours onto the root, which is exactly why the panel
    // looked like a colourised `git status`. Surfaces are now neutral tokens
    // owned by the stylesheet; nothing may write them from a snapshot.
    const root = document.documentElement
    applySnapshot(makeSnapshot({ theme: FALLBACK_THEME }))

    for (const property of ['--bg', '--fg', '--selection', '--surface', '--text', '--ansi-2']) {
      expect(root.style.getPropertyValue(property)).toBe('')
    }
  })

  it('falls back to the built-in palette without a theme', () => {
    const root = document.documentElement
    applySnapshot(makeSnapshot({ theme: null }))

    expect(root.style.getPropertyValue('--accent-light')).toBe(FALLBACK_THEME.light.accent)
    expect(root.style.getPropertyValue('--accent-dark')).toBe(FALLBACK_THEME.dark.accent)
  })
})
