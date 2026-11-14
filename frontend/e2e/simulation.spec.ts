import { expect, test } from '@playwright/test'

test('replans a real timetable after reconnecting the event stream', async ({ page }) => {
  let attempts = 0
  await page.route('**/events?*', route => {
    attempts += 1
    return attempts === 1 ? route.abort('connectionreset') : route.continue()
  })
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/?workflow=legacy')
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
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByLabel('Scenario', { exact: true }).selectOption('infeasible')
  await page.getByRole('button', { name: 'Set up run', exact: true }).click()
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('No feasible meeting', { timeout: 20_000 })
  await expect(page.getByRole('region', { name: 'New plan' })).not.toContainText('Verified')
})

test('shows independent votes and a mediated replay on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByLabel('Coordinator', { exact: true }).selectOption('five')
  await page.getByRole('button', { name: 'Set up run', exact: true }).click()
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified', { timeout: 20_000 })
  await expect(page.getByRole('complementary')).toContainText('Selected a compromise offer.')
  await expect(page.locator('.timeline').getByText('Accepted the offer.')).toHaveCount(2)
  await expect(page.getByText(/7 model calls/)).toBeVisible()
  await page.locator('.evidence summary').click()
  await expect(page.getByRole('region', { name: 'Rider 1 evidence' })).toContainText('Accepted')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  if (process.env.TRL_MOBILE_CAPTURE) {
    await page.screenshot({ path: process.env.TRL_MOBILE_CAPTURE, fullPage: true })
  }
})

test('withdraws the old verified plan while a new revision is pending', async ({ page }) => {
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  let release = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/events?*', async route => {
    await gate
    await route.continue()
  })
  try {
    await page.getByRole('button', { name: 'Apply disruption' }).click()
    await expect(page.locator('.run-bar')).toContainText('Revision 2')
    await expect(page.getByRole('status')).toHaveText('Replanning')
    await expect(page.getByRole('region', { name: 'New plan' })).not.toContainText('Verified')
    await expect(page.getByRole('region', { name: 'Joint offers' })).toHaveCount(0)
  } finally {
    release()
  }
  await expect(page.getByRole('status')).toHaveText('Verified')
})

test('retries a committed command with its original key after losing the response', async ({ page }) => {
  const keys: string[] = []
  await page.route('**/disruptions', async route => {
    keys.push(route.request().headers()['idempotency-key']!)
    if (keys.length === 1) {
      const committed = await route.fetch()
      expect(committed.status()).toBe(202)
      await route.abort('connectionreset')
      return
    }
    await route.continue()
  })
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('alert')).toContainText('Retry to recover its result')
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  await expect(page.locator('.run-bar')).toContainText('Revision 1')
  await expect(page.getByText('A new disruption report is queued.')).toHaveCount(1)
  expect(keys).toHaveLength(2)
  expect(keys[0]).toBeTruthy()
  expect(keys[1]).toBe(keys[0])
})

test('recovers a failed outcome read without reissuing the command', async ({ page }) => {
  let reads = 0
  let submissions = 0
  await page.route(/\/v1\/runs\/[a-f0-9]{32}$/, async route => {
    reads += 1
    if (reads === 2) await route.abort('connectionreset')
    else await route.continue()
  })
  await page.route('**/disruptions', route => {
    submissions += 1
    return route.continue()
  })
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('alert')).toContainText('Refresh to load')
  await page.getByRole('button', { name: 'Refresh outcome' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  expect(reads).toBe(3)
  expect(submissions).toBe(1)
})

test('clarifies an ambiguous notice and keeps evidence bound to the selected offer', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('textbox', { name: 'Disruption notice text' })
    .fill('Konak is closed from 08:24 to 10:00.')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Clarification needed')
  await expect(page.getByRole('region', { name: 'Joint offers' })).toHaveCount(0)
  await page.getByRole('textbox', { name: 'Which stop or trip is affected, and when?' })
    .fill('Konak İskele tram')
  await page.getByRole('button', { name: 'Send clarification' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  await expect(page.locator('.run-bar')).toContainText('Revision 1')
  const evidence = page.locator('.evidence')
  await evidence.locator('summary').focus()
  await page.keyboard.press('Enter')
  await expect(evidence).toContainText('Timetable check passed')
  const rider = page.getByRole('region', { name: 'Rider 1 evidence' })
  await expect(rider).toBeVisible()
  await expect(rider).toContainText('Accepted')
  await expect(rider).toContainText('Walk')
  await expect(rider).toContainText('Fahrettin Altay')
  await expect(page.getByText('Konak İskele closed · 08:24–10:00').first()).toBeVisible()
  if (process.env.TRL_EVIDENCE_CAPTURE) {
    await page.screenshot({ path: process.env.TRL_EVIDENCE_CAPTURE, fullPage: true })
  }
  await page.getByRole('button', { name: /Offer 2/ }).click()
  await evidence.locator('summary').click()
  await expect(evidence).toContainText('No verification recorded')
  await expect(rider).toContainText('No vote')
})

test('retries startup against the same run after losing the creation receipt', async ({ page }) => {
  const receipts: { key: string; id: string }[] = []
  await page.route('**/v1/runs', async route => {
    const response = await route.fetch()
    expect(response.status()).toBe(201)
    const body = await response.json() as { run_id: string }
    receipts.push({ key: route.request().headers()['idempotency-key']!, id: body.run_id })
    if (receipts.length === 1) await route.abort('connectionreset')
    else await route.fulfill({ response })
  })
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('alert')).toBeVisible()
  await page.getByRole('button', { name: 'Retry', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('Ready')
  expect(receipts).toHaveLength(2)
  expect(receipts[0]?.key).toBeTruthy()
  expect(receipts[0]?.id).toBeTruthy()
  expect(receipts[1]).toEqual(receipts[0])
})

test('compares closure interpretations and independently verifies the resilient route', async ({ page }) => {
  const record = process.env.TRL_VNEXT_VIDEO === '1'
  if (record) test.setTimeout(115_000)
  const pause = async (ms: number) => {
    if (record) await new Promise<void>(resolve => setTimeout(resolve, ms))
  }
  await page.setViewportSize({ width: 1440, height: 960 })
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await pause(11_000)
  await page.getByText('Run settings', { exact: true }).click()
  await page.getByLabel('Ranking', { exact: true }).selectOption('robust')
  await page.getByRole('button', { name: 'Set up run', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Clarification needed')
  const interpretations = page.getByRole('region', { name: 'Possible interpretations' })
  await expect(interpretations).toContainText('Konak İskele closure')
  await expect(interpretations).toContainText('No feasible meeting')
  await pause(16_000)
  await expect(page.getByRole('region', { name: 'Joint offers' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Konak İskele (Tram)', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  const comparison = page.getByRole('region', { name: 'Scenario resilience' })
  await expect(comparison).toContainText('128 / 128')
  if (record) await comparison.scrollIntoViewIfNeeded()
  await pause(15_000)
  await page.getByText('Offer evidence', { exact: true }).click()
  await expect(page.getByText('Timetable check passed')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Rider 1 evidence' })).toContainText('Accepted')
  if (record) await page.getByRole('region', { name: 'Rider 1 evidence' }).scrollIntoViewIfNeeded()
  await pause(18_000)
  if (process.env.TRL_VNEXT_CAPTURE) await page.screenshot({ path: process.env.TRL_VNEXT_CAPTURE, fullPage: true })
  await page.getByRole('button', { name: /Earliest/ }).click()
  await expect(comparison).toContainText('109 / 128')
  await page.getByRole('button', { name: /2 minutes late/ }).click()
  await expect(comparison).toContainText('Missed connection')
  if (record) await comparison.scrollIntoViewIfNeeded()
  await pause(23_000)
})

test('keeps an unanswered disruption unresolved on mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await page.getByRole('button', { name: 'I don’t know', exact: true }).click()
  await expect(page.getByRole('status')).toHaveText('Disruption unresolved')
  await expect(page.getByRole('region', { name: 'Joint offers' })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
})

test('clarifies by keyboard on a narrow screen without WebGL', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 })
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext
    HTMLCanvasElement.prototype.getContext = function (this: HTMLCanvasElement, ...args: unknown[]) {
      return String(args[0]).startsWith('webgl') ? null : Reflect.apply(original, this, args)
    } as typeof original
  })
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Ready')
  async function activate(name: string) {
    const button = page.getByRole('button', { name, exact: true })
    for (let step = 0; step < 80; step += 1) {
      if (await button.evaluate(element => element === document.activeElement)) {
        await page.keyboard.press('Enter')
        return
      }
      await page.keyboard.press('Tab')
    }
    throw new Error(`Unreachable by keyboard: ${name}`)
  }
  await activate('Apply disruption')
  await expect(page.getByRole('status')).toHaveText('Clarification needed')
  await activate('Konak İskele (Tram)')
  await expect(page.getByRole('status')).toHaveText('Verified')
  await expect(page.getByRole('region', { name: 'Decision summary' }))
    .toContainText('2/2 current rider acceptances')
  await expect(page.getByText('The map needs WebGL. Journey details are available below.').first()).toBeVisible()
  await expect(page.getByRole('region', { name: 'New plan' })).toContainText('Via Fahrettin Altay')
  await expect(page.getByRole('region', { name: 'New plan' })).toContainText('Direct tram')
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)
})

test('uses the lexicon operator for an indirect report', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByText('Run settings', { exact: true }).click()
  await page.getByLabel('Operator', { exact: true }).selectOption('lexicon')
  await page.getByRole('button', { name: 'Set up run', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Apply disruption' })).toBeEnabled()
  await page.getByRole('textbox', { name: 'Disruption notice text' })
    .fill('Konak İskele tram stop is out of service from 08:24 to 10:00.')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified')
  await expect(page.getByText(/model calls/)).toHaveCount(0)
  await expect(page.getByRole('region', { name: 'Decision summary' }))
    .toContainText('Konak İskele closed · 08:24–10:00')
})

test('retracts an incident and reopens the same run from its link', async ({ page }) => {
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified', { timeout: 20_000 })

  const incidents = page.getByRole('region', { name: 'Active disruptions' })
  await expect(incidents.getByRole('listitem')).toHaveCount(1)
  await expect(page).toHaveURL(/run=[0-9a-f]{32}/)

  // The run survives a reload because its link names it.
  const link = page.url()
  await page.reload()
  await expect(page.getByRole('status')).toHaveText('Verified')
  expect(page.url()).toBe(link)
  await expect(page.locator('.run-bar')).toContainText('Revision 1')

  await incidents.getByRole('button', { name: /Retract/ }).click()
  await expect(page.getByRole('status')).toHaveText('Ready', { timeout: 20_000 })
  await expect(incidents).toContainText('No disruption is active.')
  await expect(page.locator('.run-bar')).toContainText('Revision 2')
})

test('switches the interface to Turkish and remembers the choice', async ({ page }) => {
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Türkçe' }).click()
  await expect(page.getByRole('status')).toHaveText('Hazır')
  await page.reload()
  await expect(page.getByRole('status')).toHaveText('Hazır')
  await expect(page.locator('html')).toHaveAttribute('lang', 'tr')
})

test('has no serious accessibility violations in light or dark themes', async ({ page }) => {
  const { default: AxeBuilder } = await import('@axe-core/playwright')
  await page.goto('/?workflow=legacy')
  await expect(page.getByRole('status')).toHaveText('Ready')
  await page.getByRole('button', { name: 'Apply disruption' }).click()
  await expect(page.getByRole('status')).toHaveText('Verified', { timeout: 20_000 })
  for (const dark of [false, true]) {
    if (dark) await page.getByRole('button', { name: 'Switch theme' }).click()
    const result = await new AxeBuilder({ page }).disableRules(['color-contrast']).analyze()
    const serious = result.violations.filter(item => item.impact === 'serious' || item.impact === 'critical')
    expect(serious.map(item => `${item.id}: ${item.nodes[0]?.html}`)).toEqual([])
  }
})
