import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { StashPanel } from '../../src/components/stash/stash-panel'
import * as client from '../../src/api/client'
import { applySnapshot } from '../../src/state/repo'
import { dialog, resolveDialog } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'

const entries = {
  entries: [
    { index: 0, message: 'On main: wip', sha: 'a'.repeat(40), timestamp: 1700000000 },
    { index: 1, message: 'On main: older', sha: 'b'.repeat(40), timestamp: 1699999999 },
  ],
}

describe('StashPanel', () => {
  beforeEach(() => {
    resetState()
    applySnapshot(makeSnapshot({ stash_count: 2 }))
    vi.spyOn(client, 'getStash').mockResolvedValue(entries)
  })

  it('lists entries and applies one', async () => {
    const stashAction = vi.spyOn(client, 'stashAction').mockResolvedValue()
    render(<StashPanel />)

    expect(await screen.findByText('On main: wip')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Apply stash@{0}' }))
    expect(stashAction).toHaveBeenCalledWith(0, 'apply')
  })

  it('pushes a stash with a message and untracked files', async () => {
    const stashPush = vi.spyOn(client, 'stashPush').mockResolvedValue()
    render(<StashPanel />)
    await screen.findByText('On main: wip')

    await userEvent.type(screen.getByLabelText('Stash message'), 'wip work')
    await userEvent.click(screen.getByLabelText('Include untracked'))
    await userEvent.click(screen.getByRole('button', { name: 'Stash' }))

    expect(stashPush).toHaveBeenCalledWith('wip work', true)
  })

  it('confirms before dropping', async () => {
    const stashAction = vi.spyOn(client, 'stashAction').mockResolvedValue()
    render(<StashPanel />)
    await screen.findByText('On main: wip')

    await userEvent.click(screen.getByRole('button', { name: 'Drop stash@{1}' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('drop')

    await waitFor(() => expect(stashAction).toHaveBeenCalledWith(1, 'drop'))
  })

  it('shows an empty state', async () => {
    vi.spyOn(client, 'getStash').mockResolvedValue({ entries: [] })
    applySnapshot(makeSnapshot({ stash_count: 0 }))
    render(<StashPanel />)
    expect(await screen.findByText('No stashes')).toBeInTheDocument()
  })
})
