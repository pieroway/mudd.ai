import { expect, test } from '@playwright/test'

test('player enters the world and moves north', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill('Playwright')
  await page.getByTestId('login-button').click()

  await expect(page.getByText(/Online/)).toBeVisible()
  const transcript = page.getByTestId('transcript')
  await expect(transcript).toContainText(/You stand in the (Town Square|Forest)\./)

  if ((await transcript.textContent())?.includes('Forest')) {
    await page.getByTestId('command-input').fill('south')
    await page.getByTestId('command-input').press('Enter')
    await expect(transcript).toContainText('Town Square')
  }

  await page.getByTestId('command-input').fill('north')
  await page.getByTestId('command-input').press('Enter')

  await expect(transcript).toContainText('You move north.')
  await expect(transcript).toContainText('Forest')
})

test('a connected username cannot be used by another player', async ({ browser }) => {
  const firstPage = await browser.newPage()
  const secondPage = await browser.newPage()

  await firstPage.goto('/')
  await firstPage.getByTestId('username-input').fill('UniquePlaywright')
  await firstPage.getByTestId('login-button').click()
  await expect(firstPage.getByText(/Online/)).toBeVisible()

  await secondPage.goto('/')
  await secondPage.getByTestId('username-input').fill(' uniqueplaywright ')
  await secondPage.getByTestId('login-button').click()

  await expect(secondPage.getByTestId('transcript')).toContainText(
    '[ERROR] That username is already connected.',
  )
})
