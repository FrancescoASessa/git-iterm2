import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { GraphPanel } from '../../src/components/graph/graph-panel'
import * as client from '../../src/api/client'
import { ApiError } from '../../src/api/client'
import { applySnapshot } from '../../src/state/repo'
import { selectedCommit, toasts } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'
import type { GraphCommit, GraphPage } from '../../src/api/types'

function commit(index: number, overrides: Partial<GraphCommit> = {}): GraphCommit {
  return {
    sha: String(index).padStart(40, '0'),
    parents: [],
    author: 'Ann',
    timestamp: 1700000000,
    subject: `commit ${index}`,
    refs: [],
    lane: 0,
    edges: [],
    ...overrides,
  }
}

const page1: GraphPage = {
  commits: [commit(1, { refs: ['HEAD', 'main'] }), commit(2)],
  next_cursor: 'cur',
}
const page2: GraphPage = { commits: [commit(3)], next_cursor: null }

describe('GraphPanel', () => {
  beforeEach(() => {
    resetState()
    applySnapshot(makeSnapshot())
  })

  it('renders commits with refs and selects one', async () => {
    vi.spyOn(client, 'getGraph').mockResolvedValue(page1)
    render(<GraphPanel />)

    expect(await screen.findByText('commit 1')).toBeInTheDocument()
    expect(screen.getByText('HEAD')).toBeInTheDocument()
    expect(screen.getByText('main')).toBeInTheDocument()

    await userEvent.click(screen.getByText('commit 2'))
    expect(selectedCommit.value).toBe(page1.commits[1]?.sha)
  })

  it('appends the next page when the end is reached', async () => {
    const getGraph = vi
      .spyOn(client, 'getGraph')
      .mockResolvedValueOnce(page1)
      .mockResolvedValueOnce(page2)
    render(<GraphPanel />)
    await screen.findByText('commit 2')

    // the list is short enough that the end is already visible
    await waitFor(() => expect(getGraph).toHaveBeenCalledWith('cur', 200))
    expect(await screen.findByText('commit 3')).toBeInTheDocument()
  })

  it('reloads from the top on STALE_CURSOR', async () => {
    const getGraph = vi
      .spyOn(client, 'getGraph')
      .mockResolvedValueOnce(page1)
      .mockRejectedValueOnce(
        new ApiError('STALE_CURSOR', 'Graph changed; reload from the top', '', 409),
      )
      .mockResolvedValueOnce({ commits: [commit(9)], next_cursor: null })
    render(<GraphPanel />)

    await screen.findByText('commit 1')
    await waitFor(() => expect(screen.queryByText('commit 1')).not.toBeInTheDocument())
    expect(await screen.findByText('commit 9')).toBeInTheDocument()
    expect(getGraph).toHaveBeenLastCalledWith(null, 200)
    expect(toasts.value[0]?.tone).toBe('info')
  })

  it('stops paginating after a page error', async () => {
    const getGraph = vi
      .spyOn(client, 'getGraph')
      .mockResolvedValueOnce(page1)
      .mockRejectedValueOnce(new ApiError('GIT_FAILED', 'boom', '', 0))
    render(<GraphPanel />)

    await screen.findByText('commit 1')
    await screen.findByText('boom')

    // give any runaway reach-end-triggered retries a couple of turns to (not) happen
    await new Promise((resolve) => setTimeout(resolve, 0))
    await new Promise((resolve) => setTimeout(resolve, 0))

    expect(getGraph).toHaveBeenCalledTimes(2)
    expect(screen.getByText('commit 1')).toBeInTheDocument()
    expect(screen.getByText('commit 2')).toBeInTheDocument()
  })

  it('shows an empty state for a repository without commits', async () => {
    vi.spyOn(client, 'getGraph').mockResolvedValue({ commits: [], next_cursor: null })
    render(<GraphPanel />)
    expect(await screen.findByText('No commits yet')).toBeInTheDocument()
  })
})
