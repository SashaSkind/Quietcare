import {
  HEARTBEAT_INTERVAL_MS,
  RECONNECT_BASE_DELAY_MS,
  RECONNECT_MAX_DELAY_MS,
  ELDER_ID,
} from '../config';
import { breadcrumb, captureException } from '../sentry';
import type {
  ClientMessage,
  ServerMessage,
  DeviceState,
} from '../types';

export type ConnectionState = 'connecting' | 'open' | 'closed';

export interface WebSocketClientHandlers {
  onMessage: (msg: ServerMessage) => void;
  onLog: (direction: 'in' | 'out' | 'info', text: string) => void;
  onStateChange: (state: ConnectionState) => void;
  getDeviceState: () => DeviceState;
}

/**
 * Resilient WebSocket client implementing protocol v1:
 * - sends `register` on open
 * - sends `heartbeat` every 30s
 * - auto-reconnects with exponential backoff
 * - logs every message in/out
 */
export class WebSocketClient {
  private url: string;
  private handlers: WebSocketClientHandlers;
  private ws: WebSocket | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private shouldRun = false;

  constructor(url: string, handlers: WebSocketClientHandlers) {
    this.url = url;
    this.handlers = handlers;
  }

  connect(): void {
    this.shouldRun = true;
    this.openSocket();
  }

  private openSocket(): void {
    this.clearReconnect();
    this.handlers.onStateChange('connecting');
    this.handlers.onLog('info', `Connecting to ${this.url} …`);
    breadcrumb('ws', 'connecting', { url: this.url });

    try {
      this.ws = new WebSocket(this.url);
    } catch (err) {
      captureException(err, { stage: 'ws_construct', url: this.url });
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.handlers.onStateChange('open');
      this.handlers.onLog('info', 'WebSocket open');
      breadcrumb('ws', 'open');
      this.send({ type: 'register', elder_id: ELDER_ID });
      this.startHeartbeat();
    };

    this.ws.onmessage = (event: { data: unknown }) => {
      this.handleRawMessage(event.data);
    };

    this.ws.onerror = (event: Event) => {
      // RN WebSocket error events carry a `message` field.
      const message = (event as unknown as { message?: string }).message ?? 'unknown';
      this.handlers.onLog('info', `WebSocket error: ${message}`);
      breadcrumb('ws', 'error', { message });
    };

    this.ws.onclose = (event: { code?: number }) => {
      this.stopHeartbeat();
      this.handlers.onStateChange('closed');
      this.handlers.onLog('info', `WebSocket closed (code ${event.code ?? '?'})`);
      breadcrumb('ws', 'close', { code: event.code });
      if (this.shouldRun) {
        this.scheduleReconnect();
      }
    };
  }

  private handleRawMessage(raw: unknown): void {
    if (typeof raw !== 'string') {
      this.handlers.onLog('info', 'Ignored non-text frame');
      return;
    }
    let msg: ServerMessage;
    try {
      msg = JSON.parse(raw) as ServerMessage;
    } catch (err) {
      this.handlers.onLog('info', `Bad JSON in: ${raw.slice(0, 80)}`);
      captureException(err, { stage: 'ws_parse' });
      return;
    }
    this.handlers.onLog('in', summarize(msg));
    breadcrumb('ws', `in:${(msg as { type?: string }).type ?? 'unknown'}`);
    try {
      this.handlers.onMessage(msg);
    } catch (err) {
      captureException(err, { stage: 'ws_dispatch', type: (msg as { type?: string }).type });
    }
  }

  send(msg: ClientMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.handlers.onLog('info', `Cannot send ${msg.type}: socket not open`);
      return;
    }
    try {
      this.ws.send(JSON.stringify(msg));
      this.handlers.onLog('out', summarize(msg));
      breadcrumb('ws', `out:${msg.type}`);
    } catch (err) {
      captureException(err, { stage: 'ws_send', type: msg.type });
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.send({
        type: 'heartbeat',
        elder_id: ELDER_ID,
        ts: new Date().toISOString(),
        device_state: this.handlers.getDeviceState(),
      });
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnect();
    const delay = Math.min(
      RECONNECT_BASE_DELAY_MS * 2 ** this.reconnectAttempts,
      RECONNECT_MAX_DELAY_MS,
    );
    this.reconnectAttempts += 1;
    this.handlers.onLog('info', `Reconnecting in ${Math.round(delay / 1000)}s …`);
    this.reconnectTimer = setTimeout(() => this.openSocket(), delay);
  }

  private clearReconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  close(): void {
    this.shouldRun = false;
    this.stopHeartbeat();
    this.clearReconnect();
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // ignore
      }
      this.ws = null;
    }
  }
}

// Compact one-line summary for the debug log; never logs full audio payloads.
function summarize(msg: ClientMessage | ServerMessage): string {
  const redacted: Record<string, unknown> = { ...(msg as unknown as Record<string, unknown>) };
  for (const key of ['audio_b64', 'audio_clip_b64', 'frame_b64']) {
    if (redacted[key] != null) {
      const len = String(redacted[key]).length;
      redacted[key] = `<${len} b64 chars>`;
    }
  }
  return JSON.stringify(redacted);
}
