import { beforeEach, describe, expect, it } from 'vitest'

import { handleOpDone, handleOpProgress, isBusy, runningOps } from '../../src/state/ops'
import { toasts } from '../../src/state/ui'

describe('ops state', () => {
  beforeEach(() => {
    runningOps.value = []
    toasts.value = []
  })

  it('tracks progress per op', () => {
    handleOpProgress({
      type: 'op_progress',
      op_id: 'a',
      phase: 'Receiving objects',
      pct: 10,
      line: 'x',
    })
    handleOpProgress({
      type: 'op_progress',
      op_id: 'a',
      phase: 'Receiving objects',
      pct: 60,
      line: 'y',
    })
    handleOpProgress({
      type: 'op_progress',
      op_id: 'b',
      phase: 'Resolving deltas',
      pct: null,
      line: 'z',
    })

    expect(isBusy.value).toBe(true)
    expect(runningOps.value).toEqual([
      { opId: 'a', phase: 'Receiving objects', pct: 60, line: 'y' },
      { opId: 'b', phase: 'Resolving deltas', pct: null, line: 'z' },
    ])
  })

  it('clears an op on success without a toast', () => {
    handleOpProgress({ type: 'op_progress', op_id: 'a', phase: '', pct: null, line: '' })
    handleOpDone({ type: 'op_done', op_id: 'a', ok: true, error: null })

    expect(runningOps.value).toEqual([])
    expect(isBusy.value).toBe(false)
    expect(toasts.value).toEqual([])
  })

  it('reports a failure as an error toast with the stderr detail', () => {
    handleOpProgress({ type: 'op_progress', op_id: 'a', phase: '', pct: null, line: '' })
    handleOpDone({
      type: 'op_done',
      op_id: 'a',
      ok: false,
      error: { code: 'AUTH_REQUIRED', message: 'could not read Username', stderr: 'fatal: ...' },
    })

    expect(runningOps.value).toEqual([])
    expect(toasts.value).toHaveLength(1)
    expect(toasts.value.at(0)?.tone).toBe('error')
    expect(toasts.value.at(0)?.message).toContain('could not read Username')
    expect(toasts.value.at(0)?.detail).toBe('fatal: ...')
  })
})
