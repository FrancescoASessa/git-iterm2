import { beforeEach, describe, expect, it, vi } from 'vitest'

import { readTokenFromLocation } from '../../src/api/token'

describe('readTokenFromLocation', () => {
  beforeEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('reads the token and removes it from the address bar', () => {
    window.history.replaceState(null, '', '/?t=secret-token')
    const replaceState = vi.spyOn(window.history, 'replaceState')

    expect(readTokenFromLocation()).toBe('secret-token')

    expect(replaceState).toHaveBeenCalledWith(null, '', '/')
    expect(window.location.search).toBe('')
  })

  it('returns an empty string when there is no token', () => {
    expect(readTokenFromLocation()).toBe('')
  })

  it('keeps other query parameters', () => {
    window.history.replaceState(null, '', '/?t=abc&debug=1')
    expect(readTokenFromLocation()).toBe('abc')
    expect(window.location.search).toBe('?debug=1')
  })
})
