import { Check, ChevronDown } from 'lucide-react'
import type { Network, Offer, Run } from './api'
import { elapsed, time } from './api'
import { ReportEvidence } from './DecisionEvidence'
import { mode, name } from './format'

export function OfferEvidence({ offer, run, network, failedOffer }: {
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
