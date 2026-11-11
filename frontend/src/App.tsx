import { useState } from 'react'
import {
  Activity, ArrowRight, Check, ChevronDown, CircleDot, Clock3, GitBranch, MapPin,
  RotateCcw, TrainFront, TriangleAlert, Waypoints,
} from 'lucide-react'
import type { Architecture, Itinerary, Network, Offer, Run, RunEvent, ScenarioId } from './api'
import { elapsed, time } from './api'
import { RouteMap } from './RouteMap'
import { useRun } from './useRun'

const statusLabels: Record<Run['status'], string> = {
  ready: 'Ready',
  planning: 'Replanning',
  clarification: 'Clarification needed',
  verified: 'Verified',
  no_agreement: 'No agreement',
  infeasible: 'No feasible meeting',
  search_incomplete: 'Search incomplete',
  model_error: 'Model or worker error',
  verification_failed: 'Verification failed',
}

const roleLabels: Record<string, string> = {
  operator: 'Operator', router: 'Route engine', rider_a: 'Rider A', rider_b: 'Rider B',
  analyst: 'Transfer analyst', mediator: 'Mediator', verifier: 'Verifier', system: 'System',
}

const roleOrder = ['operator', 'rider_a', 'rider_b', 'analyst', 'mediator', 'verifier']

function name(network: Network | undefined, id: string | undefined) {
  return network?.stops.find(stop => stop.id === id)?.name ?? id ?? '—'
}

function Journey({ route, rider, network }: { route: Itinerary; rider: 'A' | 'B'; network: Network }) {
  const change = route.legs.find(leg => leg.kind === 'walk')
  return (
    <div className="journey">
      <span className={`rider-key rider-key--${rider.toLowerCase()}`}>{rider}</span>
      <div>
        <strong>{name(network, route.origin)}</strong>
        <span>{change ? `Via ${name(network, change.origin)}` : 'Direct tram'}</span>
      </div>
      <time>{time(route.arrival)}</time>
    </div>
  )
}

function PlanPanel({ label, title, network, run, offer, after }: {
  label: string; title: string; network: Network; run: Run; offer?: Offer | null; after?: boolean
}) {
  const verified = Boolean(after && run.status === 'verified' && run.verified_offer === offer?.id)
  return (
    <section className="plan-panel" aria-label={title}>
      <header className="plan-header">
        <div>
          <p className="plan-label">{label}</p>
          <h2>{title}</h2>
        </div>
        {offer && <span className={`plan-tag ${verified ? 'plan-tag--verified' : ''}`}>
          {verified ? <Check size={14} /> : <CircleDot size={13} />}
          {verified ? 'Verified' : after ? 'Proposal' : 'Timetable'}
        </span>}
      </header>
      <RouteMap network={network} offer={offer} incident={after ? run.incident : undefined}
        origins={[run.origin_a, run.origin_b]} destination={offer?.a.destination ?? run.destinations[0]}
        label={`${title} route map`} />
      <div className="journeys">
        {offer ? <>
          <Journey route={offer.a} rider="A" network={network} />
          <Journey route={offer.b} rider="B" network={network} />
          <div className="meeting"><MapPin size={16} />
            <span>Meet at <strong>{name(network, offer.a.destination)}</strong></span>
            <time>{time(offer.meeting)}</time>
          </div>
        </> : <p className="empty-plan">{after
          ? 'Replanned journeys appear here when the route engine finds an option.'
          : 'No initial joint journey in this window.'}</p>}
      </div>
    </section>
  )
}

function Timeline({ events, live }: { events: RunEvent[]; live: boolean }) {
  return (
    <aside className="activity-panel" aria-label="Simulation activity">
      <header className="section-head">
        <div><Activity size={18} /><h2>Activity</h2></div>
        {live && <span className="live-indicator">Live</span>}
      </header>
      {events.length ? <ol className="timeline" aria-live="polite">
        {events.map(event => <li key={event.seq}>
          <span className={`event-dot event-dot--${event.role}`} />
          <div>
            <div className="event-heading">
              <strong>{roleLabels[event.role] ?? event.role}</strong>
              <span>#{event.seq - events[0]!.seq + 1}</span>
            </div>
            <p>{event.message}</p>
          </div>
        </li>)}
      </ol> : <p className="quiet">Agent actions and verification will appear here after you apply a disruption.</p>}
      <details className="roles">
        <summary>Agent roles <ChevronDown size={15} /></summary>
        <ul>{roleOrder.map(role => {
          const last = events.findLast(event => event.role === role)
          return <li key={role}><strong>{roleLabels[role]}</strong><span>{last?.message ?? 'Waiting'}</span></li>
        })}</ul>
      </details>
    </aside>
  )
}

export function App() {
  const { network, run, events, connection, busy, error, start, send } = useRun()
  const [architecture, setArchitecture] = useState<Architecture>('rules')
  const [scenario, setScenario] = useState<ScenarioId>('demo')
  const [selection, setSelection] = useState<{ run: string; version: number; id: string }>()
  const [answer, setAnswer] = useState('')
  const [notice, setNotice] = useState<{ run: string; text: string }>()
  const text = run && notice?.run === run.id ? notice.text : run?.notice ?? ''
  const selectedId = run && selection?.run === run.id && selection.version === run.version
    ? selection.id : run?.verified_offer
  const offer = run?.offers.find(candidate => candidate.id === selectedId) ?? run?.offers[0]
  const active = busy || run?.status === 'planning'
  const settingsChanged = Boolean(run && (architecture !== run.architecture || scenario !== run.scenario))

  return (
    <>
      <header className="topbar">
        <div className="brand"><span className="brand-symbol"><TrainFront size={20} /></span>
          <span>Transit Replan Lab</span>
        </div>
        <div className="top-meta"><span className="connection-dot" />Local simulator <span className="top-location">İzmir, Türkiye</span></div>
      </header>
      <main className="workspace">
        <section className="overview">
          <div>
            <p className="location"><MapPin size={15} /> İzmir Metro M1 &amp; Konak Tram</p>
            <h1>Replan the journey.</h1>
            <p className="lede">Two riders, one meeting point. See how a tram closure changes their routes to Alsancak Gar.</p>
          </div>
          <div className="controls">
            <div className="selectors">
              <label>Coordinator<select aria-label="Coordinator" value={architecture} onChange={event => setArchitecture(event.target.value as Architecture)}>
                <option value="rules">Rules baseline</option>
                <option value="single">Single agent</option>
                <option value="three">Three agents</option>
                <option value="five">Five agents</option>
              </select></label>
              <label>Scenario<select aria-label="Scenario" value={scenario} onChange={event => setScenario(event.target.value as ScenarioId)}>
                <option value="demo">Konak closure</option>
                <option value="infeasible">Tight meeting window</option>
              </select></label>
              <button className="icon-button" type="button" title="Set up a new run" aria-label="Set up a new run"
                disabled={busy} onClick={() => { setAnswer(''); void start(scenario, architecture) }}>
                <RotateCcw size={17} />
              </button>
            </div>
            <button className="primary" type="button" disabled={active || !run || !text.trim()}
              onClick={() => {
                if (settingsChanged) {
                  void start(scenario, architecture)
                } else {
                  void send('disruptions', text)
                }
              }}>
              {active ? 'Working…' : settingsChanged ? 'Set up run' : 'Apply disruption'}
              <ArrowRight size={17} />
            </button>
          </div>
        </section>
        {error && <p className="error-banner" role="alert"><TriangleAlert size={17} />{error}</p>}
        {run && network && <>
          <div className="run-bar">
            <span className={`run-status run-status--${run.status}`} role="status">
              {run.status === 'verified' ? <Check size={15} /> : <CircleDot size={14} />}{statusLabels[run.status]}
            </span>
            <span><Clock3 size={15} />{run.service_date} · İzmir time</span>
            <span><GitBranch size={15} />Revision {run.version}</span>
            {connection === 'reconnecting' && <span className="reconnecting">Reconnecting…</span>}
          </div>
          <div className="board">
            <div className="map-board">
              <div className="plans">
                <PlanPanel label="Before disruption" title="Initial plan" network={network} run={run} offer={run.initial} />
                <PlanPanel label="After disruption" title="New plan" network={network} run={run} offer={offer} after />
              </div>
              <div className="legend" aria-label="Map legend">
                <span><i className="line-a" />Rider A</span><span><i className="line-b" />Rider B</span>
                <span><i className="line-walk" />Walking transfer</span>
                <span><TriangleAlert size={13} />Closure</span>
                <span className="attribution">GTFS · İzmir Metropolitan Municipality · CC BY 4.0</span>
              </div>
              {run.offers.length > 0 && <section className="offers" aria-label="Joint offers">
                <div className="section-head"><div><Waypoints size={18} /><h2>Joint offers</h2></div>
                  {run.initial && offer && <span>{elapsed(offer.meeting - run.initial.meeting)} later</span>}
                </div>
                <div className="offer-list">{run.offers.map((candidate, index) =>
                  <button key={candidate.id} type="button" aria-pressed={candidate.id === offer?.id}
                    onClick={() => setSelection({ run: run.id, version: run.version, id: candidate.id })}>
                    Offer {index + 1} <time>{time(candidate.meeting)}</time>
                    {run.verified_offer === candidate.id && <Check size={14} aria-label="Verified" />}
                  </button>)}
                </div>
              </section>}
            </div>
            <div className="right-column">
              <section className="incident-panel" aria-label="Disruption notice">
                <div className="section-head"><div><TriangleAlert size={17} /><h2>Disruption notice</h2></div></div>
                <textarea aria-label="Disruption notice text" maxLength={600} value={text}
                  disabled={active} onChange={event => setNotice({ run: run.id, text: event.target.value })} />
                {run.question && <form className="clarify" onSubmit={event => {
                  event.preventDefault()
                  if (answer.trim()) void send('clarifications', answer)
                }}>
                  <label>{run.question}<input required maxLength={400} value={answer}
                    onChange={event => setAnswer(event.target.value)} /></label>
                  <button type="submit" disabled={active}>Send clarification</button>
                </form>}
              </section>
              <Timeline events={events} live={connection === 'live'} />
            </div>
          </div>
        </>}
        {!run && !error && <p className="loading" role="status">Loading the timetable…</p>}
      </main>
    </>
  )
}
