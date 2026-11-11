import { expect, test } from '@playwright/test'

test('replans a real timetable after reconnecting the event stream', async ({ page }) => {
  let attempts = 0
  await page.route('**/events?*', route => {
    attempts += 1
    return attempts === 1 ? route.abort('connectionreset') : route.continue()
  })
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Replan the journey.' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'Initial plan' })).toContainText('Via Konak')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified', { timeout: 20_000 })
  expect(attempts).toBeGreaterThan(1)

  const newPlan = page.getByRole('region', { name: 'New plan' })
  await expect(newPlan).toContainText('Via Fahrettin Altay')
  await expect(newPlan).toContainText('Verified')
  await expect(newPlan.locator('.station-marker--closed')).toContainText('Konak İskele')
  await expect(page.getByRole('complementary')).toContainText('Both votes and the timetable agree.')
  await expect(newPlan.getByTestId('route-map')).toHaveAttribute('data-map-ready', 'true')
  if (process.env.TRL_CAPTURE) await page.screenshot({ path: process.env.TRL_CAPTURE, fullPage: true })
  const second = page.getByRole('button', { name: /Offer 2/ })
  await second.focus()
  await page.keyboard.press('Enter')
  await expect(second).toHaveAttribute('aria-pressed', 'true')
  await expect(newPlan).toContainText('Proposal')
  await expect(newPlan).not.toContainText('Verified')
})

test('explains a completed search with no feasible joint arrival', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByLabel('Scenario', { exact: true }).selectOption('infeasible')
  await page.getByRole('button', { name: 'Set up run', exact: true }).click()
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('No feasible meeting', { timeout: 20_000 })
  await expect(page.getByRole('region', { name: 'New plan' })).not.toContainText('Verified')
})
