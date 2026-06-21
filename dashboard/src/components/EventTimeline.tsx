import {
  AlertTriangle,
  Pill,
  Activity,
  CheckCircle2,
  XCircle,
  MapPin,
  PhoneCall,
} from 'lucide-react';
import { formatTime, humanize } from '@/lib/utils';
import { isIncident } from '@/lib/status';
import type { EventRecord, IncidentEvent, MedicationEvent } from '@/lib/types';

function IncidentRow({ e }: { e: IncidentEvent }) {
  const Icon = e.trigger_source === 'geofence' ? MapPin : e.escalated ? AlertTriangle : Activity;
  return (
    <div className="flex gap-3">
      <div
        className={
          'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ' +
          (e.escalated ? 'bg-alert-soft text-alert-fg' : 'bg-muted text-muted-foreground')
        }
      >
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{humanize(e.trigger_source)} check-in</span>
          {e.escalated ? (
            <span className="rounded-full bg-alert-soft px-2 py-0.5 text-xs font-semibold text-alert-fg">
              <PhoneCall className="mr-1 inline h-3 w-3" />escalated
            </span>
          ) : (
            <span className="rounded-full bg-ok-soft px-2 py-0.5 text-xs font-semibold text-ok-fg">resolved</span>
          )}
          <span className="ml-auto text-xs text-muted-foreground">{formatTime(e.ts)}</span>
        </div>
        {e.summary && <p className="mt-1 text-sm text-muted-foreground">{e.summary}</p>}
        {e.last_transcript && (
          <p className="mt-1 text-sm italic text-foreground/80">“{e.last_transcript}”</p>
        )}
        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
          <span>final: {humanize(e.final_state)}</span>
          {e.risk_level && <span>risk: {e.risk_level}{e.risk_score != null ? ` (${e.risk_score})` : ''}</span>}
        </div>
      </div>
    </div>
  );
}

function MedicationRow({ e }: { e: MedicationEvent }) {
  const confirmed = e.status === 'confirmed';
  return (
    <div className="flex gap-3">
      <div
        className={
          'mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ' +
          (confirmed ? 'bg-ok-soft text-ok-fg' : 'bg-warn-soft text-warn-fg')
        }
      >
        <Pill className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium">{e.medication || 'Medication'}</span>
          {confirmed ? (
            <CheckCircle2 className="h-4 w-4 text-ok" />
          ) : (
            <XCircle className="h-4 w-4 text-warn" />
          )}
          <span className="text-sm text-muted-foreground">{confirmed ? 'taken' : 'missed'}</span>
          <span className="ml-auto text-xs text-muted-foreground">{formatTime(e.ts)}</span>
        </div>
        {e.scheduled_time && (
          <p className="mt-0.5 text-xs text-muted-foreground">scheduled {e.scheduled_time}{e.note ? ` · ${e.note}` : ''}</p>
        )}
      </div>
    </div>
  );
}

export function EventTimeline({ events }: { events: EventRecord[] }) {
  if (!events.length) {
    return (
      <div className="rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
        No history yet.
      </div>
    );
  }
  // Most recent first.
  const ordered = [...events].reverse();
  return (
    <div className="space-y-5">
      {ordered.map((e, i) => (
        <div key={i}>
          {isIncident(e) ? (
            <IncidentRow e={e} />
          ) : (e as MedicationEvent).kind === 'medication' ? (
            <MedicationRow e={e as MedicationEvent} />
          ) : null}
        </div>
      ))}
    </div>
  );
}
