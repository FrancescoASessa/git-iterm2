import { useEffect, useRef, useState } from 'preact/hooks'

import { ApiError, getGraph } from '../../api/client'
import type { GraphCommit } from '../../api/types'
import { snapshot } from '../../state/repo'
import { pushToast, selectedCommit } from '../../state/ui'
import { EmptyState } from '../common/empty-state'
import { VirtualList } from '../common/virtual-list'
import { CommitDetailView } from './commit-detail'
import { Lanes, ROW_HEIGHT } from './lanes'

function relativeTime(unixSeconds: number): string {
  const diff = Math.max(0, Date.now() / 1000 - unixSeconds)
  if (diff < 60) return 'now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d`
  if (diff < 86400 * 28) return `${Math.floor(diff / (86400 * 7))}w`
  return new Date(unixSeconds * 1000).toISOString().slice(0, 10)
}

// A commit can carry HEAD plus several branch and tag refs. Four chips ate
// the whole row and pushed the subject out of the panel; three ellipsised to
// unreadable stubs ("H…", "m…") at 240px. One readable chip plus a count of
// the rest is the most a narrow toolbelt can show honestly — the full list is
// the chip's tooltip, and the commit detail spells it out.
const MAX_REFS = 1

function GraphRow({ commit, maxLane }: { commit: GraphCommit; maxLane: number }) {
  const refs = commit.refs.slice(0, MAX_REFS)
  const hidden = commit.refs.length - refs.length
  return (
    <button
      class="row graph-row"
      onClick={() => {
        selectedCommit.value = commit.sha
      }}
    >
      <Lanes commit={commit} maxLane={maxLane} />
      <span class="sha muted">{commit.sha.slice(0, 7)}</span>
      {refs.map((ref) => (
        <span class="ref" key={ref}>
          {ref}
        </span>
      ))}
      {hidden > 0 && (
        <span class="ref ref-more" title={commit.refs.join(', ')}>
          +{hidden}
        </span>
      )}
      <span class="grow">{commit.subject}</span>
      <span class="time count">{relativeTime(commit.timestamp)}</span>
    </button>
  )
}

export function GraphPanel() {
  const [commits, setCommits] = useState<GraphCommit[]>([])
  const [cursor, setCursor] = useState<string | null>(null)
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const loadingRef = useRef(false)
  const generationRef = useRef(0)

  const head = snapshot.value?.head.branch ?? null
  const state = snapshot.value?.state ?? null

  async function loadPage(nextCursor: string | null, generation: number): Promise<void> {
    if (loadingRef.current) return
    loadingRef.current = true
    setLoading(true)
    try {
      const page = await getGraph(nextCursor, 200)
      if (generation !== generationRef.current) return
      setCommits((prev) => {
        if (nextCursor === null) return page.commits
        const seen = new Set(prev.map((existing) => existing.sha))
        return [...prev, ...page.commits.filter((next) => !seen.has(next.sha))]
      })
      setCursor(page.next_cursor)
      // page.next_cursor === nextCursor guards against a cursor that stopped advancing
      // (the backend never does this, but it keeps pagination from looping forever)
      setDone(page.next_cursor === null || page.next_cursor === nextCursor)
      setError(null)
    } catch (err) {
      if (generation !== generationRef.current) return
      if (err instanceof ApiError && err.code === 'STALE_CURSOR') {
        setCommits([])
        setCursor(null)
        setDone(false)
        loadingRef.current = false
        setLoading(false)
        pushToast({ tone: 'info', message: 'History changed — graph reloaded' })
        await loadPage(null, generation)
        return
      }
      if (err instanceof ApiError) {
        setError(err.message)
        // Stop paginating on a hard failure (e.g. the backend restarted, the
        // token was rejected) instead of busy-looping: VirtualList re-arms
        // onReachEnd on every render, so without a terminal flag the panel
        // would keep retrying the same failing request forever.
        setDone(true)
      } else {
        throw err
      }
    } finally {
      // Only clear the in-flight guard for the generation that owns it — a
      // stale (superseded) request's finally must not clear the flag the
      // current generation just set, or the panel can flash "No commits
      // yet" between a branch switch and its fresh page landing.
      if (generation === generationRef.current) {
        loadingRef.current = false
        setLoading(false)
      }
    }
  }

  useEffect(() => {
    generationRef.current += 1
    const generation = generationRef.current
    loadingRef.current = false
    setCommits([])
    setCursor(null)
    setDone(false)
    setError(null)
    void loadPage(null, generation)
    // reload whenever the checked-out branch or repo state changes
  }, [head, state])

  function handleReachEnd(): void {
    if (done || loadingRef.current) return
    void loadPage(cursor, generationRef.current)
  }

  const maxLane = commits.reduce((max, commit) => Math.max(max, commit.lane), 0)

  return (
    <div class="graph">
      {error !== null && <div class="diff-error">{error}</div>}
      {commits.length === 0 && !loading && error === null && <EmptyState title="No commits yet" />}
      {commits.length > 0 && (
        <VirtualList
          total={commits.length}
          rowHeight={ROW_HEIGHT}
          onReachEnd={handleReachEnd}
          renderRow={(index) => {
            const commit = commits[index]
            return commit === undefined ? null : (
              <GraphRow key={commit.sha} commit={commit} maxLane={maxLane} />
            )
          }}
        />
      )}
      {selectedCommit.value !== null && <CommitDetailView sha={selectedCommit.value} />}
    </div>
  )
}
