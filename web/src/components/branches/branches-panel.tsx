import { useEffect, useState } from 'preact/hooks'

import {
  ApiError,
  checkout,
  deleteBranch,
  getBranches,
  renameBranch,
  setUpstream,
  stashPush,
} from '../../api/client'
import type { Branches } from '../../api/types'
import { snapshot } from '../../state/repo'
import { askConfirm, branchFilter, pushToast } from '../../state/ui'
import { EmptyState } from '../common/empty-state'
import { useAsyncAction } from '../common/use-async-action'
import { BranchList } from './branch-list'

function toastError(error: unknown): void {
  if (error instanceof ApiError) {
    pushToast({ tone: 'error', message: error.message, detail: error.stderr || undefined })
  } else {
    throw error
  }
}

async function withToast(action: () => Promise<void>): Promise<void> {
  try {
    await action()
  } catch (error) {
    toastError(error)
  }
}

function useBranches(reloadKey: number): { branches: Branches | null; error: string | null } {
  const [branches, setBranches] = useState<Branches | null>(null)
  const [error, setError] = useState<string | null>(null)
  const head = snapshot.value?.head.branch ?? null
  const state = snapshot.value?.state ?? null

  useEffect(() => {
    let cancelled = false
    getBranches()
      .then((result) => {
        if (cancelled) return
        setBranches(result)
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
    // reloadKey forces a reload after actions that don't otherwise change head/state
  }, [head, state, reloadKey])

  return { branches, error }
}

function matches(name: string, filter: string): boolean {
  return name.toLowerCase().includes(filter.trim().toLowerCase())
}

function NewBranchControl({ onCreate }: { onCreate: (name: string) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const { pending, run } = useAsyncAction()

  function close(): void {
    setOpen(false)
    setName('')
  }

  function submit(): void {
    const trimmed = name.trim()
    if (trimmed === '') return
    close()
    run(() => onCreate(trimmed))
  }

  if (!open) {
    return (
      <button class="btn" onClick={() => setOpen(true)}>
        New branch
      </button>
    )
  }

  return (
    <input
      aria-label="New branch name"
      value={name}
      disabled={pending}
      onInput={(event) => setName((event.target as HTMLInputElement).value)}
      onKeyDown={(event) => {
        if (event.key === 'Enter') submit()
        else if (event.key === 'Escape') close()
      }}
    />
  )
}

export function BranchesPanel() {
  const [reloadKey, setReloadKey] = useState(0)
  const { branches, error } = useBranches(reloadKey)
  const filter = branchFilter.value

  function reload(): void {
    setReloadKey((key) => key + 1)
  }

  async function checkoutBranch(name: string): Promise<void> {
    try {
      await checkout({ branch: name })
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'DIRTY_TREE') throw error
      const choice = await askConfirm({
        title: `Checkout ${name}?`,
        body: 'The working tree has local changes.',
        choices: [
          { id: 'stash', label: 'Stash and checkout' },
          { id: 'force', label: 'Discard changes', tone: 'danger' },
        ],
      })
      if (choice === 'stash') {
        await stashPush('', true)
        await checkout({ branch: name })
      } else if (choice === 'force') {
        await checkout({ branch: name, force: true })
      }
    }
  }

  function handleCheckout(name: string): Promise<void> {
    return withToast(() => checkoutBranch(name))
  }

  function handleCreate(name: string): Promise<void> {
    return withToast(() => checkout({ create: name }))
  }

  async function deleteBranchFlow(name: string): Promise<void> {
    const choice = await askConfirm({
      title: `Delete ${name}?`,
      body: 'This cannot be undone.',
      choices: [{ id: 'delete', label: 'Delete', tone: 'danger' }],
    })
    if (choice !== 'delete') return
    try {
      await deleteBranch(name, false)
      reload()
    } catch (error) {
      if (!(error instanceof ApiError)) throw error
      // Only git's "not fully merged" refusal is worth a force retry. A
      // LOCKED or UNAUTHORIZED failure must surface as an error instead of
      // inviting the user to force-delete the branch.
      if (!/not fully merged/i.test(error.message)) throw error
      const forceChoice = await askConfirm({
        title: `Delete ${name}?`,
        body: error.message,
        choices: [{ id: 'force', label: 'Delete anyway', tone: 'danger' }],
      })
      if (forceChoice !== 'force') return
      await deleteBranch(name, true)
      reload()
    }
  }

  function handleDelete(name: string): Promise<void> {
    return withToast(() => deleteBranchFlow(name))
  }

  function handleRename(oldName: string, newName: string): Promise<void> {
    return withToast(async () => {
      await renameBranch(oldName, newName)
      reload()
    })
  }

  function handleSetUpstream(name: string, upstream: string): Promise<void> {
    return withToast(async () => {
      await setUpstream(name, upstream)
      reload()
    })
  }

  const localAll = branches?.local ?? []
  const remoteAll = branches?.remote ?? []
  const local = localAll.filter((branch) => matches(branch.name, filter))
  const remote = remoteAll.filter((branch) => matches(branch.name, filter))

  return (
    <div class="branches">
      <div class="row filter-row">
        <input
          class="grow"
          aria-label="Filter branches"
          placeholder="Filter branches"
          value={filter}
          onInput={(event) => {
            branchFilter.value = (event.target as HTMLInputElement).value
          }}
        />
        <NewBranchControl onCreate={handleCreate} />
      </div>
      {error !== null && <div class="diff-error">{error}</div>}
      {branches !== null && localAll.length === 0 && remoteAll.length === 0 && (
        <EmptyState title="No branches" />
      )}
      <BranchList
        title="Local"
        branches={local}
        onCheckout={handleCheckout}
        actions={{
          onDelete: handleDelete,
          onRename: handleRename,
          onSetUpstream: handleSetUpstream,
        }}
      />
      <BranchList title="Remote" branches={remote} onCheckout={handleCheckout} />
    </div>
  )
}
