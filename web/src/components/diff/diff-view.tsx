import { useEffect, useState } from 'preact/hooks'

import { ApiError, getCommitDiff, getDiff, openDiffSplit } from '../../api/client'
import { pushToast } from '../../state/ui'
import { useAsyncAction } from '../common/use-async-action'
import type { Diff } from '../../api/types'

export type DiffSource =
  | { kind: 'worktree'; path: string; staged: boolean }
  | { kind: 'commit'; sha: string; path: string }

function load(source: DiffSource): Promise<Diff> {
  return source.kind === 'worktree'
    ? getDiff(source.path, source.staged)
    : getCommitDiff(source.sha, source.path)
}

export function DiffView({ source, revision }: { source: DiffSource; revision?: unknown }) {
  const [diff, setDiff] = useState<Diff | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { pending, run } = useAsyncAction()
  const key =
    source.kind === 'worktree'
      ? `w:${source.staged ? 1 : 0}:${source.path}`
      : `c:${source.sha}:${source.path}`
  // A commit's diff is immutable, so only a worktree diff tracks the caller's
  // revision. The backend pushes a snapshot only when something really changed,
  // so this refetches once per change rather than looping.
  const worktreeRevision = source.kind === 'worktree' ? revision : undefined

  useEffect(() => {
    let active = true
    setDiff(null)
    setError(null)
    load(source)
      .then((loaded) => {
        if (active) setDiff(loaded)
      })
      .catch((thrown: unknown) => {
        if (!active) return
        setError(thrown instanceof ApiError ? thrown.message : 'Could not load the diff')
      })
    return () => {
      active = false
    }
  }, [key, worktreeRevision])

  const openSplit = async (): Promise<void> => {
    if (source.kind !== 'worktree') return
    try {
      await openDiffSplit(source.path, source.staged)
    } catch (thrown) {
      if (thrown instanceof ApiError) {
        pushToast({
          tone: thrown.code === 'UNSUPPORTED' ? 'info' : 'error',
          message: thrown.message,
          detail: thrown.stderr || undefined,
        })
      } else throw thrown
    }
  }

  if (error !== null) return <div class="diff diff-error">{error}</div>
  if (diff === null) return <div class="diff muted">Loading…</div>

  return (
    <div class="diff">
      <div class="row diff-toolbar">
        <span class="grow path muted">{diff.path}</span>
        {source.kind === 'worktree' && (
          <button class="btn" disabled={pending} onClick={() => run(openSplit)}>
            Open in split
          </button>
        )}
      </div>
      {diff.binary && <div class="diff-note">Binary file</div>}
      {diff.truncated && (
        <div class="diff-note">Diff truncated at 5000 lines — open in split for the full diff</div>
      )}
      {diff.hunks.map((hunk) => (
        <div key={hunk.header} class="hunk">
          <div class="diff-line diff-header">
            <span class="grow">{hunk.header}</span>
          </div>
          {hunk.lines.map((line, index) => (
            <div key={index} class={`diff-line diff-${line.kind}`}>
              <span class="lineno">{line.old_no ?? ''}</span>
              <span class="lineno">{line.new_no ?? ''}</span>
              <span class="code">{line.text}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
