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

test('player can open and close a persistent item', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill('ItemPlaywright')
  await page.getByTestId('login-button').click()

  const transcript = page.getByTestId('transcript')
  await expect(transcript).toContainText(/You stand in the (Town Square|Forest)\./)
  if ((await transcript.textContent())?.includes('Forest')) {
    await page.getByTestId('command-input').fill('south')
    await page.getByTestId('command-input').press('Enter')
    await expect(transcript).toContainText('You move south.')
  }

  await page.getByTestId('command-input').fill('close chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText(/The chest is already closed|You close the chest/)

  await page.getByTestId('command-input').fill('open chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You open the chest.')

  await page.getByTestId('command-input').fill('take torch')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You take the torch.')

  await page.getByTestId('command-input').fill('put torch in chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You put the torch in the chest.')

  await page.getByTestId('command-input').fill('look in chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('The chest contains: torch.')

  await page.getByTestId('command-input').fill('take torch from chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You take the torch from the chest.')

  await page.getByTestId('command-input').fill('use torch')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('The torch casts a steady pool of light.')

  await page.getByTestId('command-input').fill('look')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('Torchlight reaches farther.')

  await page.getByTestId('command-input').fill('put torch in chest')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText(
    'You must extinguish the torch before putting it in the chest.',
  )

  await page.getByTestId('command-input').fill('put out torch')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You extinguish the torch.')

  await page.getByTestId('command-input').fill('use torch')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('The torch casts a steady pool of light.')

  await page.getByTestId('command-input').fill('drop torch')
  await page.getByTestId('command-input').press('Enter')
  await expect(transcript).toContainText('You drop the torch. It goes out.')
})
