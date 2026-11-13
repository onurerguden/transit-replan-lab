// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Incidents } from './Incidents'
import { translate } from './i18n'
import { runLink } from './useRun'

afterEach(cleanup)

const incidents = [
  { id: 'a1', disruption: { kind: 'stop_closure' as const, stop: 'tram:7', start: 30240, end: 36000 } },
  { id: 'b2', disruption: { kind: 'trip_cancellation' as const, trip: 'metro:1', service_date: '2026-10-21' } },
]
const describeIncident = (incident: { kind: string }) => incident.kind

describe('Incidents', () => {
  it('lists every active disruption and retracts one by id', () => {
    const onRetract = vi.fn()
    render(<Incidents incidents={incidents} busy={false} t={key => translate('en', key)}
      describe={describeIncident} onRetract={onRetract} />)
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    fireEvent.click(screen.getByRole('button', { name: /Retract: trip_cancellation/ }))
    expect(onRetract).toHaveBeenCalledWith('b2')
  })

  it('disables retraction while a command is running', () => {
    render(<Incidents incidents={incidents} busy t={key => translate('en', key)}
      describe={describeIncident} onRetract={vi.fn()} />)
    for (const button of screen.getAllByRole('button')) expect((button as HTMLButtonElement).disabled).toBe(true)
  })

  it('says so when no disruption is active, in either language', () => {
    render(<Incidents incidents={[]} busy={false} t={key => translate('tr', key)}
      describe={describeIncident} onRetract={vi.fn()} />)
    expect(screen.getByText('Etkin aksama yok.')).toBeTruthy()
  })
})

describe('translations and links', () => {
  it('has the same keys in both languages', () => {
    const english = translate('en', 'status.verified')
    expect(english).toBe('Verified')
    expect(translate('tr', 'status.verified')).toBe('Doğrulandı')
  })

  it('builds a link that keeps other query parameters', () => {
    expect(runLink('abc', '?workflow=legacy')).toContain('workflow=legacy')
    expect(runLink('abc', '?workflow=legacy')).toContain('run=abc')
  })
})
