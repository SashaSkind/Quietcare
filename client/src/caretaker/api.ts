// Thin REST client for the in-app caretaker dashboard. Talks to the Quietcare
// FastAPI backend (config.API_URL). React Native fetch has no CORS, so this
// works directly against the LAN backend on a physical device.

import { API_URL, ELDER_ID } from '../config';

export interface ElderProfile {
  name?: string;
  age?: number | null;
  conditions?: string[];
  medications?: string[];
  caretaker?: { name?: string; phone?: string };
}

export interface IncidentEvent {
  kind: 'incident';
  ts: string;
  trigger_source: string;
  final_state: string;
  escalated: boolean;
  last_transcript?: string;
  summary?: string;
}

export interface MedicationEvent {
  kind: 'medication';
  ts: string;
  medication: string;
  scheduled_time?: string;
  status: 'confirmed' | 'missed';
}

export type EventRecord = IncidentEvent | MedicationEvent | { kind?: string; ts?: string };

export interface AdherenceSummary {
  confirmed: number;
  missed: number;
  total: number;
  adherence_rate: number | null;
}

export interface WellnessTrends {
  days: number;
  check_ins: number;
  incidents: number;
  escalations: number;
  wandering_alerts: number;
  medication: AdherenceSummary;
  all_normal: boolean;
}

export interface MedicationItem {
  name: string;
  time: string;
  dose?: string | null;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const careApi = {
  elder: (id = ELDER_ID) =>
    getJson<{ elder_id: string; profile: ElderProfile }>(`/elders/${id}`),

  summary: (id = ELDER_ID) =>
    getJson<{ summary: string }>(`/elders/${id}/summary`),

  wellness: (id = ELDER_ID, days = 7) =>
    getJson<{ trends: WellnessTrends; summary: string }>(
      `/elders/${id}/wellness?days=${days}`,
    ),

  medications: (id = ELDER_ID) =>
    getJson<{ medications: MedicationItem[] }>(`/elders/${id}/medications`),

  adherence: (id = ELDER_ID) =>
    getJson<{ adherence: AdherenceSummary }>(`/elders/${id}/adherence`),

  events: (id = ELDER_ID, limit = 25) =>
    getJson<{ events: EventRecord[] }>(`/elders/${id}/events?limit=${limit}`),

  confirmation: (id = ELDER_ID) =>
    getJson<{ status: string; reason?: string }>(`/incidents/${id}/confirmation`).catch(
      () => null,
    ),

  callBridge: (id = ELDER_ID) =>
    postJson<{ prompted: boolean }>(`/elders/${id}/call-bridge`, {}),

  // Elder-side: report an on-device fall so it surfaces on the dashboard.
  reportIncident: (
    body: { trigger_source?: string; escalated?: boolean; summary?: string; last_transcript?: string },
    id = ELDER_ID,
  ) => postJson<{ event: IncidentEvent }>(`/elders/${id}/demo/incident`, body),
};

export function isIncident(e: EventRecord): e is IncidentEvent {
  return (e as { kind?: string }).kind === 'incident';
}
export function isMedication(e: EventRecord): e is MedicationEvent {
  return (e as { kind?: string }).kind === 'medication';
}
