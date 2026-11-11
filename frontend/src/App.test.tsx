import { renderToStaticMarkup } from 'react-dom/server'
import { expect, test } from 'vitest'
import { App } from './App'

test('describes the simulation and its initial loading state', () => {
  const html = renderToStaticMarkup(<App />)
  expect(html).toContain('<h1>Replan the journey.</h1>')
  expect(html).toContain('Loading the timetable')
  expect(html).not.toContain('Verified')
})
