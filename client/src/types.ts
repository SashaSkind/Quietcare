// WebSocket protocol v1 message types. Mirrors shared/protocol.md (read-only contract).

export type TriggerSource = 'fall' | 'audio_event' | 'scheduled' | 'manual';

export type Connectivity = 'wifi' | 'cellular' | 'offline' | 'unknown';

export interface DeviceState {
  battery: number;
  connectivity: Connectivity;
}

// ---- CLIENT -> BACKEND ----

export interface RegisterMessage {
  type: 'register';
  elder_id: string;
}

export interface TriggerMessage {
  type: 'trigger';
  elder_id: string;
  ts: string;
  trigger_source: TriggerSource;
  audio_clip_b64: string | null;
  frame_b64: string | null;
  device_state: DeviceState;
}

export interface AudioResponseMessage {
  type: 'audio_response';
  elder_id: string;
  ts: string;
  prompt_id: string;
  audio_clip_b64: string;
}

export interface HeartbeatMessage {
  type: 'heartbeat';
  elder_id: string;
  ts: string;
  device_state: DeviceState;
}

export type ClientMessage =
  | RegisterMessage
  | TriggerMessage
  | AudioResponseMessage
  | HeartbeatMessage;

// ---- BACKEND -> CLIENT ----

export interface SpeakMessage {
  type: 'speak';
  prompt_id: string;
  audio_b64: string;
  text?: string;
}

export interface ListenMessage {
  type: 'listen';
  prompt_id: string;
  duration_ms: number;
}

export type BackendState = 'idle' | 'checking_in' | 'escalating' | 'resolved';

export interface StatusMessage {
  type: 'status';
  state: BackendState;
}

export interface AckMessage {
  type: 'ack';
  received: string;
}

export type ServerMessage =
  | SpeakMessage
  | ListenMessage
  | StatusMessage
  | AckMessage;

// ---- UI-facing app status ----

export type AppStatus = 'all_good' | 'checking_in' | 'alerting';
