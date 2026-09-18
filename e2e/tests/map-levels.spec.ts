import { expect, test } from '@playwright/test'

test('visited floors stay ghosted, compact, and readable around the current neighborhood', async ({ page }) => {
  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto('/')
  await page.getByTestId('username-input').fill('MapExplorer')
  await page.getByTestId('password-input').fill('A long test-only passphrase1!')
  await page.getByTestId('login-button').click()
  const panel = page.getByTestId('map-panel')
  await expect(panel.getByRole('button', { name: 'Cedar Hall, you are here' })).toBeVisible()
  await panel.getByRole('button', { name: 'Expand map' }).click()
  await expect(panel.locator('[data-level]')).toHaveCount(5)
  await expect(panel.locator('[data-level="1"]')).toHaveCSS('opacity', '0.38')
  await expect(panel.locator('[data-level="2"]')).toHaveCSS('opacity', '0.24')
  await expect(panel.locator('[data-level="-1"]')).toHaveCSS('opacity', '0.38')
  await expect(panel.locator('[data-level="-2"]')).toHaveCSS('opacity', '0.24')
  await expect(panel.getByRole('button', { name: /Roof|Deep Cave|Unvisited Vault/ })).toHaveCount(0)
  await expect(panel.getByRole('button', { name: 'Library', exact: true }).getByRole('img', { name: 'Down exits' })).toBeVisible()
  const hall = panel.locator('[data-room="map_hall"]')
  const landing = panel.locator('[data-room="map_landing"]')
  const cellar = panel.locator('[data-room="map_cellar"]')
  const measure = async (room: typeof hall) => room.locator('.map-room-box').evaluate(el => {
    // Playwright boundingBox includes the thicker current-room highlight stroke.
    const rect = el as SVGGraphicsElement
    const box = rect.getBBox()
    const matrix = rect.getScreenCTM()!
    const start = new DOMPoint(box.x, box.y).matrixTransform(matrix)
    return { x: start.x, y: start.y, width: box.width * matrix.a, height: box.height * matrix.d }
  })
  const currentBox = (await measure(hall))!
  const upperBox = (await measure(landing))!
  const lowerBox = (await measure(cellar))!
  expect(upperBox.width).toBeCloseTo(currentBox.width, 1)
  expect(upperBox.height).toBeCloseTo(currentBox.height, 1)
  expect(upperBox.x - currentBox.x).toBeCloseTo(-currentBox.width / 8, 1)
  expect(upperBox.y - currentBox.y).toBeCloseTo(-currentBox.height / 4, 1)
  expect(lowerBox.x - currentBox.x).toBeCloseTo(currentBox.width / 8, 1)
  expect(lowerBox.y - currentBox.y).toBeCloseTo(currentBox.height / 4, 1)
  await expect(panel.locator('[data-level]').last()).toHaveAttribute('data-level', '0')
  const upperLabel = (await landing.locator('.map-label text').boundingBox())!
  const lowerLabel = (await cellar.locator('.map-label text').boundingBox())!
  expect(upperLabel.y).toBeGreaterThan(upperBox.y)
  expect(upperLabel.y + upperLabel.height).toBeLessThan(currentBox.y)
  expect(lowerLabel.y).toBeGreaterThan(currentBox.y + currentBox.height)
  expect(lowerLabel.y + lowerLabel.height).toBeLessThan(lowerBox.y + lowerBox.height)
  const downBadge = (await hall.locator('[data-exit="down"]').boundingBox())!
  expect(downBadge.x).toBeGreaterThan(currentBox.x + currentBox.width / 2)
  expect(downBadge.y).toBeGreaterThan(currentBox.y + currentBox.height / 2)
  expect(downBadge.y + downBadge.height).toBeLessThanOrEqual(currentBox.y + currentBox.height)
  // The exposed label is an actual pointer target, not just hidden SVG text.
  await page.mouse.click(upperLabel.x + upperLabel.width / 2, upperLabel.y + upperLabel.height / 2)
  await expect(panel.locator('.map-details summary')).toHaveText('Landing — known exits')
  await hall.click()
  await page.mouse.move(0, 0)
  const layout = await hall.getAttribute('transform')
  const fontSize = () => hall.locator('.map-label text').first().evaluate(el => {
    const svgText = el as SVGGraphicsElement
    return parseFloat(getComputedStyle(el).fontSize) * svgText.getScreenCTM()!.a
  })
  const initialFont = await fontSize()
  const fit = panel.getByRole('button', { name: 'Fit map', exact: true })
  const expectFitted = async () => {
    const viewport = await panel.locator('svg').boundingBox()
    for (const box of await panel.locator('.map-room-box').all()) {
      const bounds = await box.boundingBox()
      expect(bounds!.x).toBeGreaterThanOrEqual(viewport!.x)
      expect(bounds!.y).toBeGreaterThanOrEqual(viewport!.y)
      expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport!.x + viewport!.width)
      expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport!.y + viewport!.height)
    }
  }
  await fit.click()
  await expectFitted()
  await page.screenshot({ path: 'test-results/map-levels-desktop.png' })
  await panel.getByRole('button', { name: 'Center on me' }).click()
  await panel.getByRole('button', { name: 'Zoom out' }).click()
  expect(await fontSize()).toBeCloseTo(initialFont, 1)
  await panel.getByRole('button', { name: 'Nearby levels' }).click()
  await expect(panel.locator('[data-level]')).toHaveCount(1)
  await expect(hall).toHaveAttribute('transform', layout!)
  await panel.getByRole('button', { name: 'Nearby levels' }).click()
  const command = page.getByTestId('command-input')
  await command.fill('up')
  await command.press('Enter')
  await expect(panel.locator('[data-level="0"] [data-room="map_landing"]')).toBeVisible()
  await expect(panel.locator('[data-level="-1"] [data-room="map_hall"]')).toBeVisible()
  await expect(panel.locator('[data-level="2"] [data-room="map_roof"]')).toBeAttached()
  await expect(panel.locator('[data-room="map_tunnel"]')).toHaveCount(0)
  await panel.getByRole('button', { name: 'Center on me' }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(panel.locator('[data-level]')).toHaveCount(1)
  await expect(panel.getByRole('button', { name: 'Nearby levels' })).toHaveCount(0)
  await expect(page.getByTestId('command-input')).toBeVisible()
  await expect(panel.getByRole('button', { name: 'Landing, you are here' })).toBeInViewport({ ratio: 1 })
  expect((await panel.boundingBox())!.height).toBeLessThanOrEqual(844 * 0.4 + 1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await fit.click()
  await expectFitted()
  await page.screenshot({ path: 'test-results/map-levels-mobile.png' })
  await page.setViewportSize({ width: 1920, height: 1080 })
  await expect(panel.getByRole('button', { name: 'Nearby levels' })).toHaveAttribute('aria-pressed', 'true')
  await expect(panel.locator('[data-level]')).toHaveCount(5)
  await expectFitted()
})
