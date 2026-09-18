import { runningOps } from '../src/state/ops'
import { applySnapshot, connection, receivedSnapshot, shellIntegration } from '../src/state/repo'
import {
  activeTab,
  branchFilter,
  dialog,
  selectedCommit,
  selectedFile,
  toasts,
} from '../src/state/ui'
import type { RepoSnapshot } from '../src/api/types'

export function makeSnapshot(overrides: Partial<RepoSnapshot> = {}): RepoSnapshot {
  return {
    root: '/repo',
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

export function resetState(): void {
  applySnapshot(null)
  // applySnapshot flips receivedSnapshot; put it back so a test starts in the
  // pre-first-snapshot state the app really boots in.
  receivedSnapshot.value = false
  // applySnapshot's `shellIntegrationAvailable` defaults to true, so the
  // line above already restored it; assert-by-assignment keeps this honest
  // if that default ever changes.
  shellIntegration.value = true
  connection.value = 'open'
  runningOps.value = []
  toasts.value = []
  dialog.value = null
  activeTab.value = 'changes'
  selectedFile.value = null
  selectedCommit.value = null
  branchFilter.value = ''
}
