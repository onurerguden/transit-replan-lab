import { expect, test } from 'vitest'
import type { Itinerary, Network } from './api'
import { routeFeatures } from './RouteMap'

test('orients shared track edges consistently when riders travel in opposite directions', () => {
  const network: Network = {
    stops: ['z', 'b', 'c'].map((id, index) => ({
      id, name: id, longitude: 27 + index / 100, latitude: 38,
    })),
    lines: [{ id: 'metro:1', mode: 'metro', stops: ['z', 'b', 'c'] }],
  }
  const journey = (origin: string, destination: string): Itinerary => ({
    origin, destination, start: 0, arrival: 60,
    legs: [{
      kind: 'ride', origin, destination, departure: 0, arrival: 60,
      trip: 'metro:1', service_date: '2026-10-21', board_index: 0, alight_index: 1,
    }],
  })
  const map = routeFeatures(network, {
    id: 'v1-1', version: 1, meeting: 60, a: journey('z', 'c'), b: journey('b', 'z'),
  })
  const a = map.features.filter(feature => feature.properties.rider === 'a')
  const b = map.features.filter(feature => feature.properties.rider === 'b')
  expect(a).toHaveLength(1)
  expect(b).toHaveLength(1)
  const lineA = a[0]?.geometry
  const lineB = b[0]?.geometry
  expect(lineA?.type).toBe('LineString')
  expect(lineB?.type).toBe('LineString')
  if (lineA?.type === 'LineString' && lineB?.type === 'LineString') {
    expect(lineA.coordinates.slice(1)).toEqual(lineB.coordinates)
  }
})
