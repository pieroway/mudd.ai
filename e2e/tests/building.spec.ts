import { expect, test } from '@playwright/test'

test('complete building has connected floors and basements after approval and reload', async ({ page }) => {
  test.setTimeout(90000)
  await page.goto('/')
  await page.getByTestId('username-input').fill('BuildingAdmin')
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()
  const room = page.getByTestId('current-room')
  await expect(room).toHaveText('Building Lot')
  const input = page.getByTestId('command-input')
  const transcript = page.getByTestId('transcript')
  const send = async (command: string, expected: string) => {
    const count = await transcript.locator('.transcript-line').count()
    await input.pressSequentially(command, { delay: 15 })
    await input.press('Enter')
    const reply = transcript.locator('.transcript-line').nth(count + 1)
    await expect(reply).toContainText(expected)
    return (await reply.textContent())!
  }
  const draft = await send('/world generate building east --floors 3 --rooms-per-floor 4 --main-rooms 2 --basement-levels 2 --theme "The Lantern House with a great room, kitchen, cellar and chamber beneath it."', '16 rooms, 1 buildings')
  for (const label of ['Floor 1:', 'Floor 2:', 'Floor 3:', 'Basement level 1:', 'Basement level 2:']) {
    expect(draft).toContain(label)
  }
  const id = draft.match(/Neighborhood proposal ([a-f0-9-]{36})/)![1]
  await expect(room).toHaveText('Building Lot')
  await send(`/world approve ${id}`, '16 rooms added')
  await send('open east door', 'You open')
  await send('east', 'Floor 1 room 1')
  await send('up', 'Floor 2 room 1')
  await send('up', 'Floor 3 room 1')
  await send('down', 'Floor 2 room 1')
  await send('down', 'Floor 1 room 1')
  await send('open down door', 'You open')
  await send('down', 'Basement 1')
  await send('open down door', 'You open')
  await send('down', 'Basement 2')
  await page.reload()
  await expect(room).toHaveText('Basement 2')
  await send('up', 'Basement 1')
  await send('up', 'Floor 1 room 1')
  await send('west', 'Building Lot')
  await expect(room).toHaveText('Building Lot')
})
