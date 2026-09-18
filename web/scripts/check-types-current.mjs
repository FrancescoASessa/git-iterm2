import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const dir = mkdtempSync(join(tmpdir(), 'git-iterm2-types-'))
const generated = join(dir, 'types.gen.ts')
try {
  execFileSync('npx', ['openapi-typescript', '../backend/openapi.json', '-o', generated], {
    stdio: 'inherit',
  })
  const fresh = readFileSync(generated, 'utf8')
  const committed = readFileSync('src/api/types.gen.ts', 'utf8')
  if (fresh !== committed) {
    console.error('src/api/types.gen.ts is stale: run `npm run gen:types`')
    process.exit(1)
  }
  console.log('src/api/types.gen.ts is current')
} finally {
  rmSync(dir, { recursive: true, force: true })
}
