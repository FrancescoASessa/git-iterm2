import { describe, expect, it } from 'vitest'

import { startConnection } from '../../src/api/connect'
import { getToken } from '../../src/api/client'
import { connection, snapshot } from '../../src/state/repo'
import { runningOps } from '../../src/state/ops'
import type { ServerMessage } from '../../src/api/types'

type FakeSocket = {
  onopen: (() => void) | null
  onmessage: ((event: { data: string }) => void) | null
  onclose: (() => void) | null
  close: () => void
  send: () => void
}

describe('startConnection', () => {
  it('takes the token from the URL and routes messages into the signals', () => {
    window.history.replaceState(null, '', '/?t=from-url')
    const socketRef: { current: FakeSocket | null } = { current: null }
    const socketFactory = () => {
      const fake: FakeSocket = {
        onopen: null,
        onmessage: null,
        onclose: null,
        close: () => {},
        send: () => {},
      }
      socketRef.current = fake
      return fake as unknown as WebSocket
    }

    const handle = startConnection({
      socketFactory,
      timer: (() => 0) as unknown as typeof setTimeout,
    })

    expect(getToken()).toBe('from-url')
    expect(window.location.search).toBe('')

    const deliver = (message: ServerMessage) =>
      socketRef.current?.onmessage?.({ data: JSON.stringify(message) })
    socketRef.current?.onopen?.()
    expect(connection.value).toBe('open')

    deliver({
      type: 'snapshot',
      repo: {
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
      },
    })
    expect(snapshot.value?.root).toBe('/r')

    deliver({ type: 'op_progress', op_id: 'a', phase: 'p', pct: 5, line: 'l' })
    expect(runningOps.value).toHaveLength(1)

    deliver({ type: 'op_done', op_id: 'a', ok: true, error: null })
    expect(runningOps.value).toHaveLength(0)

    handle.close()
  })
})
