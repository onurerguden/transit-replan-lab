import type { components } from './api.generated'

type Schemas = components['schemas']
export type Network = Schemas['Network']
export type Run = Schemas['RunView']
export type Offer = Schemas['Offer']
export type Itinerary = Schemas['Itinerary']
export type Receipt = Schemas['Receipt']
export type Architecture = Schemas['CreateRun']['architecture']
export type ScenarioId = NonNullable<Schemas['CreateRun']['scenario']>
export type Stop = Schemas['Stop']
export type Incident = NonNullable<Run['incident']>

export interface RunEvent {
  seq: number
  version: number
  kind: string
  role: string
  message: string
  recorded_at: string
  details: Record<string, unknown>
}

export async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init)
  if (!response.ok) {
    const detail = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(detail.detail ?? 'The simulation service is unavailable.')
  }
  return await response.json() as T
}

export function command<T>(path: string, body: object, key: string = crypto.randomUUID()) {
  return get<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
    body: JSON.stringify(body),
  })
}

export function time(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return [hours, minutes].map(value => String(value).padStart(2, '0')).join(':')
}

export function elapsed(seconds: number) {
  const minutes = Math.round(seconds / 60)
  return minutes >= 60 ? `${Math.floor(minutes / 60)}h ${minutes % 60}m` : `${minutes} min`
}
