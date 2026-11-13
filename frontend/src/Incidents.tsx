import { TriangleAlert, X } from 'lucide-react'
import type { Run } from './api'
import type { Key } from './i18n'

type Props = {
  incidents: Run['incidents']
  busy: boolean
  describe: (incident: NonNullable<Run['incident']>) => string
  t: (key: Key) => string
  onRetract: (id: string) => void
}

export function Incidents({ incidents, busy, describe, t, onRetract }: Props) {
  const list = incidents ?? []
  return (
    <section className="incident-list" aria-label={t('incidents.title')}>
      <div className="section-head"><div><TriangleAlert size={17} /><h2>{t('incidents.title')}</h2></div></div>
      {list.length === 0 ? <p className="muted">{t('incidents.empty')}</p> : (
        <ul>
          {list.map(item => (
            <li key={item.id}>
              <span>{describe(item.disruption)}</span>
              <button type="button" disabled={busy} onClick={() => onRetract(item.id)}
                aria-label={`${t('incidents.retract')}: ${describe(item.disruption)}`}>
                <X size={14} aria-hidden="true" />{t('incidents.retract')}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
