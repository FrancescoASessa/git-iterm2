import type {
  Branches,
  CommitDetail,
  Diff,
  ErrorBody,
  ErrorCode,
  GraphPage,
  OpStarted,
  StashList,
} from './types'

let token = ''

export function setToken(value: string): void {
  token = value
}

export function getToken(): string {
  return token
}

export class ApiError extends Error {
  readonly code: ErrorCode
  readonly stderr: string
  readonly status: number

  constructor(code: ErrorCode, message: string, stderr: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.stderr = stderr
    this.status = status
  }
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as ErrorBody).code === 'string' &&
    typeof (value as ErrorBody).message === 'string'
  )
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      method: init?.method ?? 'GET',
      headers: {
        'X-Token': token,
        ...(init?.body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...init?.headers,
      },
    })
  } catch (cause) {
    throw new ApiError(
      'GIT_FAILED',
      cause instanceof Error ? cause.message : 'Request failed',
      '',
      0,
    )
  }

  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    if (isErrorBody(body)) {
      throw new ApiError(body.code, body.message, body.stderr ?? '', response.status)
    }
    throw new ApiError('GIT_FAILED', `Request failed (${response.status})`, '', response.status)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

function post<T = void>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function getDiff(path: string, staged: boolean): Promise<Diff> {
  const query = new URLSearchParams({ path, staged: String(staged) })
  return request<Diff>(`/api/diff?${query}`)
}

export function getBranches(): Promise<Branches> {
  return request<Branches>('/api/branches')
}

export function getGraph(cursor: string | null, limit = 200): Promise<GraphPage> {
  const query = new URLSearchParams({ limit: String(limit) })
  if (cursor !== null) query.set('cursor', cursor)
  return request<GraphPage>(`/api/graph?${query}`)
}

export function getCommit(sha: string): Promise<CommitDetail> {
  return request<CommitDetail>(`/api/commit/${encodeURIComponent(sha)}`)
}

export function getCommitDiff(sha: string, path: string): Promise<Diff> {
  const query = new URLSearchParams({ path })
  return request<Diff>(`/api/commit/${encodeURIComponent(sha)}/diff?${query}`)
}

export function getStash(): Promise<StashList> {
  return request<StashList>('/api/stash')
}

export const stage = (paths: string[]): Promise<void> => post('/api/stage', { paths })
export const unstage = (paths: string[]): Promise<void> => post('/api/unstage', { paths })
export const discard = (paths: string[]): Promise<void> => post('/api/discard', { paths })
export const commit = (message: string, amend = false): Promise<void> =>
  post('/api/commit', { message, amend })
export const checkout = (body: {
  branch?: string
  create?: string
  start_point?: string
  force?: boolean
}): Promise<void> => post('/api/checkout', body)
export const renameBranch = (oldName: string, newName: string): Promise<void> =>
  post('/api/branch/rename', { old_name: oldName, new_name: newName })
export const deleteBranch = (name: string, force = false): Promise<void> =>
  post('/api/branch/delete', { name, force })
export const setUpstream = (name: string, upstream: string): Promise<void> =>
  post('/api/branch/upstream', { name, upstream })
export const stashPush = (message: string, includeUntracked: boolean): Promise<void> =>
  post('/api/stash/push', { message, include_untracked: includeUntracked })
export const stashAction = (index: number, action: 'apply' | 'pop' | 'drop'): Promise<void> =>
  post(`/api/stash/${action}`, { index })
export const remoteOp = (op: 'fetch' | 'pull' | 'push'): Promise<OpStarted> =>
  post<OpStarted>(`/api/${op}`)
export const sequence = (action: 'continue' | 'abort'): Promise<void> =>
  post(`/api/sequence/${action}`)
export const openDiffSplit = (path: string, staged: boolean): Promise<void> =>
  post('/api/open-diff-split', { path, staged })
