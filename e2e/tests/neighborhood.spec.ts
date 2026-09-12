import { expect, test } from '@playwright/test'

test('admin reviews a neighborhood and players explore shared doors and containers', async ({ page, browser }) => {
  test.setTimeout(90000)
  const context = await browser.newContext()
  const explorer = await context.newPage()
  const send = async (target: typeof page, command: string, expected: string) => {
    await target.getByTestId('command-input').fill(command)
    await target.getByTestId('command-input').press('Enter')
    await expect(target.getByTestId('transcript')).toContainText(expected)
  }
  try {
    await page.goto('/')
    await page.getByTestId('username-input').fill('NeighborhoodAdmin')
    await page.getByTestId('password-input').fill('A long test-only passphrase1!')
    await page.getByTestId('login-button').click()
    await expect(page.getByText(/Online/)).toBeVisible()
    await send(page, 'south', 'Docks')
    await send(page, '/world generate east --rooms 2 --buildings 1 --theme "Cedar crafts"', 'Neighborhood proposal')
    const draft = await page.getByTestId('transcript').innerText()
    const id = draft.match(/Neighborhood proposal ([a-f0-9-]{36})/)?.[1]
    expect(id).toBeTruthy()
    for (const detail of ['Cedar Workroom', 'cedar door', 'wooden box', 'clay cup', 'stone bench']) {
      expect(draft).toContain(detail)
    }
    await expect(page.getByTestId('map-panel')).not.toContainText('Cedar Lane')
    await page.reload()
    await expect(page.getByText(/Online/)).toBeVisible()
    await send(page, `/world preview ${id}`, 'clay cup')
    await send(page, `/world approve ${id}`, '2 rooms added')
    await expect(page.getByTestId('map-panel')).not.toContainText('Cedar Lane')

    await explorer.goto('/')
    await explorer.getByTestId('register-toggle').click()
    await explorer.getByTestId('username-input').fill(`Neighbor-${Date.now()}`)
    await explorer.getByTestId('password-input').fill('A long test-only passphrase1!')
    await explorer.getByTestId('login-button').click()
    await expect(explorer.getByText(/Online/)).toBeVisible()
    await send(explorer, 'south', 'Docks')
    await send(explorer, 'east', 'Cedar Lane')
    await send(explorer, 'east', 'cedar door is closed')
    await expect(explorer.getByTestId('map-panel')).not.toContainText('Cedar Workroom')
    await send(explorer, 'take stone bench', 'fixed in place')
    await send(page, 'east', 'Cedar Lane')
    await send(page, 'open east door', 'You open the cedar door')
    await expect(explorer.getByTestId('transcript')).toContainText('cedar door opens')
    await send(explorer, 'east', 'Cedar Workroom')
    await send(explorer, 'close west door', 'You close the cedar door')
    await expect(page.getByTestId('transcript')).toContainText('cedar door closes')
    await send(explorer, 'open wooden box', 'You open the wooden box')
    await send(explorer, 'get clay cup from wooden box', 'You take the clay cup')
    await expect(explorer.getByTestId('inventory-panel')).toContainText('clay cup')
    await explorer.reload()
    await expect(explorer.getByText(/Online/)).toBeVisible()
    await expect(explorer.getByTestId('current-room')).toHaveText('Cedar Workroom')
    await expect(explorer.getByTestId('inventory-panel')).toContainText('clay cup')
    await send(explorer, 'west', 'cedar door is closed')
  } finally {
    await context.close()
  }
})
