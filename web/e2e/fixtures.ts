import { readFileSync } from 'node:fs'
import { test as base, expect, type Page } from '@playwright/test'

type Env = { baseURL: string; token: string; repo: string }

export const env = (): Env => JSON.parse(readFileSync('.e2e-env.json', 'utf8')) as Env

export const test = base.extend<{ panel: Page }>({
  panel: async ({ page }, use) => {
    const { baseURL, token } = env()
    await page.goto(`${baseURL}/?t=${token}`)
    await expect(page.getByRole('tab', { name: 'Changes' })).toBeVisible()
    await use(page)
  },
})

export { expect }
