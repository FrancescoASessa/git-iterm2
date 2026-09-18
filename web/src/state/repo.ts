import { computed, signal } from '@preact/signals'

import type { RepoSnapshot } from '../api/types'
import type { WsStatus } from '../api/ws'
import { applyTheme } from '../theme'

export const snapshot = signal<RepoSnapshot | null>(null)
export const connection = signal<WsStatus>('connecting')
// False until the backend has answered once. `snapshot === null` alone cannot
// tell "still loading" from "answered: this is not a repository".
export const receivedSnapshot = signal(false)

export const hasRepo = computed(() => snapshot.value !== null)

export const headLabel = computed(() => {
  const head = snapshot.value?.head
  if (!head) return '—'
  if (head.branch !== null) return head.branch
  if (head.detached_sha !== null) return `detached @ ${head.detached_sha.slice(0, 7)}`
  return '—'
})

export const changeCount = computed(() => {
  const current = snapshot.value
  if (current === null) return 0
  return (
    current.staged.length +
    current.unstaged.length +
    current.untracked.length +
    current.conflicted.length
  )
})

let appliedTheme: string | null = null

export function applySnapshot(next: RepoSnapshot | null): void {
  snapshot.value = next
  receivedSnapshot.value = true
  const key = JSON.stringify(next?.theme ?? null)
  if (key !== appliedTheme) {
    appliedTheme = key
    applyTheme(next?.theme ?? null)
  }
}
