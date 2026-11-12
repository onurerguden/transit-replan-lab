import { useCallback, useEffect, useRef, useState } from 'react'
import { command, get, HttpError } from './api'
import type { Architecture, Network, Receipt, Run, RunEvent, RunSetup, ScenarioId } from './api'

const finalEvents = new Set(['verified', 'verification_failed', 'infeasible', 'error', 'clarification', 'no_agreement', 'abstained'])

type PendingCommand = {
  id: string
  kind: 'disruptions' | 'clarifications'
  version: number
  text: string
  key: string
  questionId?: string
  optionId?: string
}

type Retry = 'command' | 'snapshot'

function describe(cause: unknown) {
  return cause instanceof Error ? cause.message : 'Unable to reach the simulation service.'
}

export function useRun() {
  const [network, setNetwork] = useState<Network>()
  const [settings, setSettings] = useState<RunSetup>()
  const [run, setRun] = useState<Run>()
  const [events, setEvents] = useState<RunEvent[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [retry, setRetry] = useState<Retry>()
  const [connection, setConnection] = useState<'idle' | 'live' | 'reconnecting'>('idle')
  const stream = useRef<EventSource | undefined>(undefined)
  const epoch = useRef(0)
  const cursor = useRef(0)
  const inFlight = useRef(false)
  const pending = useRef<PendingCommand | undefined>(undefined)
  const reload = useRef<(() => Promise<void>) | undefined>(undefined)
  const createKey = useRef<{ body: string; key: string } | undefined>(undefined)

  const start = useCallback(async (scenario: ScenarioId, architecture: Architecture, configuration: RunSetup = {}) => {
    if (inFlight.current) return
    const generation = ++epoch.current
    stream.current?.close()
    cursor.current = 0
    pending.current = undefined
    reload.current = undefined
    const body = { ...configuration, scenario, architecture }
    const serialized = JSON.stringify(body)
    if (createKey.current?.body !== serialized) {
      createKey.current = { body: serialized, key: crypto.randomUUID() }
    }
    inFlight.current = true
    setConnection('idle')
    setRun(undefined)
    setEvents([])
    setRetry(undefined)
    setBusy(true)
    setError('')
    try {
      const [receipt, map] = await Promise.all([
        command<Receipt>('/v1/runs', body, createKey.current.key),
        get<Network>('/v1/network'),
      ])
      const snapshot = await get<Run>(`/v1/runs/${receipt.run_id}`)
      if (generation === epoch.current) {
        createKey.current = undefined
        setSettings(body)
        setNetwork(map)
        setRun(snapshot)
      }
    } catch (cause) {
      if (generation === epoch.current) setError(describe(cause))
    } finally {
      if (generation === epoch.current) {
        inFlight.current = false
        setBusy(false)
      }
    }
  }, [])

  useEffect(() => {
    const setup = window.setTimeout(() => {
      const legacy = new URLSearchParams(window.location.search).get('workflow') === 'legacy'
      void start(legacy ? 'demo' : 'resilience', 'rules', { workflow: legacy ? 'legacy' : 'vnext', route_policy: 'earliest', operator_mode: null, preference_a: null, preference_b: null })
    }, 0)
    return () => {
      window.clearTimeout(setup)
      epoch.current += 1
      inFlight.current = false
      stream.current?.close()
    }
  }, [start])

  function watch(receipt: Receipt, generation: number) {
    const path = `/v1/runs/${receipt.run_id}`
    stream.current?.close()
    const source = new EventSource(`${path}/events?after=${cursor.current}`)
    stream.current = source
    const current = () => generation === epoch.current && source === stream.current
    let reading = false

    async function readOutcome() {
      if (!current() || reading) return
      reading = true
      setRetry(undefined)
      setError('')
      try {
        const snapshot = await get<Run>(path)
        if (!current()) return
        setRun(snapshot)
        if (snapshot.status === 'planning') watch({ run_id: snapshot.id, version: snapshot.version }, generation)
      } catch {
        if (current()) {
          setError('The run finished. Refresh to load its latest outcome.')
          setRetry('snapshot')
        }
      } finally {
        reading = false
      }
    }

    reload.current = readOutcome
    source.onopen = () => { if (current()) setConnection('live') }
    source.onerror = () => { if (current()) setConnection('reconnecting') }
    source.onmessage = (message: MessageEvent<string>) => {
      if (!current()) return
      const event = JSON.parse(message.data) as RunEvent
      if (event.seq <= cursor.current) return
      cursor.current = event.seq
      setEvents(previous => [...previous, event])
      if (event.version >= receipt.version && finalEvents.has(event.kind)) {
        source.close()
        setConnection('idle')
        void readOutcome()
      }
    }
  }

  async function submit(action: PendingCommand) {
    if (inFlight.current) return
    const generation = epoch.current
    const { id, kind, version, text, key, questionId, optionId } = action
    inFlight.current = true
    pending.current = action
    setBusy(true)
    setRetry(undefined)
    setError('')
    try {
      const body = kind === 'disruptions' ? { version, notice: text }
        : { version, question_id: questionId, ...(optionId ? { option_id: optionId } : { answer: text }) }
      const receipt = await command<Receipt>(`/v1/runs/${id}/${kind}`, body, key)
      if (generation !== epoch.current) return
      pending.current = undefined
      setRun(current => current?.id === id ? {
        ...current,
        version: receipt.version,
        status: 'planning',
        offers: [],
        votes: [],
        verified_offer: null,
        incident: kind === 'disruptions' ? null : current.incident,
        question: null,
        evidence: current.evidence ? { ...current.evidence, intake: null, offers: [] } : undefined,
        error: null,
      } : current)
      watch(receipt, generation)
    } catch (cause) {
      if (generation !== epoch.current) return
      if (cause instanceof HttpError && cause.status >= 400 && cause.status < 500) {
        pending.current = undefined
        setError(describe(cause))
      } else {
        setError('The command response was interrupted. Retry to recover its result.')
        setRetry('command')
      }
    } finally {
      if (generation === epoch.current) {
        inFlight.current = false
        setBusy(false)
      }
    }
  }

  async function send(kind: PendingCommand['kind'], text: string, optionId?: string) {
    if (!run || pending.current || run.status === 'planning') return
    await submit({
      id: run.id, kind, version: run.version, text, key: crypto.randomUUID(),
      questionId: kind === 'clarifications' ? run.evidence?.intake?.question?.id : undefined,
      optionId,
    })
  }

  function recover() {
    if (pending.current) void submit(pending.current)
    else void reload.current?.()
  }

  return { network, run, settings, events, connection, busy, error, retry, start, send, recover }
}
