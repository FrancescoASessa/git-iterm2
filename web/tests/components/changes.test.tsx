import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ChangesPanel } from '../../src/components/changes/changes-panel'
import * as client from '../../src/api/client'
import { ApiError } from '../../src/api/client'
import { applySnapshot } from '../../src/state/repo'
import { dialog, resolveDialog, selectedFile, toasts } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'

const emptyDiff = { path: 'changed.txt', binary: false, truncated: false, hunks: [] }

const dirty = () =>
  makeSnapshot({
    staged: [{ path: 'staged.txt', orig_path: null, status: 'A' }],
    unstaged: [{ path: 'changed.txt', orig_path: null, status: 'M' }],
    untracked: ['new.txt'],
    conflicted: [{ path: 'conflict.txt', orig_path: null, status: 'U' }],
  })

describe('ChangesPanel', () => {
  beforeEach(() => {
    resetState()
    applySnapshot(dirty())
  })

  it('groups files with counts', () => {
    // The count is no longer baked into the title string ("Staged (1)"): it
    // is a separate element so it can be aligned to the right edge of the
    // header row. Assert both halves, and that they sit in the same row.
    render(<ChangesPanel />)
    for (const title of ['Conflicts', 'Staged', 'Changes', 'Untracked']) {
      const header = screen.getByRole('button', { name: title })
      expect(header).toHaveAttribute('aria-expanded', 'true')
      const row = header.parentElement
      expect(row).not.toBeNull()
      expect(row?.querySelector('.count')).toHaveTextContent('1')
    }
    expect(screen.getByText('changed.txt')).toBeInTheDocument()
  })

  it('stages and unstages single files', async () => {
    const stage = vi.spyOn(client, 'stage').mockResolvedValue()
    const unstage = vi.spyOn(client, 'unstage').mockResolvedValue()
    render(<ChangesPanel />)

    await userEvent.click(screen.getByRole('button', { name: 'Stage changed.txt' }))
    expect(stage).toHaveBeenCalledWith(['changed.txt'])

    await userEvent.click(screen.getByRole('button', { name: 'Unstage staged.txt' }))
    expect(unstage).toHaveBeenCalledWith(['staged.txt'])
  })

  it('stages a whole group', async () => {
    const stage = vi.spyOn(client, 'stage').mockResolvedValue()
    render(<ChangesPanel />)
    await userEvent.click(screen.getByRole('button', { name: 'Stage all changes' }))
    expect(stage).toHaveBeenCalledWith(['changed.txt'])
  })

  it('selects a file for the diff view', async () => {
    render(<ChangesPanel />)
    await userEvent.click(screen.getByText('changed.txt'))
    expect(selectedFile.value).toEqual({ path: 'changed.txt', staged: false })
  })

  it('asks before discarding and skips when cancelled', async () => {
    const discard = vi.spyOn(client, 'discard').mockResolvedValue()
    render(<ChangesPanel />)

    await userEvent.click(screen.getByRole('button', { name: 'Discard changed.txt' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog(null)
    expect(discard).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: 'Discard changed.txt' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('discard')
    await waitFor(() => expect(discard).toHaveBeenCalledWith(['changed.txt']))
  })

  it('commits with the typed message and clears it', async () => {
    const commit = vi.spyOn(client, 'commit').mockResolvedValue()
    render(<ChangesPanel />)

    const message = screen.getByLabelText('Commit message')
    await userEvent.type(message, 'add things')
    await userEvent.click(screen.getByRole('button', { name: 'Commit' }))

    expect(commit).toHaveBeenCalledWith('add things', false)
    await waitFor(() => expect(message).toHaveValue(''))
  })

  it('commits with Cmd+Enter and supports amend', async () => {
    const commit = vi.spyOn(client, 'commit').mockResolvedValue()
    render(<ChangesPanel />)

    await userEvent.click(screen.getByLabelText('Amend'))
    await userEvent.type(screen.getByLabelText('Commit message'), 'fixed{Meta>}{Enter}{/Meta}')

    expect(commit).toHaveBeenCalledWith('fixed', true)
  })

  it('shows a toast when the commit fails', async () => {
    vi.spyOn(client, 'commit').mockRejectedValue(
      new ApiError('INVALID_ARGUMENT', 'Nothing staged to commit', '', 400),
    )
    render(<ChangesPanel />)

    await userEvent.type(screen.getByLabelText('Commit message'), 'x')
    await userEvent.click(screen.getByRole('button', { name: 'Commit' }))

    await waitFor(() => expect(toasts.value[0]?.message).toBe('Nothing staged to commit'))
  })

  it('shows an empty state on a clean repo', () => {
    applySnapshot(makeSnapshot())
    render(<ChangesPanel />)
    expect(screen.getByText('No changes')).toBeInTheDocument()
  })

  it('renders renames as old → new', () => {
    applySnapshot(
      makeSnapshot({ staged: [{ path: 'new name.txt', orig_path: 'old name.txt', status: 'R' }] }),
    )
    render(<ChangesPanel />)
    expect(screen.getByText('old name.txt → new name.txt')).toBeInTheDocument()
  })

  it('stages a file only once per click burst', async () => {
    const resolvePromiseRef: { current: (() => void) | null } = { current: null }
    const promise = new Promise<void>((resolve) => {
      resolvePromiseRef.current = resolve
    })
    const stage = vi.spyOn(client, 'stage').mockReturnValue(promise)
    render(<ChangesPanel />)

    const button = screen.getByRole('button', { name: 'Stage changed.txt' })
    await userEvent.click(button)
    await userEvent.click(button)

    expect(stage).toHaveBeenCalledOnce()
    expect(button).toHaveAttribute('disabled')

    resolvePromiseRef.current?.()
    await waitFor(() => expect(button).not.toHaveAttribute('disabled'))
  })

  it('stages a group only once per click burst', async () => {
    const resolvePromiseRef: { current: (() => void) | null } = { current: null }
    const promise = new Promise<void>((resolve) => {
      resolvePromiseRef.current = resolve
    })
    const stage = vi.spyOn(client, 'stage').mockReturnValue(promise)
    render(<ChangesPanel />)

    const button = screen.getByRole('button', { name: 'Stage all changes' })
    await userEvent.click(button)
    await userEvent.click(button)

    expect(stage).toHaveBeenCalledOnce()
    expect(button).toHaveAttribute('disabled')

    resolvePromiseRef.current?.()
    await waitFor(() => expect(button).not.toHaveAttribute('disabled'))
  })

  it('opens diff in split on double-click', async () => {
    const openSplit = vi.spyOn(client, 'openDiffSplit').mockResolvedValue()
    render(<ChangesPanel />)

    const pathButton = screen.getByRole('button', { name: 'changed.txt' })
    await userEvent.dblClick(pathButton)

    expect(openSplit).toHaveBeenCalledWith('changed.txt', false)
  })

  it('reloads the diff on the staged side after the file is staged', async () => {
    const getDiff = vi.spyOn(client, 'getDiff').mockResolvedValue(emptyDiff)
    vi.spyOn(client, 'stage').mockResolvedValue()
    render(<ChangesPanel />)

    await userEvent.click(screen.getByText('changed.txt'))
    await waitFor(() => expect(getDiff).toHaveBeenCalledWith('changed.txt', false))

    await userEvent.click(screen.getByRole('button', { name: 'Stage changed.txt' }))
    // The backend answers a stage with a fresh snapshot; the panel must follow
    // the selection to the staged side instead of keeping the cached diff.
    applySnapshot(
      makeSnapshot({
        staged: [{ path: 'changed.txt', orig_path: null, status: 'M' }],
        untracked: ['new.txt'],
      }),
    )

    await waitFor(() => expect(getDiff).toHaveBeenCalledWith('changed.txt', true))
    expect(selectedFile.value).toEqual({ path: 'changed.txt', staged: true })
  })

  it('refetches the diff when a new snapshot arrives', async () => {
    const getDiff = vi.spyOn(client, 'getDiff').mockResolvedValue(emptyDiff)
    render(<ChangesPanel />)

    await userEvent.click(screen.getByText('changed.txt'))
    await waitFor(() => expect(getDiff).toHaveBeenCalledTimes(1))

    applySnapshot(dirty())
    await waitFor(() => expect(getDiff).toHaveBeenCalledTimes(2))
    expect(getDiff).toHaveBeenLastCalledWith('changed.txt', false)
  })

  it('drops the diff box when the selected file is discarded', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue(emptyDiff)
    vi.spyOn(client, 'discard').mockResolvedValue()
    const { container } = render(<ChangesPanel />)

    await userEvent.click(screen.getByText('changed.txt'))
    await waitFor(() => expect(container.querySelector('.diff')).not.toBeNull())

    await userEvent.click(screen.getByRole('button', { name: 'Discard changed.txt' }))
    await waitFor(() => expect(dialog.value).not.toBeNull())
    resolveDialog('discard')
    await waitFor(() => expect(client.discard).toHaveBeenCalledWith(['changed.txt']))

    // Other changes remain, so the panel stays mounted; only the diff goes.
    applySnapshot(
      makeSnapshot({
        staged: [{ path: 'staged.txt', orig_path: null, status: 'A' }],
        untracked: ['new.txt'],
      }),
    )

    await waitFor(() => expect(selectedFile.value).toBeNull())
    expect(container.querySelector('.diff')).toBeNull()
  })

  it('opens a split only once per double-click burst', async () => {
    const resolvePromiseRef: { current: (() => void) | null } = { current: null }
    const promise = new Promise<void>((resolve) => {
      resolvePromiseRef.current = resolve
    })
    const openSplit = vi.spyOn(client, 'openDiffSplit').mockReturnValue(promise)
    render(<ChangesPanel />)

    const pathButton = screen.getByRole('button', { name: 'changed.txt' })
    await userEvent.dblClick(pathButton)
    await userEvent.dblClick(pathButton)

    expect(openSplit).toHaveBeenCalledOnce()
    expect(openSplit).toHaveBeenCalledWith('changed.txt', false)

    resolvePromiseRef.current?.()
    await waitFor(() => expect(openSplit).toHaveBeenCalledOnce())
  })
})
