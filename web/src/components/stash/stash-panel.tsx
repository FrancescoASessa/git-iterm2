import { useEffect, useState } from 'preact/hooks'

import { ApiError, getStash, stashAction, stashPush } from '../../api/client'
import type { StashEntry } from '../../api/types'
import { snapshot } from '../../state/repo'
import { askConfirm, pushToast } from '../../state/ui'
import { EmptyState } from '../common/empty-state'
import { useAsyncAction } from '../common/use-async-action'

function relativeTime(unixSeconds: number): string {
  const diff = Math.max(0, Date.now() / 1000 - unixSeconds)
  if (diff < 60) return 'now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d`
  if (diff < 86400 * 28) return `${Math.floor(diff / (86400 * 7))}w`
  return new Date(unixSeconds * 1000).toISOString().slice(0, 10)
}

async function withToast(action: () => Promise<void>): Promise<void> {
  try {
    await action()
  } catch (error) {
    if (error instanceof ApiError) {
      pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
    } else {
      throw error
    }
  }
}

function useStashEntries(reloadKey: number): {
  entries: StashEntry[] | null
  error: string | null
} {
  const [entries, setEntries] = useState<StashEntry[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const stashCount = snapshot.value?.stash_count ?? 0

  useEffect(() => {
    let cancelled = false
    getStash()
      .then((result) => {
        if (cancelled) return
        setEntries(result.entries)
        setError(null)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError) {
          setError(err.message)
        } else {
          throw err
        }
      })
    return () => {
      cancelled = true
    }
    // reloadKey forces a reload after actions that don't otherwise change stash_count
  }, [stashCount, reloadKey])

  return { entries, error }
}

function StashRow({
  entry,
  onAction,
}: {
  entry: StashEntry
  onAction: (index: number, action: 'apply' | 'pop' | 'drop') => Promise<void>
}) {
  const { pending, run } = useAsyncAction()

  return (
    <div class="row stash-row">
      <span class="stash-ref muted">{`stash@{${entry.index}}`}</span>
      <span class="grow">{entry.message}</span>
      <span class="count">{relativeTime(entry.timestamp)}</span>
      <div class="row-actions">
        <button
          disabled={pending}
          aria-label={`Apply stash@{${entry.index}}`}
          onClick={() => run(() => onAction(entry.index, 'apply'))}
        >
          Apply
        </button>
        <button
          disabled={pending}
          aria-label={`Pop stash@{${entry.index}}`}
          onClick={() => run(() => onAction(entry.index, 'pop'))}
        >
          Pop
        </button>
        <button
          class="danger"
          disabled={pending}
          aria-label={`Drop stash@{${entry.index}}`}
          onClick={() => run(() => onAction(entry.index, 'drop'))}
        >
          Drop
        </button>
      </div>
    </div>
  )
}

function StashPushControl({
  pending,
  onPush,
}: {
  pending: boolean
  onPush: (message: string, includeUntracked: boolean) => void
}) {
  const [message, setMessage] = useState('')
  const [includeUntracked, setIncludeUntracked] = useState(false)

  function submit(): void {
    const value = message
    const untracked = includeUntracked
    setMessage('')
    setIncludeUntracked(false)
    onPush(value, untracked)
  }

  return (
    <div class="row push-row">
      <input
        class="grow"
        aria-label="Stash message"
        placeholder="Stash message"
        value={message}
        disabled={pending}
        onInput={(event) => setMessage((event.target as HTMLInputElement).value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter') submit()
        }}
      />
      <label>
        <input
          type="checkbox"
          aria-label="Include untracked"
          checked={includeUntracked}
          disabled={pending}
          onChange={(event) => setIncludeUntracked((event.target as HTMLInputElement).checked)}
        />
        Include untracked
      </label>
      <button class="btn" disabled={pending} onClick={submit}>
        Stash
      </button>
    </div>
  )
}

export function StashPanel() {
  const [reloadKey, setReloadKey] = useState(0)
  const { entries, error } = useStashEntries(reloadKey)
  const { pending, run } = useAsyncAction()

  function reload(): void {
    setReloadKey((key) => key + 1)
  }

  function handlePush(message: string, includeUntracked: boolean): Promise<void> {
    return withToast(async () => {
      await stashPush(message, includeUntracked)
      reload()
    })
  }

  async function dropFlow(index: number): Promise<void> {
    const choice = await askConfirm({
      title: `Drop stash@{${index}}?`,
      body: 'This cannot be undone.',
      choices: [{ id: 'drop', label: 'Drop', tone: 'danger' }],
    })
    if (choice !== 'drop') return
    await stashAction(index, 'drop')
    reload()
  }

  function handleAction(index: number, action: 'apply' | 'pop' | 'drop'): Promise<void> {
    return withToast(async () => {
      if (action === 'drop') {
        await dropFlow(index)
        return
      }
      await stashAction(index, action)
      reload()
    })
  }

  return (
    <div class="stash">
      <StashPushControl
        pending={pending}
        onPush={(message, includeUntracked) => run(() => handlePush(message, includeUntracked))}
      />
      {error !== null && <div class="diff-error">{error}</div>}
      {entries !== null && entries.length === 0 && <EmptyState title="No stashes" />}
      {entries !== null &&
        entries.map((entry) => (
          <StashRow key={entry.index} entry={entry} onAction={handleAction} />
        ))}
    </div>
  )
}
