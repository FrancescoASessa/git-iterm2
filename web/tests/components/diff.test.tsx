import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DiffView } from '../../src/components/diff/diff-view'
import * as client from '../../src/api/client'
import { ApiError } from '../../src/api/client'
import { toasts } from '../../src/state/ui'
import { resetState } from '../helpers'
import type { Diff } from '../../src/api/types'

const diff: Diff = {
  path: 'a.txt',
  binary: false,
  truncated: false,
  hunks: [
    {
      header: '@@ -1,2 +1,2 @@',
      old_start: 1,
      old_lines: 2,
      new_start: 1,
      new_lines: 2,
      lines: [
        { kind: 'context', text: 'one', old_no: 1, new_no: 1 },
        { kind: 'del', text: 'two', old_no: 2, new_no: null },
        { kind: 'add', text: 'TWO', old_no: null, new_no: 2 },
      ],
    },
  ],
}

describe('DiffView', () => {
  beforeEach(resetState)

  it('renders hunk lines with line numbers', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue(diff)
    render(<DiffView source={{ kind: 'worktree', path: 'a.txt', staged: false }} />)

    expect(await screen.findByText('@@ -1,2 +1,2 @@')).toBeInTheDocument()
    const added = screen.getByText('TWO')
    expect(added.closest('.diff-line')).toHaveClass('diff-add')
    expect(screen.getByText('two').closest('.diff-line')).toHaveClass('diff-del')
    expect(client.getDiff).toHaveBeenCalledWith('a.txt', false)
  })

  it('renders a binary notice', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue({ ...diff, binary: true, hunks: [] })
    render(<DiffView source={{ kind: 'worktree', path: 'i.png', staged: false }} />)
    expect(await screen.findByText('Binary file')).toBeInTheDocument()
  })

  it('warns when the diff is truncated', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue({ ...diff, truncated: true })
    render(<DiffView source={{ kind: 'worktree', path: 'a.txt', staged: false }} />)
    expect(await screen.findByText(/truncated/i)).toBeInTheDocument()
  })

  it('opens the diff in a split', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue(diff)
    const open = vi.spyOn(client, 'openDiffSplit').mockResolvedValue()
    render(<DiffView source={{ kind: 'worktree', path: 'a.txt', staged: true }} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Open in split' }))
    expect(open).toHaveBeenCalledWith('a.txt', true)
  })

  it('explains that split needs iTerm2', async () => {
    vi.spyOn(client, 'getDiff').mockResolvedValue(diff)
    vi.spyOn(client, 'openDiffSplit').mockRejectedValue(
      new ApiError('UNSUPPORTED', 'Opening a split requires iTerm2', '', 501),
    )
    render(<DiffView source={{ kind: 'worktree', path: 'a.txt', staged: false }} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Open in split' }))
    await waitFor(() => expect(toasts.value[0]?.tone).toBe('info'))
    expect(toasts.value[0]?.message).toMatch(/requires iTerm2/)
  })

  it('shows a load error inline', async () => {
    vi.spyOn(client, 'getDiff').mockRejectedValue(
      new ApiError('INVALID_PATH', 'Invalid path', '', 400),
    )
    render(<DiffView source={{ kind: 'worktree', path: '../x', staged: false }} />)
    expect(await screen.findByText('Invalid path')).toBeInTheDocument()
    expect(toasts.value).toHaveLength(0)
  })

  it('loads a commit diff without the split button', async () => {
    vi.spyOn(client, 'getCommitDiff').mockResolvedValue(diff)
    render(<DiffView source={{ kind: 'commit', sha: 'abc1234', path: 'a.txt' }} />)

    await screen.findByText('one')
    expect(client.getCommitDiff).toHaveBeenCalledWith('abc1234', 'a.txt')
    expect(screen.queryByRole('button', { name: 'Open in split' })).not.toBeInTheDocument()
  })

  it('opens a split only once per click burst', async () => {
    const resolvePromiseRef: { current: (() => void) | null } = { current: null }
    const promise = new Promise<void>((resolve) => {
      resolvePromiseRef.current = resolve
    })
    vi.spyOn(client, 'getDiff').mockResolvedValue(diff)
    const open = vi.spyOn(client, 'openDiffSplit').mockReturnValue(promise)
    render(<DiffView source={{ kind: 'worktree', path: 'a.txt', staged: false }} />)

    const button = await screen.findByRole('button', { name: 'Open in split' })
    await userEvent.click(button)
    await userEvent.click(button)

    expect(open).toHaveBeenCalledOnce()
    expect(button).toHaveAttribute('disabled')

    resolvePromiseRef.current?.()
    await waitFor(() => expect(button).not.toHaveAttribute('disabled'))
  })
})
