import { useCallback, useEffect, useRef, useState } from 'react'
import { command, get } from './api'
import type { Architecture, Network, Receipt, Run, RunEvent, ScenarioId } from './api'

const finalEvents = new Set(['verified', 'verification_failed', 'infeasible', 'error', 'clarification', 'no_agreement'])

function describe(cause: unknown) {
  return cause instanceof Error ? cause.message : 'Unable to reach the simulation service.'
}

export function useRun() {
  const [network, setNetwork] = useState<Network>()
  const [run, setRun] = useState<Run>()
  const [events, setEvents] = useState<RunEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [connection, setConnection] = useState<'idle' | 'live' | 'reconnecting'>('idle')
  const stream = useRef<EventSource | undefined>(undefined)
  const epoch = useRef(0)
  const cursor = useRef(0)
  const startupKey = useRef<string | undefined>(undefined)

  const start = useCallback(async (scenario: ScenarioId, architecture: Architecture, key?: string) => {
    const generation = ++epoch.current
    stream.current?.close()
    cursor.current = 0
    setConnection('idle')
    setRun(undefined)
    setEvents([])
    setBusy(true)
    setError('')
    try {
      const [receipt, map] = await Promise.all([
        command<Receipt>('/v1/runs', { scenario, architecture }, key),
        get<Network>('/v1/network'),
      ])
      const snapshot = await get<Run>(`/v1/runs/${receipt.run_id}`)
      if (generation === epoch.current) {
        setNetwork(map)
        setRun(snapshot)
      }
    } catch (cause) {
      if (generation === epoch.current) setError(describe(cause))
    } finally {
      if (generation === epoch.current) setBusy(false)
    }
  }, [])

  useEffect(() => {
    startupKey.current ??= crypto.randomUUID()
    const setup = window.setTimeout(() => void start('demo', 'rules', startupKey.current), 0)
    return () => {
      window.clearTimeout(setup)
      epoch.current += 1
      stream.current?.close()
    }
  }, [start])

  async function send(kind: 'disruptions' | 'clarifications', text: string) {
    if (!run || busy) return
    const generation = epoch.current
    const id = run.id
    setBusy(true)
    setError('')
    const path = `/v1/runs/${id}`
    try {
      const body = kind === 'disruptions'
        ? { version: run.version, notice: text }
        : { version: run.version, answer: text }
      const receipt = await command<Receipt>(`${path}/${kind}`, body)
      if (generation !== epoch.current) return
      setRun(current => current?.id === id ? {
        ...current,
        version: receipt.version,
        status: 'planning',
        offers: [],
        votes: [],
        verified_offer: null,
        incident: kind === 'disruptions' ? null : current.incident,
        question: null,
        error: null,
      } : current)
      stream.current?.close()
      const source = new EventSource(`${path}/events?after=${cursor.current}`)
      stream.current = source
      source.onopen = () => setConnection('live')
      source.onerror = () => setConnection('reconnecting')
      source.onmessage = (message: MessageEvent<string>) => {
        if (generation !== epoch.current || source !== stream.current) return
        const event = JSON.parse(message.data) as RunEvent
        if (event.seq <= cursor.current) return
        cursor.current = event.seq
        setEvents(current => [...current, event])
        const final = event.version === receipt.version && finalEvents.has(event.kind)
        if (final) {
          source.close()
          setConnection('idle')
        }
        void get<Run>(path).then(snapshot => {
          if (generation !== epoch.current || source !== stream.current) return
          setRun(current => {
            if (!current || current.id !== id || snapshot.version < current.version) return current
            if (current.version === snapshot.version && current.status !== 'planning' &&
                snapshot.status === 'planning') return current
            return snapshot
          })
        }).catch(cause => {
          if (generation === epoch.current && final) setError(describe(cause))
        })
      }
    } catch (cause) {
      if (generation === epoch.current) setError(describe(cause))
    } finally {
      if (generation === epoch.current) setBusy(false)
    }
  }

  return { network, run, events, connection, busy, error, start, send }
}
