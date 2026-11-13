import { useEffect, useRef, useState } from 'react'
import {
  Activity, ArrowRight, Check, ChevronDown, CircleDot, Clock3, GitBranch, MapPin,
  RotateCcw, TrainFront, TriangleAlert, Waypoints,
} from 'lucide-react'
import type { Architecture, Itinerary, Network, Offer, OperatorMode, Preference, RoutePolicy, Run, RunEvent, ScenarioId } from './api'
import { elapsed, time } from './api'
import { RouteMap } from './RouteMap'
import { useRun } from './useRun'
import { DecisionSummary, ImpactComparison, Resilience, ReportEvidence, policyLabels } from './DecisionEvidence'

const statusLabels: Record<Run['status'], string> = {
  ready: 'Ready',
  planning: 'Replanning',
  clarification: 'Clarification needed',
  abstained: 'Disruption unresolved',
  verified: 'Verified',
  no_agreement: 'No agreement',
  infeasible: 'No feasible meeting',
  search_incomplete: 'Search incomplete',
  model_error: 'Model error',
  system_error: 'Internal error',
  verification_failed: 'Verification failed',
}

const roleLabels: Record<string, string> = {
  operator: 'Operator', router: 'Route engine', rider_a: 'Rider 1', rider_b: 'Rider 2',
  analyst: 'Transfer analyst', mediator: 'Mediator', verifier: 'Verifier', system: 'System',
}

const roleOrder = ['operator', 'rider_a', 'rider_b', 'analyst', 'mediator', 'verifier']

function name(network: Network | undefined, id: string | undefined) {
  return network?.stops.find(stop => stop.id === id)?.name ?? id ?? '—'
}

function mode(trip: string) {
  return trip.startsWith('metro:') ? 'Metro' : 'Tram'
}

function Journey({ route, rider, network }: { route: Itinerary; rider: 'A' | 'B'; network: Network }) {
  const change = route.legs.find(leg => leg.kind === 'walk')
  const ride = route.legs.find(leg => leg.kind === 'ride')
  let summary = 'At the meeting stop'
  if (change) summary = `Via ${name(network, change.origin)}`
  else if (ride) summary = route.legs.length > 1 ? 'Scheduled connections' : `Direct ${mode(ride.trip).toLowerCase()}`
  return (
    <div className="journey">
      <span className={`rider-key rider-key--${rider.toLowerCase()}`} aria-label={`Rider ${rider === 'A' ? '1' : '2'}`}>{rider === 'A' ? '1' : '2'}</span>
      <div>
        <strong>{name(network, route.origin)}</strong>
        <span>{summary}</span>
      </div>
      <time>{time(route.arrival)}</time>
    </div>
  )
}

function newPlanMessage(status: Run['status']) {
  switch (status) {
    case 'planning': return 'Searching the affected timetable and collecting rider decisions.'
    case 'clarification': return 'Clarify the disruption to continue replanning.'
    case 'abstained': return 'Add the missing information and submit a new report.'
    case 'infeasible': return 'The search completed without a joint arrival in this meeting window.'
    case 'search_incomplete': return 'The search reached its resource limit before feasibility could be determined.'
    case 'model_error': return 'The coordinator could not complete this revision.'
    default: return 'Apply a disruption to compare the replanned journeys.'
  }
}

function OfferEvidence({ offer, run, network, failedOffer }: {
  offer: Offer; run: Run; network: Network; failedOffer: unknown
}) {
  const verified = run.status === 'verified' && run.verified_offer === offer.id
  const selectedVotes = run.votes.filter(vote => vote.version === offer.version && vote.offer_id === offer.id)
  const verdict = verified ? 'Timetable check passed'
    : run.status === 'verification_failed' && failedOffer === offer.id ? 'Timetable check failed'
    : 'No verification recorded'
  return (
    <details className="evidence" key={offer.id}>
      <summary>
        <span><strong>Offer evidence</strong><small>{offer.id} · Revision {offer.version}</small></span>
        <span className={verified ? 'evidence-verdict verified' : 'evidence-verdict'}>
          {verified && <Check size={14} />} {verdict}
        </span>
        <ChevronDown size={15} />
      </summary>
      <ReportEvidence evidence={run.evidence} />
      <div className="evidence-riders">
        {(['a', 'b'] as const).map(rider => {
          const route = offer[rider]
          const vote = selectedVotes.find(item => item.rider === rider)
          const waiting = offer.meeting - route.arrival
          return <section className="evidence-rider" key={rider} aria-label={`Rider ${rider === 'a' ? '1' : '2'} evidence`}>
            <div className="evidence-rider-heading">
              <strong>Rider {rider === 'a' ? '1' : '2'}</strong>
              <span>{vote ? vote.accepted ? 'Accepted' : 'Rejected' : 'No vote'}</span>
            </div>
            <p>Arrives {time(route.arrival)} · {waiting ? `waits ${elapsed(waiting)}` : 'no wait'}</p>
            {route.legs.length > 0 ? <ol>{route.legs.map((leg, index) =>
              <li key={index}>
                <span>{leg.kind === 'ride' ? mode(leg.trip) : 'Walk'} · {time(leg.departure)}–{time(leg.arrival)}</span>
                <strong>{name(network, leg.origin)}{leg.kind === 'walk' && ` (${mode(leg.origin)})`}
                  {' → '}{name(network, leg.destination)}{leg.kind === 'walk' && ` (${mode(leg.destination)})`}
                </strong>
                {leg.kind === 'ride' && <small>{leg.trip} · {leg.service_date}</small>}
              </li>,
            )}</ol> : <p>Already at {name(network, route.destination)}.</p>}
          </section>
        })}
      </div>
    </details>
  )
}

function disruptionSummary(incident: NonNullable<Run['incident']>, network: Network) {
  switch (incident.kind) {
    case 'stop_closure':
      return `${name(network, incident.stop)} closed · ${time(incident.start)}–${time(incident.end)}`
    case 'trip_cancellation':
      return `Trip ${incident.trip} cancelled`
    case 'trip_delay':
      return `Trip ${incident.trip} delayed ${elapsed(incident.seconds)}`
  }
}

function meetingDifference(meeting: number, initial: number) {
  const difference = meeting - initial
  return difference === 0 ? 'Same meeting time'
    : `${elapsed(Math.abs(difference))} ${difference > 0 ? 'later' : 'earlier'}`
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
          ? newPlanMessage(run.status)
          : 'No initial joint journey in this window.'}</p>}
      </div>
    </section>
  )
}

function Timeline({ events, live }: { events: RunEvent[]; live: boolean }) {
  const list = useRef<HTMLOListElement>(null)
  useEffect(() => {
    const timeline = list.current
    if (timeline) timeline.scrollTop = timeline.scrollHeight
  }, [events.length])
  return (
    <aside className="activity-panel" aria-label="Simulation activity">
      <header className="section-head">
        <div><Activity size={18} /><h2>Activity</h2></div>
        {live && <span className="live-indicator">Live</span>}
      </header>
      {events.length ? <ol ref={list} className="timeline" aria-live="polite">
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
  const { network, run, settings, events, connection, busy, error, retry, start, send, recover } = useRun()
  const [architecture, setArchitecture] = useState<Architecture>('rules')
  const [legacy] = useState(() => typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('workflow') === 'legacy')
  const [scenario, setScenario] = useState<ScenarioId>(legacy ? 'demo' : 'resilience')
  const [routePolicy, setRoutePolicy] = useState<RoutePolicy>('earliest')
  const [operatorMode, setOperatorMode] = useState<OperatorMode | 'default'>('default')
  const [preferenceA, setPreferenceA] = useState<Preference | ''>('')
  const [preferenceB, setPreferenceB] = useState<Preference | ''>('')
  const [selection, setSelection] = useState<{ run: string; version: number; id: string }>()
  const [answer, setAnswer] = useState('')
  const [notice, setNotice] = useState<{ run: string; text: string }>()
  const text = run && notice?.run === run.id ? notice.text : run?.notice ?? ''
  const selectedId = run && selection?.run === run.id && selection.version === run.version
    ? selection.id : run?.verified_offer
  const offer = run?.offers.find(candidate => candidate.id === selectedId) ?? run?.offers[0]
  const revisionEvents = events.filter(event => event.version === run?.version)
  const failedOffer = revisionEvents.findLast(event => event.kind === 'verification_failed')?.details.offer_id
  const active = busy || run?.status === 'planning'
  const settingsChanged = Boolean(run && (
    architecture !== run.architecture || scenario !== run.scenario ||
    routePolicy !== (settings?.route_policy ?? 'earliest') ||
    operatorMode !== (settings?.operator_mode ?? 'default') ||
    preferenceA !== (settings?.preference_a ?? '') || preferenceB !== (settings?.preference_b ?? '')
  ))
  const question = run?.status === 'clarification' ? run.evidence?.intake?.question : undefined
  const analysis = run?.evidence?.offers?.find(item => item.offer_id === offer?.id)

  function setup() {
    setAnswer('')
    void start(scenario, architecture, {
      workflow: legacy ? 'legacy' : 'vnext', route_policy: routePolicy,
      operator_mode: operatorMode === 'default' ? null : operatorMode,
      preference_a: preferenceA || null, preference_b: preferenceB || null,
    })
  }

  return (
    <>
      <a className="skip-link" href="#main">Skip to replanning</a>
      <header className="topbar">
        <div className="brand"><span className="brand-symbol"><TrainFront size={20} /></span>
          <span>Transit Replan Lab</span>
        </div>
        <div className="top-meta"><span className="connection-dot" />Local simulator <span className="top-location">İzmir, Türkiye</span></div>
      </header>
      <main className="workspace" id="main" tabIndex={-1}>
        <section className="overview">
          <div>
            <p className="location"><MapPin size={15} /> İzmir Metro M1 &amp; Konak Tram</p>
            <h1>Replan the journey.</h1>
            <p className="lede">Compare two riders’ routes to Alsancak Gar, then trace which disruption changed their meeting.</p>
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
                {!legacy && <option value="resilience">Ambiguous closure</option>}
                <option value="demo">Konak closure</option>
                <option value="infeasible">Tight meeting window</option>
              </select></label>
              <button className="icon-button" type="button" title="Set up a new run" aria-label="Set up a new run"
                disabled={busy} onClick={setup}>
                <RotateCcw size={17} />
              </button>
            </div>
            {!legacy && <details className="run-settings">
              <summary>Run settings</summary>
              <div className="run-setting-fields">
                <label>Ranking<select aria-label="Ranking" value={routePolicy} onChange={event => setRoutePolicy(event.target.value as RoutePolicy)}>
                  {Object.entries(policyLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}
                </select></label>
                <label>Operator<select aria-label="Operator" value={operatorMode} onChange={event => setOperatorMode(event.target.value as OperatorMode | 'default')}>
                  <option value="default">Release default</option><option value="rules">Rules</option>
                  <option value="lexicon">Lexicon · no model</option><option value="hybrid">Hybrid experiment</option>
                </select></label>
                {([['Rider 1', preferenceA, setPreferenceA], ['Rider 2', preferenceB, setPreferenceB]] as const)
                  .map(([rider, preference, update]) => <label key={rider}>{rider} preference
                    <select value={preference} onChange={event => update(event.target.value as Preference | '')}>
                      <option value="">None</option><option value="earlier_arrival">Earlier arrival</option><option value="fewer_transfers">Fewer transfers</option>
                      <option value="less_wait">Less waiting</option><option value="less_walking">Less walking</option>
                    </select>
                  </label>)}
              </div>
            </details>}
            <button className="primary" type="button" disabled={active || !run || Boolean(retry) || (!settingsChanged && !text.trim())}
              onClick={() => {
                if (settingsChanged) {
                  setup()
                } else {
                  void send('disruptions', text)
                }
              }}>
              {active ? 'Working…' : settingsChanged ? 'Set up run' : 'Apply disruption'}
              <ArrowRight size={17} />
            </button>
          </div>
        </section>
        {error && <div className="error-banner" role="alert">
          <TriangleAlert size={17} /><span>{error}</span>
          {(retry || !run) && <button type="button" disabled={busy}
            onClick={run ? recover : setup}>
            {retry === 'snapshot' ? 'Refresh outcome' : 'Retry'}
          </button>}
        </div>}
        {run && network && <>
          <div className="run-bar">
            <span className={`run-status run-status--${run.status}`} role="status">
              {run.status === 'verified' ? <Check size={15} /> : <CircleDot size={14} />}{statusLabels[run.status]}
            </span>
            <span><Clock3 size={15} />{run.service_date} · İzmir time</span>
            <span><GitBranch size={15} />Revision {run.version}</span>
            {run.metrics.calls > 0 && <span><Activity size={15} />{run.metrics.calls} model calls
              {run.metrics.backend === 'replay' && ' · Recorded replay'}
              {run.metrics.backend === 'ollama' && ' · Local Ollama'}
              {run.metrics.output_tokens > 0 && ` · ${(run.metrics.input_tokens + run.metrics.output_tokens).toLocaleString()} tokens · ${(run.metrics.model_ms / 1000).toFixed(1)} s`}
            </span>}
            {connection === 'reconnecting'  && <span className="reconnecting">Reconnecting…</span>}
          </div>
          <DecisionSummary run={run} offer={offer} event={run.incident
            ? disruptionSummary(run.incident, network)
            : run.status === 'ready' ? text : run.evidence?.notice_text ?? text} />
          <ImpactComparison intake={run.evidence?.intake} network={network} />
          {(question || run.question) && <section className="clarification-panel" aria-label="Clarify disruption">
            {question && <div className="question-options" aria-label="Clarification options">
              {question.options?.map(option => <button key={option.id} type="button"
                disabled={active || Boolean(retry)}
                onClick={() => void send('clarifications', '', option.id)}>{option.label}</button>)}
              <button type="button" disabled={active || Boolean(retry)}
                onClick={() => void send('clarifications', '', 'unknown')}>I don’t know</button>
            </div>}
            {run.question && <form className="clarify" onSubmit={event => {
              event.preventDefault()
              if (answer.trim()) void send('clarifications', answer)
            }}>
              <label>{run.question}<input required maxLength={400} value={answer}
                onChange={event => setAnswer(event.target.value)} /></label>
              <button type="submit" disabled={active || Boolean(retry)}>Send clarification</button>
            </form>}
          </section>}
          <div className="board">
            <div className="map-board">
              <div className="plans">
                <PlanPanel label="Before disruption" title="Initial plan" network={network} run={run} offer={run.initial} />
                <PlanPanel label="After disruption" title="New plan" network={network} run={run} offer={offer} after />
              </div>
              <div className="legend" aria-label="Map legend">
                <span><i className="line-a" />Rider 1 · solid</span><span><i className="line-b" />Rider 2 · long dashes</span>
                <span><i className="line-walk" />Walk · short dashes</span>
                <span className="closure-key"><TriangleAlert size={13} aria-hidden="true" />× Closure</span>
                <span className="attribution">GTFS · İzmir Metropolitan Municipality · CC BY 4.0</span>
              </div>
              {run.offers.length > 0 && <section className="offers" aria-label="Joint offers">
                <div className="section-head"><div><Waypoints size={18} /><h2>Joint offers</h2></div>
                  {run.initial && offer && <span>{meetingDifference(offer.meeting, run.initial.meeting)}</span>}
                </div>
                <div className="offer-list">{run.offers.map((candidate, index) =>
                  <button key={candidate.id} type="button" aria-pressed={candidate.id === offer?.id}
                    onClick={() => setSelection({ run: run.id, version: run.version, id: candidate.id })}>
                    {run.evidence?.offers?.find(item => item.offer_id === candidate.id)?.policies
                      ?.map(policy => policyLabels[policy]).join(' / ') || `Offer ${index + 1}`} <time>{time(candidate.meeting)}</time>
                    {run.verified_offer === candidate.id && <Check size={14} aria-label="Verified" />}
                  </button>)}
                </div>
                {analysis && <Resilience key={`resilience-${analysis.offer_id}`} analysis={analysis} network={network} />}
                {offer && <OfferEvidence key={offer.id} offer={offer} run={run}
                  network={network} failedOffer={failedOffer} />}
              </section>}
            </div>
            <div className="right-column">
              <section className="incident-panel" aria-label="Disruption notice">
                <div className="section-head"><div><TriangleAlert size={17} /><h2>Disruption notice</h2></div></div>
                <textarea aria-label="Disruption notice text" maxLength={600} value={text}
                  disabled={active || Boolean(retry)} onChange={event => setNotice({ run: run.id, text: event.target.value })} />
              </section>
              <Timeline events={revisionEvents} live={connection === 'live'} />
            </div>
          </div>
        </>}
        {!run && !error && <p className="loading" role="status">Loading the timetable…</p>}
      </main>
    </>
  )
}
