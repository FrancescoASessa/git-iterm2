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
    shell_integration: true,
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

  it('applies the theme from the snapshot', () => {
    const root = document.documentElement
    applySnapshot(makeSnapshot({ theme: { ...FALLBACK_THEME, background: '#123456' } }))
    expect(root.style.getPropertyValue('--bg')).toBe('#123456')

    applySnapshot(makeSnapshot({ theme: null }))
    expect(root.style.getPropertyValue('--bg')).toBe(FALLBACK_THEME.background)
  })
})
