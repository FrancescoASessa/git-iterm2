import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { BranchesPanel } from '../../src/components/branches/branches-panel'
import * as client from '../../src/api/client'
import { ApiError } from '../../src/api/client'
import { applySnapshot } from '../../src/state/repo'
import { dialog, resolveDialog, toasts } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'
import type { BranchInfo, Branches } from '../../src/api/types'

function branch(overrides: Partial<BranchInfo>): BranchInfo {
  return {
    name: 'main',
    full_ref: 'refs/heads/main',
    is_remote: false,
    is_current: false,
    upstream: null,
    ahead: null,
    behind: null,
    last_commit_sha: 'a'.repeat(40),
    last_commit_subject: 'initial',
    last_commit_ts: 1,
    ...overrides,
  }
}

const branches: Branches = {
  local: [
    branch({ name: 'main', is_current: true, upstream: 'origin/main', ahead: 1, behind: 0 }),
    branch({ name: 'feature/x', full_ref: 'refs/heads/feature/x' }),
  ],
  remote: [branch({ name: 'origin/main', full_ref: 'refs/remotes/origin/main', is_remote: true })],
}

describe('BranchesPanel', () => {
  beforeEach(() => {
    resetState()
    applySnapshot(makeSnapshot())
    vi.spyOn(client, 'getBranches').mockResolvedValue(branches)
  })

  it('lists local and remote branches and marks the current one', async () => {
    render(<BranchesPanel />)
    expect(await screen.findByText('feature/x')).toBeInTheDocument()
    expect(screen.getByText('origin/main')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^main/ })).toHaveAttribute('aria-current', 'true')
  })

  it('filters by name', async () => {
    render(<BranchesPanel />)
    await screen.findByText('feature/x')

    await userEvent.type(screen.getByLabelText('Filter branches'), 'feat')

    expect(screen.getByText('feature/x')).toBeInTheDocument()
    expect(screen.queryByText('origin/main')).not.toBeInTheDocument()
  })

  it('checks out a branch', async () => {
    const checkout = vi.spyOn(client, 'checkout').mockResolvedValue()
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByText('feature/x'))
    expect(checkout).toHaveBeenCalledWith({ branch: 'feature/x' })
  })

  it('offers stash or force when the tree is dirty', async () => {
    const checkout = vi
      .spyOn(client, 'checkout')
      .mockRejectedValueOnce(new ApiError('DIRTY_TREE', 'local changes', '', 409))
      .mockResolvedValue()
    const stashPush = vi.spyOn(client, 'stashPush').mockResolvedValue()
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByText('feature/x'))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    expect(dialog.value?.choices.map((choice) => choice.id)).toEqual(['stash', 'force'])

    resolveDialog('stash')
    await waitFor(() => expect(stashPush).toHaveBeenCalledWith('', true))
    expect(checkout).toHaveBeenLastCalledWith({ branch: 'feature/x' })
  })

  it('forces the checkout when asked', async () => {
    const checkout = vi
      .spyOn(client, 'checkout')
      .mockRejectedValueOnce(new ApiError('DIRTY_TREE', 'local changes', '', 409))
      .mockResolvedValue()
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByText('feature/x'))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('force')

    await waitFor(() =>
      expect(checkout).toHaveBeenLastCalledWith({ branch: 'feature/x', force: true }),
    )
  })

  it('creates a branch', async () => {
    const checkout = vi.spyOn(client, 'checkout').mockResolvedValue()
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByRole('button', { name: 'New branch' }))
    await userEvent.type(screen.getByLabelText('New branch name'), 'feature/y{Enter}')

    expect(checkout).toHaveBeenCalledWith({ create: 'feature/y' })
  })

  it('deletes a branch after confirmation and retries with force', async () => {
    const deleteBranch = vi
      .spyOn(client, 'deleteBranch')
      .mockRejectedValueOnce(new ApiError('GIT_FAILED', 'not fully merged', '', 500))
      .mockResolvedValue()
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete feature/x' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('delete')
    await waitFor(() => expect(deleteBranch).toHaveBeenCalledWith('feature/x', false))

    await waitFor(() => expect(dialog.value?.choices[0]?.id).toBe('force'))
    resolveDialog('force')
    await waitFor(() => expect(deleteBranch).toHaveBeenLastCalledWith('feature/x', true))
  })

  it('reports a locked delete without offering a force retry', async () => {
    const deleteBranch = vi
      .spyOn(client, 'deleteBranch')
      .mockRejectedValue(new ApiError('LOCKED', 'Another git process is running', '', 409))
    render(<BranchesPanel />)

    await userEvent.click(await screen.findByRole('button', { name: 'Delete feature/x' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('delete')
    await waitFor(() => expect(deleteBranch).toHaveBeenCalledWith('feature/x', false))

    await waitFor(() => expect(toasts.value[0]?.message).toBe('Another git process is running'))
    expect(dialog.value).toBeNull()
    expect(deleteBranch).toHaveBeenCalledOnce()
  })
})
