import type { CareStatus, EventRecord, IncidentEvent } from './types';

export function isIncident(e: EventRecord): e is IncidentEvent {
  return (e as { kind?: string }).kind === 'incident';
}

export function latestIncident(events: EventRecord[] | undefined): IncidentEvent | undefined {
  if (!events) return undefined;
  const incidents = events.filter(isIncident);
  return incidents.length ? incidents[incidents.length - 1] : undefined;
}

export function lastSeen(events: EventRecord[] | undefined): string | undefined {
  if (!events || !events.length) return undefined;
  const ts = (events[events.length - 1] as { ts?: string }).ts;
  return ts;
}

/**
 * Derive a caretaker-facing status. `alerting` always wins when a 911
 * confirmation is pending. Otherwise a very recent incident reads as
 * "checking in", an escalated incident as "alerting", else "all good".
 */
export function careStatus(
  events: EventRecord[] | undefined,
  hasPendingConfirmation: boolean,
): CareStatus {
  if (hasPendingConfirmation) return 'alerting';
  const inc = latestIncident(events);
  if (!inc) return 'ok';
  const ageMs = Date.now() - new Date(inc.ts).getTime();
  const RECENT = 2 * 60 * 1000;
  if (inc.escalated && ageMs < 10 * 60 * 1000) return 'alerting';
  if (ageMs < RECENT) return 'checking_in';
  return 'ok';
}

export const STATUS_LABEL: Record<CareStatus, string> = {
  ok: 'All good',
  checking_in: 'Checking in',
  alerting: 'Needs attention',
};
