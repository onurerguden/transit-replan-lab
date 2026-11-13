import { Check, CircleDot, MapPin } from 'lucide-react'
import type { Itinerary, Network, Offer, Run } from './api'
import { time } from './api'
import { RouteMap } from './RouteMap'
import { mode, name } from './format'

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

export function PlanPanel({ label, title, network, run, offer, after }: {
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
