// ============================================================================
// Types mirrored from the Quietcare FastAPI backend (server/app/*).
// Keep in sync with shared/protocol.md and the endpoint response shapes.
// ============================================================================

export interface CaretakerInfo {
  name?: string;
  phone?: string;
  relationship?: string;
}

export interface ElderProfile {
  name?: string;
  age?: number | null;
  medications?: string[];
  conditions?: string[];
  prior_falls?: number;
  notes?: string;
  caretaker?: CaretakerInfo;
  [key: string]: unknown;
}

export interface ElderDetail {
  elder_id: string;
  profile: ElderProfile;
}

export interface ListEldersResponse {
  elders: string[];
}

// ---- Events / incidents ------------------------------------------------------

export type TriggerSource =
  | 'fall'
  | 'inactivity'
  | 'audio_event'
  | 'geofence'
  | 'scheduled'
  | 'manual'
  | 'unknown';

export interface IncidentEvent {
  kind: 'incident';
  ts: string;
  trigger_source: TriggerSource;
  final_state: string;
  fsm_trace?: string[];
  escalated: boolean;
  last_transcript?: string;
  summary?: string;
  risk_score?: number;
  risk_level?: string;
}

export interface MedicationEvent {
  kind: 'medication';
  ts: string;
  medication: string;
  scheduled_time?: string;
  status: 'confirmed' | 'missed';
  transcript?: string;
  note?: string;
}

export type EventRecord = IncidentEvent | MedicationEvent | Record<string, unknown>;

export interface EventsResponse {
  elder_id: string;
  count: number;
  events: EventRecord[];
}

// ---- Summary -----------------------------------------------------------------

export interface SummaryResponse {
  elder_id: string;
  question: string;
  summary: string;
}

// ---- Wellness ----------------------------------------------------------------

export interface AdherenceSummary {
  confirmed: number;
  missed: number;
  total: number;
  adherence_rate: number | null;
}

export interface WellnessTrends {
  days: number;
  total_events: number;
  incidents: number;
  escalations: number;
  check_ins: number;
  by_trigger_source: Record<string, number>;
  wandering_alerts: number;
  medication: AdherenceSummary;
  all_normal: boolean;
}

export interface WellnessResponse {
  elder_id: string;
  days: number;
  trends: WellnessTrends;
  summary: string;
}

// ---- Medications -------------------------------------------------------------

export interface MedicationItem {
  name: string;
  time: string; // "HH:MM"
  dose?: string | null;
}

export interface MedicationsResponse {
  elder_id: string;
  medications: MedicationItem[];
}

export interface AdherenceResponse {
  elder_id: string;
  adherence: AdherenceSummary;
}

export interface RemindResponse {
  elder_id: string;
  event: MedicationEvent;
}

// ---- Everyday-care actions ---------------------------------------------------

export interface BrowserTask {
  ok: boolean;
  detail: string;
  mocked: boolean;
  session_id?: string | null;
  replay_url?: string | null;
}

export interface RefillResponse {
  elder_id: string;
  task: BrowserTask;
}

export interface CallBridgeResponse {
  elder_id: string;
  prompted: boolean;
}

// ---- Emergency confirmation --------------------------------------------------

export interface ConfirmationResponse {
  elder_id: string;
  status: 'pending' | 'approved' | 'rejected' | string;
  reason?: string;
}

export interface Confirm911Response {
  [key: string]: unknown;
}

// ---- Health / integrations ---------------------------------------------------

export interface HealthResponse {
  status: string;
  providers: Record<string, string>;
}

// ---- Security scan -----------------------------------------------------------

export interface ScanResult {
  ok: boolean;
  url: string;
  severity_level: string;
  vulnerability_score: number;
  scanned_hosts: number;
  reachable_hosts: number;
  mcp_endpoints: number;
  chain_attacks_detected: number;
  vulnerabilities: unknown[];
  mocked: boolean;
  detail: string;
}

// ---- Admin: create elder -----------------------------------------------------

export interface CreateElderBody {
  elder_id: string;
  name: string;
  age?: number | null;
  medications?: string[];
  conditions?: string[];
  prior_falls?: number;
  notes?: string;
  caretaker?: CaretakerInfo;
}

export interface CreateElderResponse {
  elder_id: string;
  device_token: string;
  profile: ElderProfile;
}

// ---- UI-derived status -------------------------------------------------------

export type CareStatus = 'ok' | 'checking_in' | 'alerting';
