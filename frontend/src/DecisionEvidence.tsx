import { useState } from 'react'
import type { components } from './api.generated'
import type { Intake, Network, Offer, OfferAnalysis, RoutePolicy, Run } from './api'
import { elapsed, time } from './api'

export const policyLabels: Record<RoutePolicy, string> = {
  earliest: 'Earliest',
  robust: 'Most resilient',
  balanced: 'Balanced',
}

function stopName(network: Network, id: string) {
  return network.stops.find(stop => stop.id === id)?.name ?? id
}

export function DecisionSummary({ run, offer, event }: { run: Run; offer?: Offer; event: string }) {
  const verified = run.status === 'verified' && run.verified_offer === offer?.id
  const accepted = new Set(run.votes.filter(vote => vote.accepted && vote.version === run.version &&
    vote.offer_id === offer?.id).map(vote => vote.rider)).size
  const policies = run.evidence?.offers.find(item => item.offer_id === offer?.id)?.policies ?? []
  return <section className="decision-summary" aria-label="Decision summary">
    <div className="decision-event"><h2>What changed</h2><p>{event}</p>
      <small>{run.incident ? 'Applied to this revision' : run.status === 'ready'
        ? 'Draft report' : run.status === 'abstained' ? 'No disruption applied' : 'Report awaiting resolution'}</small></div>
    <div><h2>Selected offer</h2><p>{offer
      ? `${policies.map(policy => policyLabels[policy]).join(' / ') || offer.id} · ${time(offer.meeting)}`
      : 'No offer selected'}</p><small>{offer ? `${offer.id} · Revision ${offer.version}` : 'Resolve the report to compare routes.'}</small></div>
    <div><h2>Verification</h2><p>{verified
      ? `${accepted}/2 current rider acceptances. Independent timetable and hard-constraint checks passed.`
      : offer ? 'This is a proposal. No verification is recorded for this selection.'
      : 'Verification follows route search and both rider acceptances.'}</p>
      <small>Archived timetable · synthetic disruptions, not live service</small></div>
  </section>
}

export function ImpactComparison({ intake, network }: { intake?: Intake | null; network: Network }) {
  if (!intake?.impacts?.length) return null
  return (
    <section className="interpretations" aria-label="Possible interpretations">
      <header><h2>Possible interpretations</h2><p>Timetable previews before applying the disruption</p></header>
      <div className="interpretation-grid">
        {intake.impacts.map(({ hypothesis, status, preview }) => {
          const incident = hypothesis.incident
          const label = incident.kind === 'stop_closure'
            ? `${stopName(network, incident.stop)} closure` : incident.trip
          return <article className="interpretation" key={hypothesis.id}>
            <h3>{label}</h3>
            {status === 'feasible' && preview
              ? <p>Joint arrival <strong>{time(preview.meeting)}</strong></p>
              : <p>{status === 'infeasible' ? 'No feasible meeting' : 'Search incomplete'}</p>}
          </article>
        })}
      </div>
    </section>
  )
}

function addedTime(delta: number | null | undefined) {
  if (delta == null) return '—'
  return delta < 0 ? `−${elapsed(-delta)}` : delta > 0 ? `+${elapsed(delta)}` : '0 min'
}

export function Resilience({ analysis, network }: { analysis: OfferAnalysis; network: Network }) {
  const [preview, setPreview] = useState(false)
  const check = analysis.counterfactual
  return (
    <section className="resilience" aria-label="Scenario resilience">
      <dl>
        <div><dt>Simulated joint arrivals</dt><dd>{analysis.successful} / {analysis.total}</dd></div>
        <div><dt>Tightest transfer</dt><dd>{analysis.transfer_slack == null ? 'Direct' : elapsed(analysis.transfer_slack)}</dd></div>
        <div><dt>Added trip time</dt><dd>Rider 1 {addedTime(analysis.extra_seconds_a)} <span>·</span> Rider 2 {addedTime(analysis.extra_seconds_b)}</dd></div>
      </dl>
      {check && <button type="button" className="what-if" aria-expanded={preview} onClick={() => setPreview(open => !open)}>
        What if the incoming trip runs 2 minutes late?
      </button>}
      {preview && check && <p className="what-if-result">
        {check.failure?.startsWith('missed_connection:')
          ? `Missed connection at ${stopName(network, check.failure.slice('missed_connection:'.length))}.`
          : check.meeting != null ? `Joint arrival at ${time(check.meeting)}.`
          : 'The fixed itinerary no longer meets the rider constraints.'}
        <small>Trip {check.trip} · synthetic delay</small>
      </p>}
    </section>
  )
}

export function ReportEvidence({ evidence }: { evidence?: components['schemas']['RunEvidence'] | null }) {
  const selected = evidence?.intake?.selected
  if (!evidence || !selected) return null
  return <div className="report-evidence">
    <p>Report evidence <small>Timetable {evidence.snapshot.slice(0, 12)} · {evidence.scenario_profile}</small></p>
    <ul>
      {selected.facts.map(({ slot, span, value }) => {
        const text = span?.source === 'answer' ? evidence.answer_text : evidence.notice_text
        const quote = span && text && Array.from(text).slice(span.start, span.end).join('')
        return <li key={slot}>{slot} <mark>{quote || String(value)}</mark></li>
      })}
    </ul>
  </div>
}
