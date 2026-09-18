import { render, screen } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../src/app'
import * as client from '../src/api/client'
import { applySnapshot, connection } from '../src/state/repo'
import { FALLBACK_THEME } from '../src/theme'
import { makeSnapshot, resetState } from './helpers'
import type { RepoSnapshot } from '../src/api/types'

describe('app shell', () => {
  afterEach(() => {
    connection.value = 'connecting'
  })

  it('renders the four tabs', () => {
    render(<App />)
    const tabs = screen.getAllByRole('tab').map((tab) => tab.textContent)
    expect(tabs).toEqual(['Changes', 'Branches', 'Graph', 'Stash'])
  })

  it('shows a reconnecting banner once the socket has closed', () => {
    connection.value = 'closed'
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Disconnected — reconnecting…')
  })

  it('shows an unauthorized banner without reconnecting wording', () => {
    connection.value = 'unauthorized'
    render(<App />)
    const banner = screen.getByRole('status')
    expect(banner).toHaveTextContent('Unauthorized — reopen the panel from iTerm2')
    expect(banner.textContent).not.toMatch(/reconnecting/i)
  })

  it('exposes the fallback theme and the snapshot type', () => {
    expect(FALLBACK_THEME.ansi).toHaveLength(16)
    const snapshot: RepoSnapshot = {
      root: '/r',
      head: { branch: 'main', detached_sha: null },
      upstream: null,
      state: 'clean',
      staged: [],
      unstaged: [],
      untracked: [],
      conflicted: [],
      stash_count: 0,
      theme: null,
      shell_integration: true,
    }
    expect(snapshot.head.branch).toBe('main')
  })
})

describe('app first paint', () => {
  beforeEach(() => {
    resetState()
    connection.value = 'connecting'
  })

  afterEach(() => {
    connection.value = 'connecting'
  })

  it('shows Loading… and no banner before the first snapshot', () => {
    render(<App />)
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByText('Not a git repository')).not.toBeInTheDocument()
  })

  it('shows the no-repo empty state once the first snapshot is null', async () => {
    render(<App />)
    applySnapshot(null)
    expect(await screen.findByText('Not a git repository')).toBeInTheDocument()
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
  })

  it('explains how to enable shell integration when the panel has no path', async () => {
    render(<App />)
    // Drive it through the real mechanism rather than poking the signal
    // directly: a repo snapshot with the flag false, then losing the repo
    // (a null snapshot), which must carry the flag forward rather than
    // resetting it.
    applySnapshot(makeSnapshot({ shell_integration: false }))
    applySnapshot(null)
    expect(await screen.findByText('Shell Integration not enabled')).toBeInTheDocument()
    expect(screen.getByText(/Install Shell Integration/)).toBeInTheDocument()
  })

  it('shows the Changes panel once a repository snapshot arrives', async () => {
    render(<App />)
    applySnapshot(makeSnapshot())
    expect(await screen.findByText('No changes')).toBeInTheDocument()
    expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
  })

  it('shows the reconnecting banner for a closed socket', () => {
    connection.value = 'closed'
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Disconnected — reconnecting…')
  })

  it('shows the unauthorized banner for an unauthorized socket', () => {
    connection.value = 'unauthorized'
    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent(
      'Unauthorized — reopen the panel from iTerm2',
    )
  })

  it('keeps the loading placeholder on a tab other than Changes', async () => {
    const getBranches = vi.spyOn(client, 'getBranches').mockResolvedValue({ local: [], remote: [] })
    render(<App />)
    await userEvent.click(screen.getByRole('tab', { name: 'Branches' }))
    expect(screen.getByText('Loading…')).toBeInTheDocument()
    expect(getBranches).not.toHaveBeenCalled()
  })
})
