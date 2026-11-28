import { useEffect, useMemo, useRef, useState } from 'react'
import type { Feature, FeatureCollection, Geometry, Position } from 'geojson'
import type { GeoJSONSource, Map as LibreMap, Marker } from 'maplibre-gl'
import type { Incident, Itinerary, Network, Offer, Stop } from './api'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'

interface MapProps {
  network: Network
  offer: Offer | null | undefined
  incident?: Incident | null
  origins: readonly [string, string]
  destination?: string
  label: string
}

type MapData = FeatureCollection<Geometry, { kind: string; rider?: string }>

function features(network: Network, offer: Offer | null | undefined): MapData {
  const stops = new Map(network.stops.map(stop => [stop.id, stop]))
  const coordinates = (ids: readonly string[]): Position[] => ids.flatMap(id => {
    const stop = stops.get(id)
    return stop ? [[stop.longitude, stop.latitude]] : []
  })
  const paths: MapData['features'] = network.lines.map(line => ({
    type: 'Feature',
    geometry: { type: 'LineString', coordinates: coordinates(line.stops) },
    properties: { kind: line.mode },
  }))
  for (const stop of network.stops) {
    paths.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [stop.longitude, stop.latitude] },
      properties: { kind: 'station' },
    })
  }
  function riderLines(itinerary: Itinerary, rider: string) {
    for (const leg of itinerary.legs) {
      let ids = [leg.origin, leg.destination]
      if (leg.kind === 'ride') {
        const mode = leg.trip.startsWith('metro:') ? 'metro' : 'tram'
        const sections = network.lines.flatMap(line => {
          const from = line.stops.indexOf(leg.origin)
          const to = line.stops.indexOf(leg.destination)
          if (line.mode !== mode || from === -1 || to === -1) return []
          const section = line.stops.slice(Math.min(from, to), Math.max(from, to) + 1)
          return [from < to ? section : section.reverse()]
        })
        sections.sort((left, right) => left.length - right.length)
        ids = sections[0] ?? ids
      }
      const segment: Feature<Geometry, { kind: string; rider: string }> = {
        type: 'Feature', geometry: { type: 'LineString', coordinates: coordinates(ids) },
        properties: { kind: leg.kind, rider },
      }
      paths.push(segment)
    }
  }
  if (offer) {
    riderLines(offer.a, 'a')
    riderLines(offer.b, 'b')
  }
  return { type: 'FeatureCollection', features: paths }
}

function labels(props: Omit<MapProps, 'label'>) {
  const { network, offer, origins, destination, incident } = props
  const routePoints = [offer?.a, offer?.b].flatMap(route =>
    route?.legs.filter(leg => leg.kind === 'walk').map(leg => leg.origin) ?? [],
  )
  const marked = [...origins, ...(destination ? [destination] : []), ...routePoints]
  const closed = incident?.kind === 'stop_closure' ? incident.stop : undefined
  if (closed) marked.push(closed)
  return Array.from(new Set(marked)).flatMap(id => {
    const stop = network.stops.find(candidate => candidate.id === id)
    if (!stop) return []
    const role = id === closed ? 'closed' : id === destination ? 'target'
      : id === origins[0] ? 'a' : id === origins[1] ? 'b' : 'transfer'
    return [{ stop, role }]
  })
}

function markerElement(stop: Stop, role: string) {
  const root = document.createElement('div')
  root.className = `station-marker station-marker--${role}`
  const symbol = document.createElement('span')
  symbol.className = 'station-symbol'
  symbol.textContent = { a: 'A', b: 'B', closed: '×', target: '◎', transfer: '↔' }[role] ?? '•'
  const name = document.createElement('span')
  name.className = 'station-name'
  name.textContent = stop.name
  root.append(symbol, name)
  return root
}

export function RouteMap(props: MapProps) {
  const { network, offer, incident, origins, destination, label } = props
  const [a, b] = origins
  const host = useRef<HTMLDivElement>(null)
  const mapRef = useRef<LibreMap | undefined>(undefined)
  const [markers, setMarkers] = useState<typeof Marker>()
  const [failure, setFailure] = useState(false)
  const data = useMemo(() => features(network, offer), [network, offer])

  useEffect(() => {
    let disposed = false
    const node = host.current
    if (!node) return
    void import('maplibre-gl').then(({ Map, Marker, NavigationControl, LngLatBounds, setWorkerUrl }) => {
      if (disposed) return
      setWorkerUrl(workerUrl)
      const map = new Map({
        container: node,
        style: { version: 8, sources: {}, layers: [
          { id: 'paper', type: 'background', paint: { 'background-color': '#e9eef2' } },
        ] },
        attributionControl: false,
        dragRotate: false,
        pitchWithRotate: false,
        canvasContextAttributes: { antialias: true },
      })
      mapRef.current = map
      map.on('error', () => { if (!disposed) setFailure(true) })
      map.on('idle', () => {
        if (!disposed && map.getLayer('network') && map.queryRenderedFeatures({ layers: ['network'] }).length) {
          node.dataset.mapReady = 'true'
        }
      })
      const bounds = new LngLatBounds()
      for (const stop of network.stops) {
        if (stop.longitude > 27.06 && stop.longitude < 27.17) {
          bounds.extend([stop.longitude, stop.latitude])
        }
      }
      if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: { top: 52, bottom: 55, left: 48, right: 48 }, duration: 0 })
      map.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')
      map.once('load', () => {
        if (disposed) return
        map.addSource('timetable', { type: 'geojson', data: features(network, undefined) })
        map.addLayer({ id: 'network', source: 'timetable', type: 'line',
          filter: ['in', ['get', 'kind'], ['literal', ['metro', 'tram']]],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 3, 'line-color': ['match', ['get', 'kind'], 'metro', '#a5b8ca', '#bbaab4'] },
        })
        map.addLayer({ id: 'stops', source: 'timetable', type: 'circle',
          filter: ['==', ['get', 'kind'], 'station'],
          paint: { 'circle-radius': 3, 'circle-color': '#f8fafc', 'circle-stroke-width': 1,
            'circle-stroke-color': '#9aacbc' },
        })
        map.addLayer({ id: 'rides', source: 'timetable', type: 'line',
          filter: ['==', ['get', 'kind'], 'ride'],
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 5, 'line-color': ['match', ['get', 'rider'], 'a', '#1b69bd', '#117c6f'],
            'line-offset': ['match', ['get', 'rider'], 'a', -1.5, 1.5] },
        })
        map.addLayer({ id: 'walks', source: 'timetable', type: 'line',
          filter: ['==', ['get', 'kind'], 'walk'],
          paint: { 'line-width': 4, 'line-dasharray': [1, 1], 'line-color': '#263e57' },
        })
        setMarkers(() => Marker)
      })
    }).catch(() => {
      if (!disposed) setFailure(true)
    })
    return () => {
      disposed = true
      mapRef.current?.remove()
      mapRef.current = undefined
    }
  }, [network])

  useEffect(() => {
    if (markers) (mapRef.current?.getSource('timetable') as GeoJSONSource | undefined)?.setData(data)
  }, [data, markers])

  const annotated = useMemo(() => labels({
    network, offer, incident, origins: [a, b], destination,
  }), [network, offer, incident, a, b, destination])
  useEffect(() => {
    const map = mapRef.current
    if (!map || !markers) return
    const rendered = annotated.map(({ stop, role }) =>
      new markers({ element: markerElement(stop, role), anchor: 'center' })
        .setLngLat([stop.longitude, stop.latitude]).addTo(map),
    )
    return () => rendered.forEach(marker => marker.remove())
  }, [annotated, markers])

  return (
    <div className="route-map">
      <div ref={host} className="map-canvas" aria-label={label} data-testid="route-map" />
      {failure && <p className="map-fallback">The map needs WebGL. Journey details are available below.</p>}
    </div>
  )
}
