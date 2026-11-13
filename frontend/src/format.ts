import type { Network, Run } from './api'
import { elapsed, time } from './api'

export const roleLabels: Record<string, string> = {
  operator: 'Operator', router: 'Route engine', rider_a: 'Rider 1', rider_b: 'Rider 2',
  analyst: 'Transfer analyst', mediator: 'Mediator', verifier: 'Verifier', system: 'System',
}

export const roleOrder = ['operator', 'rider_a', 'rider_b', 'analyst', 'mediator', 'verifier']

export function name(network: Network | undefined, id: string | undefined) {
  return network?.stops.find(stop => stop.id === id)?.name ?? id ?? '—'
}

export function mode(trip: string) {
  return trip.startsWith('metro:') ? 'Metro' : 'Tram'
}

export function disruptionSummary(incident: NonNullable<Run['incident']>, network: Network) {
  switch (incident.kind) {
    case 'stop_closure':
      return `${name(network, incident.stop)} closed · ${time(incident.start)}–${time(incident.end)}`
    case 'trip_cancellation':
      return `Trip ${incident.trip} cancelled`
    case 'trip_delay':
      return `Trip ${incident.trip} delayed ${elapsed(incident.seconds)}`
  }
}

export function meetingDifference(meeting: number, initial: number) {
  const difference = meeting - initial
  return difference === 0 ? 'Same meeting time'
    : `${elapsed(Math.abs(difference))} ${difference > 0 ? 'later' : 'earlier'}`
}
