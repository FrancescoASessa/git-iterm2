import { writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { env, expect, test } from './fixtures'

// These specs share one backend and one temp repo (see global-setup.ts) and run
// sequentially within this file (Playwright's default, fullyParallel is not set).
// Ordering is deliberate and each test depends on the state left by the ones
// before it: commit README.md on `main` -> modify README.md again on disk,
// view its (tracked) diff, then discard it to leave a clean tree -> view the
// untracked file's diff -> switch to `feature` -> create and check out a new
// branch from `feature` -> stash/restore the remaining untracked file. Keep
// this order if you add specs.

test('removes the token from the address bar', async ({ panel }) => {
  await expect.poll(() => panel.evaluate(() => window.location.search)).toBe('')
})

test('stages a file and commits it', async ({ panel }) => {
  // The group header is a title button plus a right-aligned `.count`, not a
  // single "Staged (1)" string, so the count is asserted on its own element.
  // `exact` matters: "Unstage all staged" also contains "Staged".
  const stagedGroup = panel.getByRole('button', { name: 'Staged', exact: true })
  await panel.getByRole('button', { name: 'Stage README.md' }).click()
  await expect(stagedGroup).toBeVisible()
  await expect(panel.locator('.group-header', { has: stagedGroup }).locator('.count')).toHaveText(
    '1',
  )

  await panel.getByLabel('Commit message').fill('e2e commit')
  await panel.getByRole('button', { name: 'Commit' }).click()

  // The commit clears the staged group (deviation from the brief: the brief's
  // `await expect(...).toBeHidden(...).catch(() => undefined)` line is a no-op
  // assertion — a failed toBeHidden is swallowed by the .catch — so it never
  // proves the commit happened. Assert on the real state instead.
  await expect(stagedGroup).toBeHidden()

  await panel.getByRole('tab', { name: 'Graph' }).click()
  await expect(panel.getByText('e2e commit')).toBeVisible()
})

test('shows a diff for a tracked, modified file', async ({ panel }) => {
  // README.md was staged and committed by the previous test, so it is a
  // clean tracked file at this point; modify it again on disk (not through
  // the UI) to exercise a genuinely tracked-and-modified diff, as opposed to
  // the untracked-file diff the next test covers.
  const { repo } = env()
  writeFileSync(join(repo, 'README.md'), 'hello\nworld\nagain\n')

  await panel.getByRole('tab', { name: 'Changes' }).click()
  // The backend polls the repo (--poll-interval 0.2s in global-setup.ts) and
  // pushes the updated snapshot over the websocket; wait for that round trip
  // instead of the file row being present at first paint.
  await expect(panel.getByRole('button', { name: 'Stage README.md' })).toBeVisible()

  await panel.getByText('README.md').click()
  await expect(panel.locator('.diff-line.diff-add .code')).toHaveText('again')
  await expect(panel.locator('.diff-line.diff-context').first()).toBeVisible()

  // Restore a clean working tree: the later "checks out another branch" spec
  // switches to `feature`, whose committed README.md differs from main's —
  // git refuses that checkout while README.md has uncommitted local changes
  // of its own. Discarding here keeps this spec's on-disk edit from leaking
  // into (and breaking) specs that run after it.
  await panel.getByRole('button', { name: 'Discard README.md' }).click()
  await panel.getByRole('dialog').getByRole('button', { name: 'Discard' }).click()
  await expect(panel.getByRole('button', { name: 'Stage README.md' })).toBeHidden()
})

test('shows a diff for an untracked file', async ({ panel }) => {
  // Renamed from the brief's "shows a diff for a modified file": the body
  // clicks `untracked.txt`, which is an added/untracked file, not a modified
  // one (README.md is the modified file, already committed by the previous
  // test). The title now matches what the test actually exercises.
  await panel.getByRole('tab', { name: 'Changes' }).click()
  await panel.getByText('untracked.txt').click()
  // Deviation: the brief's `getByText('u', { exact: true })` is ambiguous —
  // it can match unrelated single-character text elsewhere on the page. Scope
  // to the rendered diff's added line instead, which is unambiguous.
  await expect(panel.locator('.diff-line.diff-add .code')).toHaveText('u')
})

test('checks out another branch', async ({ panel }) => {
  await panel.getByRole('tab', { name: 'Branches' }).click()
  // Deviation: swapped the brief's `getByText('feature')` for a role-scoped,
  // exact locator. Without `exact: true` this also matches the row's
  // "Rename feature" / "Set upstream for feature" / "Delete feature" action
  // buttons (their accessible names contain "feature" as a substring),
  // producing a strict-mode violation.
  await panel.getByRole('button', { name: 'feature', exact: true }).click()
  await expect(panel.getByText('⎇ feature')).toBeVisible()
})

test('creates and checks out a new branch', async ({ panel }) => {
  // Runs after the checkout spec, so HEAD is on `feature`; the new branch is
  // created from there and becomes current.
  await panel.getByRole('tab', { name: 'Branches' }).click()
  await panel.getByRole('button', { name: 'New branch' }).click()
  await panel.getByLabel('New branch name').fill('e2e/created')
  await panel.getByLabel('New branch name').press('Enter')

  await expect(panel.getByText('⎇ e2e/created')).toBeVisible()
  await expect(panel.getByRole('button', { name: 'e2e/created', exact: true })).toBeVisible()
})

test('stashes and restores the working tree', async ({ panel }) => {
  await panel.getByRole('tab', { name: 'Stash' }).click()
  await panel.getByLabel('Stash message').fill('e2e stash')
  await panel.getByLabel('Include untracked').check()
  await panel.getByRole('button', { name: 'Stash' }).click()

  await expect(panel.getByText(/e2e stash/)).toBeVisible()
  await panel.getByRole('button', { name: 'Pop stash@{0}' }).click()
  await expect(panel.getByText('No stashes')).toBeVisible()
})

// 240px and 320px are the two widths the toolbelt is actually used at, and
// they are where this layout breaks: every control has to stay inside the
// panel, with no horizontal page scroll. These specs are read-only and placed
// last on purpose — they only resize and read, so they leave the shared repo
// exactly as the stash spec left it and do not disturb the ordering above.
for (const width of [240, 320]) {
  test(`keeps every control reachable at ${width}px`, async ({ panel }) => {
    await panel.setViewportSize({ width, height: 600 })
    try {
      const noOverflow = async (): Promise<void> => {
        expect(
          await panel.evaluate(() => document.documentElement.scrollWidth),
        ).toBeLessThanOrEqual(width)
      }

      // Header: the segmented remote group must not be pushed out by a long
      // head label, and all four tabs stay on one segmented control.
      await expect(panel.getByRole('button', { name: 'Push' })).toBeInViewport()
      for (const name of ['Changes', 'Branches', 'Graph', 'Stash']) {
        await expect(panel.getByRole('tab', { name })).toBeInViewport()
      }
      await noOverflow()

      await panel.getByRole('tab', { name: 'Changes' }).click()
      await expect(panel.getByRole('button', { name: 'Commit' })).toBeInViewport()
      await expect(panel.getByRole('button', { name: 'Stage untracked.txt' })).toBeInViewport()
      await noOverflow()

      await panel.getByRole('tab', { name: 'Branches' }).click()
      await expect(panel.getByRole('button', { name: 'Delete main' })).toBeInViewport()
      await expect(panel.getByRole('button', { name: 'New branch' })).toBeInViewport()
      await noOverflow()

      await panel.getByRole('tab', { name: 'Graph' }).click()
      // The list is virtualised, so assert on the first row rather than a
      // particular subject that may be scrolled out of the window.
      const row = panel.locator('.graph-row').first()
      await expect(row).toBeInViewport()
      expect((await row.boundingBox())?.width ?? width + 1).toBeLessThanOrEqual(width)
      await noOverflow()

      await panel.getByRole('tab', { name: 'Stash' }).click()
      await expect(panel.getByRole('button', { name: 'Stash', exact: true })).toBeInViewport()
      await noOverflow()
    } finally {
      await panel.setViewportSize({ width: 1280, height: 720 })
    }
  })
}

test('renders a diff with surface tints rather than ANSI backgrounds', async ({ panel }) => {
  // Read-only, and the last of the appearance specs: it asserts the rendered
  // result of the colour model, which no unit test can reach — a diff line's
  // tint is mixed from the panel's surface, so it must differ from the page
  // background without being an opaque terminal colour.
  await panel.getByRole('tab', { name: 'Changes' }).click()
  await panel.getByText('untracked.txt').click()

  const added = panel.locator('.diff-line.diff-add').first()
  await expect(added).toBeVisible()

  const colors = await added.evaluate((node) => ({
    line: getComputedStyle(node).backgroundColor,
    body: getComputedStyle(document.body).backgroundColor,
    mono: getComputedStyle(node).fontFamily,
    ui: getComputedStyle(document.body).fontFamily,
  }))
  expect(colors.line).not.toBe(colors.body)
  expect(colors.line).not.toBe('rgba(0, 0, 0, 0)')
  // Diff content stays monospace; the surrounding UI does not.
  expect(colors.mono).not.toBe(colors.ui)
})

test('serves the built assets from the backend', async ({ panel }) => {
  const { baseURL } = env()
  const response = await panel.request.get(`${baseURL}/`)
  expect(response.ok()).toBe(true)
  expect(await response.text()).toContain('<div id="root">')
})
