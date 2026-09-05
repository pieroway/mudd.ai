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

test('natural commands use AI fallback while classic commands bypass it', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill(`NaturalPlaywright-${Date.now()}`)
  await page.getByTestId('login-button').click()

  const terminal = page.getByTestId('terminal')
  const transcript = page.getByTestId('transcript')
  const commandInput = page.getByTestId('command-input')
  await expect(page.getByText(/Online/)).toBeVisible()

  await commandInput.fill('look')
  await commandInput.press('Enter')
  await expect(terminal).toHaveAttribute('data-command-source', 'classic')

  await commandInput.fill('walk toward the docks')
  await commandInput.press('Enter')
  await expect(transcript).toContainText('You move south.')
  await expect(transcript).toContainText('Docks')
  await expect(terminal).toHaveAttribute('data-command-source', 'ai')

  await commandInput.fill('perform an undocumented action')
  await commandInput.press('Enter')
  await expect(transcript).toContainText(
    "I couldn't interpret that command. Try 'help' for available commands.",
  )
  await expect(terminal).toHaveAttribute('data-command-source', 'ai')
})

test('player can toggle safe debug diagnostics in the transcript', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill(`DebugPlaywright-${Date.now()}`)
  await page.getByTestId('login-button').click()

  const terminal = page.getByTestId('terminal')
  const transcript = page.getByTestId('transcript')
  const commandInput = page.getByTestId('command-input')
  await expect(page.getByText(/Online/)).toBeVisible()

  await commandInput.fill('/debug on')
  await commandInput.press('Enter')
  await expect(terminal).toHaveAttribute('data-debug', 'on')

  await commandInput.fill('look')
  await commandInput.press('Enter')
  await expect(transcript).toContainText(
    '[DEBUG] type=game_output success=true room_id=town_square command_source=classic',
  )

  await commandInput.fill('/debug off')
  await commandInput.press('Enter')
  await expect(terminal).toHaveAttribute('data-debug', 'off')
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
