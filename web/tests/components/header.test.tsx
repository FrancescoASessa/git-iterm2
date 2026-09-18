import { render, screen } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { Header } from '../../src/components/header'
import * as client from '../../src/api/client'
import { runningOps } from '../../src/state/ops'
import { applySnapshot } from '../../src/state/repo'
import { makeSnapshot, resetState } from '../helpers'

describe('Header', () => {
  beforeEach(resetState)

  it('shows the branch and the upstream counters', () => {
    applySnapshot(makeSnapshot({ upstream: { name: 'origin/main', ahead: 2, behind: 1 } }))
    render(<Header />)

    expect(
      screen.getByText(
        (content, element) =>
          (element?.classList.contains('branch') ?? false) && content.includes('main'),
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('2 commits ahead of origin/main')).toHaveTextContent('↑2')
    expect(screen.getByLabelText('1 commit behind origin/main')).toHaveTextContent('↓1')
  })

  it('starts a remote operation', async () => {
    applySnapshot(makeSnapshot())
    const push = vi.spyOn(client, 'remoteOp').mockResolvedValue({ op_id: 'x' })
    render(<Header />)

    await userEvent.click(screen.getByRole('button', { name: 'Push' }))

    expect(push).toHaveBeenCalledWith('push')
  })

  it('disables the remote buttons and shows progress while busy', () => {
    applySnapshot(makeSnapshot())
    runningOps.value = [{ opId: 'x', phase: 'Receiving objects', pct: 42, line: '' }]
    render(<Header />)

    expect(screen.getByRole('button', { name: 'Fetch' })).toBeDisabled()
    expect(screen.getByText('Receiving objects 42%')).toBeInTheDocument()
  })

  it('keeps the remote buttons present but disabled without a repository', () => {
    applySnapshot(null)
    render(<Header />)
    expect(screen.getByRole('button', { name: 'Fetch' })).toBeDisabled()
  })

  it('starts only one remote operation per click burst', async () => {
    applySnapshot(makeSnapshot())
    let resolveOp: ((value: { op_id: string }) => void) | undefined
    const push = vi.spyOn(client, 'remoteOp').mockImplementation(
      () =>
        new Promise((res) => {
          resolveOp = res
        }),
    )
    render(<Header />)

    const button = screen.getByRole('button', { name: 'Push' })
    await userEvent.click(button)
    expect(button).toBeDisabled()
    expect(push).toHaveBeenCalledTimes(1)

    await userEvent.click(button)
    expect(push).toHaveBeenCalledTimes(1)

    resolveOp?.({ op_id: 'x' })
    await vi.waitFor(() => expect(button).not.toBeDisabled())
    expect(push).toHaveBeenCalledTimes(1)
  })
})
