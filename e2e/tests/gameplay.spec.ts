import { expect, test } from '@playwright/test'

test('account persists across reload, rejects wrong password, and signs out', async ({ page }) => {
  const username = `Auth-${Date.now()}`
  await page.goto('/')
  await page.getByTestId('register-toggle').click()
  await page.getByTestId('username-input').fill(username)
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()
  await expect(page.getByText(/Online/)).toBeVisible()
  await page.getByTestId('command-input').fill('north')
  await page.getByTestId('command-input').press('Enter')
  await expect(page.getByTestId('transcript')).toContainText('You move north.')
  await page.reload()
  await expect(page.getByTestId('transcript')).toContainText('You stand in the Forest.')
  await page.getByTestId('logout-button').click()
  await expect(page.getByTestId('username-input')).toBeVisible()
  await page.getByTestId('username-input').fill(username)
  await page.getByTestId('password-input').fill('This is the wrong password')
  await page.getByTestId('login-button').click()
  await expect(page.getByRole('alert')).toContainText('Invalid username or password.')
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()
  await expect(page.getByTestId('transcript')).toContainText('You stand in the Forest.')
})

test('player enters the world and moves north', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill('Playwright')
  await page.getByTestId('register-toggle').click()
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
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
  await page.getByTestId('register-toggle').click()
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()

  const terminal = page.getByTestId('terminal')
  const transcript = page.getByTestId('transcript')
  const commandInput = page.getByTestId('command-input')
  await expect(page.getByText(/Online/)).toBeVisible()

  await commandInput.fill('look')
  await commandInput.press('Enter')
  await expect(terminal).toHaveAttribute('data-command-source', 'classic')
  await expect(page.getByTestId('ai-allowance')).toContainText('20/20 remaining')

  await commandInput.fill('walk toward the docks')
  await commandInput.press('Enter')
  await expect(transcript).toContainText('You move south.')
  await expect(transcript).toContainText('Docks')
  await expect(page.getByTestId('ai-allowance')).toContainText('19/20 remaining')
  await expect(terminal).toHaveAttribute('data-command-source', 'ai')

  await commandInput.fill('perform an undocumented action')
  await commandInput.press('Enter')
  await expect(transcript).toContainText(
    "I couldn't interpret that command. Try 'help' for available commands.",
  )
  await expect(page.getByTestId('ai-allowance')).toContainText('18/20 remaining')
  await expect(terminal).toHaveAttribute('data-command-source', 'ai')
})

test('player can toggle safe debug diagnostics in the transcript', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill(`DebugPlaywright-${Date.now()}`)
  await page.getByTestId('register-toggle').click()
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
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
  await firstPage.getByTestId('register-toggle').click()
  await firstPage.getByTestId('password-input').fill('A long test-only passphrase1!')
  await firstPage.getByTestId('login-button').click()
  await expect(firstPage.getByText(/Online/)).toBeVisible()

  await secondPage.goto('/')
  await secondPage.getByTestId('username-input').fill(' uniqueplaywright ')
  await secondPage.getByTestId('password-input').fill('A long test-only passphrase1!')
  await secondPage.getByTestId('login-button').click()

  await expect(secondPage.getByTestId('transcript')).toContainText(
    '[ERROR] That username is already connected.',
  )
})

test('player can open and close a persistent item', async ({ page }) => {
  await page.goto('/')
  await page.getByTestId('username-input').fill('ItemPlaywright')
  await page.getByTestId('register-toggle').click()
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()

  const transcript = page.getByTestId('transcript')
  await expect(transcript).toContainText(/You stand in the (Town Square|Forest)\./)
  const commandInput = page.getByTestId('command-input')
  const send = async (command: string, expected: string | RegExp) => {
    const previousLines = await transcript.locator('.transcript-line').count()
    await expect(commandInput).toBeEnabled()
    // Pace keyboard input below the server's command limit and assert a fresh reply.
    await commandInput.pressSequentially(command, { delay: 50 })
    await commandInput.press('Enter')
    await expect(transcript.locator('.transcript-line').nth(previousLines + 1)).toContainText(expected)
    await expect(transcript).not.toContainText('[ERROR]')
    await expect(commandInput).toBeEnabled()
  }

  if ((await transcript.textContent())?.includes('Forest')) {
    await send('south', 'You move south.')
  }
  await send('close chest', /The chest is already closed|You close the chest/)
  await send('open chest', 'You open the chest.')
  await send('take torch', 'You take the torch.')
  await send('put torch in chest', 'You put the torch in the chest.')
  await send('look in chest', 'The chest contains: torch.')
  await send('take torch from chest', 'You take the torch from the chest.')
  await send('use torch', 'The torch casts a steady pool of light.')
  await send('look', 'Torchlight reaches farther.')
  await send('put torch in chest', 'You must extinguish the torch before putting it in the chest.')
  await send('put out torch', 'You extinguish the torch.')
  await send('use torch', 'The torch casts a steady pool of light.')
  await send('drop torch', 'You drop the torch. It goes out.')
})
