import { useEffect, useRef } from 'react'
import { Activity, ChevronDown } from 'lucide-react'
import type { RunEvent } from './api'
import { roleLabels, roleOrder } from './format'

export function Timeline({ events, live }: { events: RunEvent[]; live: boolean }) {
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
      {events.length ? <ol ref={list} className="timeline" aria-live="polite" tabIndex={0}>
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
