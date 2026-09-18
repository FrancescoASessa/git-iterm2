import { useState } from 'preact/hooks'

import type { BranchInfo } from '../../api/types'
import { useAsyncAction } from '../common/use-async-action'

export type BranchRowActions = {
  onDelete: (name: string) => Promise<void>
  onRename: (oldName: string, newName: string) => Promise<void>
  onSetUpstream: (name: string, upstream: string) => Promise<void>
}

type EditMode = 'rename' | 'upstream'

function BranchRow({
  branch,
  onCheckout,
  actions,
}: {
  branch: BranchInfo
  onCheckout: (name: string) => Promise<void>
  actions?: BranchRowActions
}) {
  const { pending, run } = useAsyncAction()
  const [editing, setEditing] = useState<EditMode | null>(null)
  const [value, setValue] = useState('')

  function startEditing(mode: EditMode): void {
    setValue(mode === 'rename' ? branch.name : (branch.upstream ?? ''))
    setEditing(mode)
  }

  function cancelEditing(): void {
    setEditing(null)
    setValue('')
  }

  function submitEditing(): void {
    if (editing === null || actions === undefined) return
    const trimmed = value.trim()
    const mode = editing
    setEditing(null)
    setValue('')
    if (trimmed === '') return
    if (mode === 'rename') {
      run(() => actions.onRename(branch.name, trimmed))
    } else {
      run(() => actions.onSetUpstream(branch.name, trimmed))
    }
  }

  return (
    <div class="row branch-row">
      <button
        class="grow"
        aria-current={branch.is_current ? 'true' : undefined}
        disabled={pending}
        onClick={() => run(() => onCheckout(branch.name))}
      >
        {branch.name}
      </button>
      {branch.ahead !== null && <span>↑{branch.ahead}</span>}
      {branch.behind !== null && <span>↓{branch.behind}</span>}
      {branch.last_commit_subject !== null && (
        <span class="muted">{branch.last_commit_subject}</span>
      )}
      {actions !== undefined && editing !== null && (
        <input
          aria-label={
            editing === 'rename' ? `New name for ${branch.name}` : `Upstream for ${branch.name}`
          }
          value={value}
          disabled={pending}
          onInput={(event) => setValue((event.target as HTMLInputElement).value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') submitEditing()
            else if (event.key === 'Escape') cancelEditing()
          }}
        />
      )}
      {actions !== undefined && editing === null && (
        <>
          <button
            disabled={pending}
            aria-label={`Rename ${branch.name}`}
            onClick={() => startEditing('rename')}
          >
            Rename
          </button>
          <button
            disabled={pending}
            aria-label={`Set upstream for ${branch.name}`}
            onClick={() => startEditing('upstream')}
          >
            Upstream
          </button>
          <button
            class="danger"
            disabled={pending}
            aria-label={`Delete ${branch.name}`}
            onClick={() => run(() => actions.onDelete(branch.name))}
          >
            Delete
          </button>
        </>
      )}
    </div>
  )
}

export function BranchList({
  title,
  branches,
  onCheckout,
  actions,
}: {
  title: string
  branches: BranchInfo[]
  onCheckout: (name: string) => Promise<void>
  actions?: BranchRowActions
}) {
  if (branches.length === 0) return null

  return (
    <section>
      <div class="row group-header">
        <span class="grow section-title">{`${title} (${branches.length})`}</span>
      </div>
      {branches.map((branch) => (
        <BranchRow
          key={branch.full_ref}
          branch={branch}
          onCheckout={onCheckout}
          actions={actions}
        />
      ))}
    </section>
  )
}
