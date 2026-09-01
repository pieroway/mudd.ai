import { expect, test } from '@playwright/test'

test('player enters the world and moves north', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill('Playwright')
  await page.getByTestId('login-button').click()

  await expect(page.getByText(/Online/)).toBeVisible()
  await page.getByTestId('command-input').fill('north')
  await page.getByTestId('command-input').press('Enter')

  await expect(page.getByTestId('transcript')).toContainText('You move north.')
  await expect(page.getByTestId('transcript')).toContainText('Forest')
})
