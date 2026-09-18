import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const ENV_FILE = resolve('.e2e-env.json')

function git(cwd: string, ...args: string[]): void {
  execFileSync('git', args, {
    cwd,
    env: {
      ...process.env,
      GIT_AUTHOR_NAME: 'E2E',
      GIT_AUTHOR_EMAIL: 'e2e@example.com',
      GIT_COMMITTER_NAME: 'E2E',
      GIT_COMMITTER_EMAIL: 'e2e@example.com',
    },
  })
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  const repo = mkdtempSync(join(tmpdir(), 'git-iterm2-e2e-'))
  git(repo, 'init', '-q', '-b', 'main')
  writeFileSync(join(repo, 'README.md'), 'hello\n')
  git(repo, 'add', 'README.md')
  git(repo, 'commit', '-q', '-m', 'initial')
  git(repo, 'branch', 'feature')
  writeFileSync(join(repo, 'README.md'), 'hello\nworld\n')
  writeFileSync(join(repo, 'untracked.txt'), 'u\n')

  const server = spawn(
    'uv',
    [
      'run',
      'python',
      '-m',
      'git_iterm2.standalone',
      '--repo',
      repo,
      '--token',
      'e2e-token',
      '--static',
      resolve('dist'),
      '--poll-interval',
      '0.2',
    ],
    { cwd: resolve('..', 'backend'), stdio: ['ignore', 'pipe', 'inherit'] },
  )

  let baseURL: string
  try {
    baseURL = await new Promise<string>((resolvePromise, reject) => {
      const timeout = setTimeout(() => reject(new Error('backend did not start')), 20_000)
      server.stdout.on('data', (chunk: Buffer) => {
        const match = /http:\/\/127\.0\.0\.1:(\d+)\//.exec(chunk.toString())
        if (match) {
          clearTimeout(timeout)
          resolvePromise(`http://127.0.0.1:${match[1]}`)
        }
      })
    })
  } catch (error) {
    // The startup wait failed (most likely the 20s timeout) before the
    // teardown closure below was ever returned to Playwright, so nothing
    // else will kill the spawned backend or clean up the temp repo. Do it
    // here instead of leaking a running process and a directory.
    server.kill('SIGTERM')
    rmSync(repo, { recursive: true, force: true })
    throw error
  }

  writeFileSync(ENV_FILE, JSON.stringify({ baseURL, token: 'e2e-token', repo }))

  return async () => {
    server.kill('SIGTERM')
    rmSync(ENV_FILE, { force: true })
    rmSync(repo, { recursive: true, force: true })
  }
}
