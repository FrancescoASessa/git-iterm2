import { useState } from 'preact/hooks'

import { ApiError, remoteOp } from '../api/client'
import { isBusy, runningOps } from '../state/ops'
import { hasRepo, headLabel, snapshot } from '../state/repo'
import { pushToast } from '../state/ui'

const OPS: Array<{ id: 'fetch' | 'pull' | 'push'; label: string }> = [
  { id: 'fetch', label: 'Fetch' },
  { id: 'pull', label: 'Pull' },
  { id: 'push', label: 'Push' },
]

export function Header() {
  const [pending, setPending] = useState<string | null>(null)
  const upstream = snapshot.value?.upstream ?? null
  const current = runningOps.value[0]
  const disabled = isBusy.value || !hasRepo.value || pending !== null

  async function start(op: 'fetch' | 'pull' | 'push'): Promise<void> {
    if (pending !== null) return
    try {
      setPending(op)
      await remoteOp(op)
    } catch (error) {
      if (error instanceof ApiError)
        pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
      else throw error
    } finally {
      setPending(null)
    }
  }

  return (
    <header class="row header">
      <span class="branch">{'⎇ ' + headLabel.value}</span>
      {upstream !== null && (
        <>
          <span
            class="pill"
            aria-label={`${upstream.ahead} commit${upstream.ahead === 1 ? '' : 's'} ahead of ${upstream.name}`}
          >
            ↑{upstream.ahead}
          </span>
          <span
            class="pill"
            aria-label={`${upstream.behind} commit${upstream.behind === 1 ? '' : 's'} behind ${upstream.name}`}
          >
            ↓{upstream.behind}
          </span>
        </>
      )}
      <span class="op-progress">
        {current !== undefined &&
          `${current.phase}${current.pct === null ? '' : ` ${current.pct}%`}`}
      </span>
      <div class="btn-group ops">
        {OPS.map((op) => (
          <button key={op.id} class="btn" disabled={disabled} onClick={() => void start(op.id)}>
            {op.label}
          </button>
        ))}
      </div>
    </header>
  )
}
