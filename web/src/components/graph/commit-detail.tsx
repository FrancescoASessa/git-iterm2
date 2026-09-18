import { useEffect, useState } from 'preact/hooks'

import { ApiError, getCommit } from '../../api/client'
import { selectedCommit } from '../../state/ui'
import { DiffView } from '../diff/diff-view'
import type { CommitDetail } from '../../api/types'

export function CommitDetailView({ sha }: { sha: string }) {
  const [detail, setDetail] = useState<CommitDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [path, setPath] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setDetail(null)
    setError(null)
    setPath(null)
    getCommit(sha)
      .then((loaded) => {
        if (active) setDetail(loaded)
      })
      .catch((thrown: unknown) => {
        if (!active) return
        setError(thrown instanceof ApiError ? thrown.message : 'Could not load the commit')
      })
    return () => {
      active = false
    }
  }, [sha])

  const shortSha = sha.slice(0, 7)

  return (
    <div class="diff">
      <div class="row diff-toolbar">
        <span class="grow">
          <span class="muted">{shortSha}</span>
          {detail !== null && <span>{detail.subject}</span>}
        </span>
        <button
          aria-label="Close commit"
          onClick={() => {
            selectedCommit.value = null
          }}
        >
          Close
        </button>
      </div>
      {error !== null && <div class="diff-error">{error}</div>}
      {detail === null && error === null && <div class="muted">Loading…</div>}
      {detail !== null && (
        <>
          <div class="row muted commit-meta">
            {detail.author} &lt;{detail.email}&gt; ·{' '}
            {new Date(detail.timestamp * 1000).toLocaleString()}
          </div>
          {detail.body && <pre class="commit-body">{detail.body}</pre>}
          <div class="commit-files">
            {detail.files.map((file) => (
              <button key={file.path} class="row file-row" onClick={() => setPath(file.path)}>
                <span class={`status status-${file.status}`}>{file.status}</span>
                <span class="path">{file.path}</span>
              </button>
            ))}
          </div>
          {path !== null && (
            <DiffView key={`${sha}:${path}`} source={{ kind: 'commit', sha, path }} />
          )}
        </>
      )}
    </div>
  )
}
