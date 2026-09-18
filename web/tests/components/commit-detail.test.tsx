import { render, screen } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { CommitDetailView } from '../../src/components/graph/commit-detail'
import * as client from '../../src/api/client'
import { ApiError } from '../../src/api/client'
import { selectedCommit, toasts } from '../../src/state/ui'
import { resetState } from '../helpers'
import type { CommitDetail, Diff } from '../../src/api/types'

const detail: CommitDetail = {
  sha: 'abc1234def5678'.padEnd(40, '0'),
  parents: ['f'.repeat(40)],
  author: 'Ann',
  email: 'ann@example.com',
  timestamp: 1700000000,
  subject: 'add feature',
  body: 'line one\nline two',
  files: [
    { path: 'a.txt', orig_path: null, status: 'M' },
    { path: 'b.txt', orig_path: null, status: 'A' },
  ],
}

const diff: Diff = {
  path: 'a.txt',
  binary: false,
  truncated: false,
  hunks: [
    {
      header: '@@ -1 +1 @@',
      old_start: 1,
      old_lines: 1,
      new_start: 1,
      new_lines: 1,
      lines: [{ kind: 'add', text: 'hello', old_no: null, new_no: 1 }],
    },
  ],
}

describe('CommitDetailView', () => {
  beforeEach(resetState)

  it('shows metadata, files and the per-file diff', async () => {
    vi.spyOn(client, 'getCommit').mockResolvedValue(detail)
    const getCommitDiff = vi.spyOn(client, 'getCommitDiff').mockResolvedValue(diff)
    render(<CommitDetailView sha={detail.sha} />)

    expect(await screen.findByText('add feature')).toBeInTheDocument()
    expect(screen.getByText(/Ann/)).toBeInTheDocument()
    expect(screen.getByText(/line one/)).toBeInTheDocument()
    expect(screen.getByText(detail.sha.slice(0, 7))).toBeInTheDocument()

    await userEvent.click(screen.getByText('a.txt'))
    await vi.waitFor(() => expect(getCommitDiff).toHaveBeenCalledWith(detail.sha, 'a.txt'))
    expect(await screen.findByText('hello')).toBeInTheDocument()
  })

  it('closes', async () => {
    vi.spyOn(client, 'getCommit').mockResolvedValue(detail)
    selectedCommit.value = detail.sha
    render(<CommitDetailView sha={detail.sha} />)

    await userEvent.click(await screen.findByRole('button', { name: 'Close commit' }))
    expect(selectedCommit.value).toBeNull()
  })

  it('can be closed while loading', async () => {
    vi.spyOn(client, 'getCommit').mockReturnValue(new Promise(() => {}))
    selectedCommit.value = detail.sha
    render(<CommitDetailView sha={detail.sha} />)

    expect(screen.getByText('Loading…')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close commit' }))
    expect(selectedCommit.value).toBeNull()
  })

  it('can be closed after a load error', async () => {
    vi.spyOn(client, 'getCommit').mockRejectedValue(
      new ApiError('INVALID_ARGUMENT', 'Not a commit: x', '', 400),
    )
    selectedCommit.value = detail.sha
    render(<CommitDetailView sha={detail.sha} />)

    expect(await screen.findByText('Not a commit: x')).toBeInTheDocument()
    expect(toasts.value).toHaveLength(0)
    await userEvent.click(screen.getByRole('button', { name: 'Close commit' }))
    expect(selectedCommit.value).toBeNull()
  })
})
