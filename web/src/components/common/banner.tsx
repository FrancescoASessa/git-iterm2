import { useState } from 'preact/hooks'
import type { ComponentChildren } from 'preact'

import { ApiError, sequence } from '../../api/client'
import { snapshot } from '../../state/repo'
import { pushToast } from '../../state/ui'

const LABELS: Record<string, string> = {
  merging: 'Merge in progress',
  rebasing: 'Rebase in progress',
  'cherry-picking': 'Cherry-pick in progress',
}

export function Banner({
  tone = 'warn',
  children,
}: {
  tone?: 'warn' | 'info'
  children: ComponentChildren
}) {
  return (
    <div class={`banner banner-${tone}`} role="status">
      {children}
    </div>
  )
}

export function RepoStateBanner() {
  const [pending, setPending] = useState<string | null>(null)
  const state = snapshot.value?.state
  if (state === undefined || state === 'clean') return null

  async function run(action: 'continue' | 'abort'): Promise<void> {
    if (pending !== null) return
    try {
      setPending(action)
      await sequence(action)
    } catch (error) {
      if (error instanceof ApiError)
        pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
      else throw error
    } finally {
      setPending(null)
    }
  }

  return (
    <Banner>
      <span class="grow">{LABELS[state] ?? state}</span>
      <button class="btn" disabled={pending !== null} onClick={() => void run('continue')}>
        Continue
      </button>
      <button class="btn" disabled={pending !== null} onClick={() => void run('abort')}>
        Abort
      </button>
    </Banner>
  )
}
