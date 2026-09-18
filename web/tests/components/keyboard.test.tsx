import { render, screen } from '@testing-library/preact'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import * as client from '../../src/api/client'
import { App } from '../../src/app'
import { applySnapshot } from '../../src/state/repo'
import { activeTab, askConfirm, selectedFile } from '../../src/state/ui'
import { makeSnapshot, resetState } from '../helpers'

describe('keyboard shortcuts', () => {
  beforeEach(() => {
    resetState()
    applySnapshot(
      makeSnapshot({
        staged: [{ path: 'staged.txt', orig_path: null, status: 'A' }],
        unstaged: [{ path: 'changed.txt', orig_path: null, status: 'M' }],
      }),
    )
    vi.spyOn(client, 'getBranches').mockResolvedValue({ local: [], remote: [] })
    vi.spyOn(client, 'getStash').mockResolvedValue({ entries: [] })
    vi.spyOn(client, 'getGraph').mockResolvedValue({ commits: [], next_cursor: null })
    vi.spyOn(client, 'getDiff').mockResolvedValue({
      path: 'x',
      binary: false,
      truncated: false,
      hunks: [],
    })
  })

  it('moves the selection with j and k', async () => {
    render(<App />)
    await userEvent.keyboard('j')
    expect(selectedFile.value).toEqual({ path: 'staged.txt', staged: true })

    await userEvent.keyboard('j')
    expect(selectedFile.value).toEqual({ path: 'changed.txt', staged: false })

    await userEvent.keyboard('k')
    expect(selectedFile.value).toEqual({ path: 'staged.txt', staged: true })
  })

  it('stages with s and unstages with u', async () => {
    const stage = vi.spyOn(client, 'stage').mockResolvedValue()
    const unstage = vi.spyOn(client, 'unstage').mockResolvedValue()
    render(<App />)

    selectedFile.value = { path: 'changed.txt', staged: false }
    await userEvent.keyboard('s')
    expect(stage).toHaveBeenCalledWith(['changed.txt'])

    selectedFile.value = { path: 'staged.txt', staged: true }
    await userEvent.keyboard('u')
    expect(unstage).toHaveBeenCalledWith(['staged.txt'])
  })

  it('switches tabs with the number keys and focuses the filter with /', async () => {
    render(<App />)
    await userEvent.keyboard('2')
    expect(activeTab.value).toBe('branches')

    await userEvent.keyboard('/')
    expect(screen.getByLabelText('Filter branches')).toHaveFocus()
  })

  it('ignores shortcuts while a dialog is open', async () => {
    const stage = vi.spyOn(client, 'stage').mockResolvedValue()
    render(<App />)

    selectedFile.value = { path: 'changed.txt', staged: false }
    void askConfirm({
      title: 'Discard changes?',
      body: 'The changes cannot be recovered.',
      choices: [{ id: 'discard', label: 'Discard', tone: 'danger' }],
    })
    await screen.findByRole('dialog')

    await userEvent.keyboard('s')
    await userEvent.keyboard('2')

    expect(stage).not.toHaveBeenCalled()
    expect(activeTab.value).toBe('changes')
  })

  it('ignores shortcuts while typing', async () => {
    render(<App />)
    const message = screen.getByLabelText('Commit message')
    await userEvent.type(message, 'js')
    expect(selectedFile.value).toBeNull()
    expect(message).toHaveValue('js')
  })
})
