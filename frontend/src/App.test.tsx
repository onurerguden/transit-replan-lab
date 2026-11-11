import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { App } from './App'

test('identifies the simulator and its setup state', () => {
  const html = renderToStaticMarkup(<App />)
  expect(html).toContain('<h1>Transit Replan Lab</h1>')
  expect(html).toContain('Simulation setup in progress')
})
