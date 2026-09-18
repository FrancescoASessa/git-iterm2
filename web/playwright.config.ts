import { defineConfig } from '@playwright/test'

// GitHub Actions (and every other CI) sets CI=1. Everything keyed on this
// stays off for a local `npm run e2e`: no retries hiding a real failure, no
// HTML report to clean up, no artifact writing between runs.
const isCI = !!process.env.CI

export default defineConfig({
  testDir: './e2e',
  globalSetup: './e2e/global-setup.ts',
  timeout: 30_000,
  expect: { timeout: 5_000 },
  // A stray `test.only` silently shrinks the suite to one spec. Locally that
  // is the point; in CI it means a green run that tested almost nothing.
  forbidOnly: isCI,
  // One retry in CI, and only in CI. It is also what makes the trace below
  // possible: a trace is recorded on the retry, so a green run pays nothing
  // for it. A test that only passes on the retry is reported as "flaky", not
  // quietly as a pass.
  retries: isCI ? 1 : 0,
  // The HTML report is what the failure artifact uploaded by the e2e job is
  // built around; `open: 'never'` stops Playwright trying to serve it on a
  // runner with no browser to open it in.
  reporter: isCI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    headless: true,
    // Written only while a failed test is being retried, so the cost lands on
    // runs that are already red. `npx playwright show-trace` on the uploaded
    // artifact replays the run: DOM snapshots, network, console.
    trace: 'on-first-retry',
    // Captured at the moment of failure only; passing tests never screenshot.
    screenshot: 'only-on-failure',
    // 'on-first-retry' rather than 'retain-on-failure': the latter records
    // video for *every* test and throws it away when the test passes, which
    // taxes green runs to produce nothing.
    video: 'on-first-retry',
  },
  // Default locations, restated because the CI artifact upload and .gitignore
  // both name them: outputDir holds traces/screenshots/videos,
  // playwright-report holds the HTML report.
  outputDir: './test-results',
})
