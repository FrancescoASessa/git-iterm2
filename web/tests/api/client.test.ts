import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  ApiError,
  commit,
  getDiff,
  getGraph,
  remoteOp,
  setToken,
  stage,
} from '../../src/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

describe('api client', () => {
  beforeEach(() => setToken('tok'))

  it('sends the token and parses the payload', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ path: 'a.txt', binary: false, truncated: false, hunks: [] }),
      )
    vi.stubGlobal('fetch', fetchMock)

    const diff = await getDiff('a.txt', true)

    expect(diff.path).toBe('a.txt')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/diff?path=a.txt&staged=true',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ 'X-Token': 'tok' }),
      }),
    )
  })

  it('encodes query parameters', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ path: 'a b.txt', binary: false, truncated: false, hunks: [] }),
      )
    vi.stubGlobal('fetch', fetchMock)
    await getDiff('dir/a b.txt', false)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/diff?path=dir%2Fa+b.txt&staged=false',
      expect.any(Object),
    )
  })

  it('posts JSON bodies and accepts 204', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)

    await stage(['a.txt', 'b.txt'])

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/stage',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ paths: ['a.txt', 'b.txt'] }),
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
      }),
    )
  })

  it('throws ApiError carrying code, message, stderr and status', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ code: 'DIRTY_TREE', message: 'local changes', stderr: 'error: ...' }, 409),
        ),
    )

    const error = await commit('x').catch((thrown: unknown) => thrown)

    expect(error).toBeInstanceOf(ApiError)
    const apiError = error as ApiError
    expect(apiError.code).toBe('DIRTY_TREE')
    expect(apiError.message).toBe('local changes')
    expect(apiError.stderr).toBe('error: ...')
    expect(apiError.status).toBe(409)
  })

  it('falls back to GIT_FAILED when the body is not an ErrorBody', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('boom', { status: 500 })))
    const error = (await commit('x').catch((thrown: unknown) => thrown)) as ApiError
    expect(error.code).toBe('GIT_FAILED')
    expect(error.status).toBe(500)
  })

  it('maps a network failure to GIT_FAILED', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    const error = (await commit('x').catch((thrown: unknown) => thrown)) as ApiError
    expect(error.code).toBe('GIT_FAILED')
    expect(error.status).toBe(0)
  })

  it('omits the cursor when null and returns the page', async () => {
    const page = { commits: [], next_cursor: null }
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(page)))
    vi.stubGlobal('fetch', fetchMock)

    await getGraph(null)
    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/graph?limit=200', expect.any(Object))

    await getGraph('cur+sor', 50)
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/graph?limit=50&cursor=cur%2Bsor',
      expect.any(Object),
    )
  })

  it('returns the op id for remote operations', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ op_id: 'abc' }, 202)))
    expect(await remoteOp('fetch')).toEqual({ op_id: 'abc' })
  })
})
