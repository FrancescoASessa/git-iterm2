import { render, screen, waitFor } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ConfirmDialog } from '../../src/components/common/confirm-dialog'
import { ToastStack } from '../../src/components/common/toast'
import { RepoStateBanner } from '../../src/components/common/banner'
import * as client from '../../src/api/client'
import { applySnapshot } from '../../src/state/repo'
import { askConfirm, dialog, pushToast, toasts } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'

describe('ToastStack', () => {
  beforeEach(resetState)

  it('shows a toast, reveals the detail and dismisses it', async () => {
    render(<ToastStack />)
    pushToast({ tone: 'error', message: 'push rejected', detail: 'stderr text' })

    expect(await screen.findByText('push rejected')).toBeInTheDocument()
    expect(screen.queryByText('stderr text')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Details' }))
    expect(screen.getByText('stderr text')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    await waitFor(() => expect(toasts.value).toHaveLength(0))
  })
})

describe('ConfirmDialog', () => {
  beforeEach(resetState)

  it('resolves with the chosen id and closes', async () => {
    const user = userEvent.setup()
    render(<ConfirmDialog />)
    const choice = askConfirm({
      title: 'Discard changes?',
      body: '1 file will be reverted.',
      choices: [{ id: 'discard', label: 'Discard', tone: 'danger' }],
    })

    const dialog = await screen.findByRole('dialog')
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    await user.click(screen.getByRole('button', { name: 'Discard' }))

    await expect(choice).resolves.toBe('discard')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('resolves with null on Escape', async () => {
    render(<ConfirmDialog />)
    const escaped = askConfirm({ title: 't', body: 'b', choices: [{ id: 'ok', label: 'OK' }] })
    await screen.findByRole('dialog')
    // The keydown listener attaches in an effect after the dialog renders;
    // wait until the dispatched Escape is actually observed instead of
    // sleeping a fixed duration (flaky under load).
    await vi.waitFor(() => {
      document.dispatchEvent(
        new KeyboardEvent('keydown', {
          key: 'Escape',
          code: 'Escape',
          keyCode: 27,
          bubbles: true,
        }),
      )
      expect(dialog.value).toBeNull()
    })
    await expect(escaped).resolves.toBeNull()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('resolves with null on Cancel', async () => {
    const user = userEvent.setup()
    render(<ConfirmDialog />)
    const cancelled = askConfirm({ title: 't', body: 'b', choices: [{ id: 'ok', label: 'OK' }] })
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await expect(cancelled).resolves.toBeNull()
  })

  it('wraps Tab from the last button back to the first', async () => {
    const user = userEvent.setup()
    render(<ConfirmDialog />)
    askConfirm({
      title: 'Checkout main?',
      body: 'The working tree has local changes.',
      choices: [
        { id: 'stash', label: 'Stash and checkout' },
        { id: 'force', label: 'Discard changes', tone: 'danger' },
      ],
    })
    await screen.findByRole('dialog')

    const stash = screen.getByRole('button', { name: 'Stash and checkout' })
    const cancel = screen.getByRole('button', { name: 'Cancel' })
    // The auto-focus lands in an effect after the dialog renders.
    await waitFor(() => expect(stash).toHaveFocus())

    cancel.focus()
    await user.tab()
    expect(stash).toHaveFocus()
  })

  it('wraps Shift+Tab from the first button back to the last', async () => {
    const user = userEvent.setup()
    render(<ConfirmDialog />)
    askConfirm({
      title: 'Discard changes?',
      body: 'The changes cannot be recovered.',
      choices: [{ id: 'discard', label: 'Discard', tone: 'danger' }],
    })
    await screen.findByRole('dialog')

    await waitFor(() => expect(screen.getByRole('button', { name: 'Discard' })).toHaveFocus())
    await user.tab({ shift: true })
    expect(screen.getByRole('button', { name: 'Cancel' })).toHaveFocus()
  })

  it('keeps Tab inside the dialog when focus started behind it', async () => {
    const user = userEvent.setup()
    render(
      <>
        <button>behind</button>
        <ConfirmDialog />
      </>,
    )
    askConfirm({ title: 't', body: 'b', choices: [{ id: 'ok', label: 'OK' }] })
    await screen.findByRole('dialog')

    const behind = screen.getByRole('button', { name: 'behind' })
    behind.focus()
    await user.tab()
    expect(screen.getByRole('button', { name: 'OK' })).toHaveFocus()
    expect(behind).not.toHaveFocus()
  })

  it('resolves the first promise with null when a second dialog is requested while open', async () => {
    render(<ConfirmDialog />)
    const first = askConfirm({ title: 't1', body: 'b1', choices: [{ id: 'ok', label: 'OK' }] })
    await screen.findByRole('dialog')

    askConfirm({ title: 't2', body: 'b2', choices: [{ id: 'ok', label: 'OK' }] })

    await expect(first).resolves.toBeNull()
    expect(screen.getByRole('dialog')).toHaveTextContent('t2')
    expect(screen.queryByText('t1')).not.toBeInTheDocument()
  })
})

describe('RepoStateBanner', () => {
  beforeEach(resetState)

  it('offers continue and abort while merging', async () => {
    applySnapshot(makeSnapshot({ state: 'merging' }))
    const sequence = vi.spyOn(client, 'sequence').mockResolvedValue()
    render(<RepoStateBanner />)

    expect(screen.getByText(/merge in progress/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(sequence).toHaveBeenCalledWith('continue')

    await userEvent.click(screen.getByRole('button', { name: 'Abort' }))
    expect(sequence).toHaveBeenCalledWith('abort')
  })

  it('renders nothing when clean', () => {
    applySnapshot(makeSnapshot())
    const { container } = render(<RepoStateBanner />)
    expect(container).toBeEmptyDOMElement()
  })

  it('continues only once per button click burst', async () => {
    applySnapshot(makeSnapshot({ state: 'merging' }))
    let resolveSeq: (() => void) | undefined
    const sequenceCall = vi.spyOn(client, 'sequence').mockImplementation(
      () =>
        new Promise((res) => {
          resolveSeq = res
        }),
    )
    const user = userEvent.setup()
    render(<RepoStateBanner />)

    const button = screen.getByRole('button', { name: 'Continue' })
    await user.click(button)
    expect(button).toBeDisabled()
    expect(sequenceCall).toHaveBeenCalledTimes(1)

    await user.click(button)
    expect(sequenceCall).toHaveBeenCalledTimes(1)

    resolveSeq?.()
    await vi.waitFor(() => expect(button).not.toBeDisabled())
    expect(sequenceCall).toHaveBeenCalledTimes(1)
  })
})
