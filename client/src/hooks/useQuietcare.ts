import { useCallback, useEffect, useRef, useState } from 'react';
import { WS_URL, ELDER_ID } from '../config';
import { WebSocketClient } from '../ws/WebSocketClient';
import type { ConnectionState } from '../ws/WebSocketClient';
import { AccelerometerMonitor } from '../sensors/accelerometer';
import { playBase64Audio, recordAudioBase64 } from '../audio/audioManager';
import { SAMPLE_AUDIO_B64 } from '../assets/sampleAudio';
import { breadcrumb, captureException } from '../sentry';
import type {
  AppStatus,
  DeviceState,
  ServerMessage,
  TriggerSource,
} from '../types';

export interface LogEntry {
  id: number;
  ts: string;
  direction: 'in' | 'out' | 'info';
  text: string;
}

const MAX_LOGS = 200;

export interface QuietcareState {
  status: AppStatus;
  connection: ConnectionState;
  accelMagnitude: number;
  logs: LogEntry[];
  simulateFall: () => void;
}

function deviceState(): DeviceState {
  return { battery: 1, connectivity: 'wifi' };
}

export function useQuietcare(): QuietcareState {
  const [status, setStatus] = useState<AppStatus>('all_good');
  const [connection, setConnection] = useState<ConnectionState>('closed');
  const [accelMagnitude, setAccelMagnitude] = useState(0);
  const [logs, setLogs] = useState<LogEntry[]>([]);

  const wsRef = useRef<WebSocketClient | null>(null);
  const accelRef = useRef<AccelerometerMonitor | null>(null);
  const logIdRef = useRef(0);
  // Throttle accelerometer log lines so the debug view stays readable.
  const lastAccelLogRef = useRef(0);

  const addLog = useCallback(
    (direction: LogEntry['direction'], text: string) => {
      logIdRef.current += 1;
      const entry: LogEntry = {
        id: logIdRef.current,
        ts: new Date().toLocaleTimeString(),
        direction,
        text,
      };
      setLogs((prev) => {
        const next = [...prev, entry];
        return next.length > MAX_LOGS ? next.slice(next.length - MAX_LOGS) : next;
      });
    },
    [],
  );

  const handleServerMessage = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case 'speak': {
          setStatus('checking_in');
          playBase64Audio(msg.audio_b64).catch((err) => {
            addLog('info', `speak playback failed: ${String(err)}`);
            captureException(err, { stage: 'speak' });
          });
          break;
        }
        case 'listen': {
          setStatus('checking_in');
          recordAudioBase64(msg.duration_ms)
            .then((audio_clip_b64) => {
              wsRef.current?.send({
                type: 'audio_response',
                elder_id: ELDER_ID,
                ts: new Date().toISOString(),
                prompt_id: msg.prompt_id,
                audio_clip_b64,
              });
            })
            .catch((err) => {
              addLog('info', `listen/record failed: ${String(err)}`);
              captureException(err, { stage: 'listen', prompt_id: msg.prompt_id });
            });
          break;
        }
        case 'status': {
          if (msg.state === 'escalating') setStatus('alerting');
          else if (msg.state === 'checking_in') setStatus('checking_in');
          else setStatus('all_good');
          break;
        }
        case 'ack':
          break;
        default:
          break;
      }
    },
    [addLog],
  );

  const sendTrigger = useCallback(
    (source: TriggerSource) => {
      setStatus('checking_in');
      try {
        wsRef.current?.send({
          type: 'trigger',
          elder_id: ELDER_ID,
          ts: new Date().toISOString(),
          trigger_source: source,
          audio_clip_b64: SAMPLE_AUDIO_B64,
          frame_b64: null,
          device_state: deviceState(),
        });
      } catch (err) {
        captureException(err, { stage: 'trigger', source });
      }
    },
    [],
  );

  const simulateFall = useCallback(() => {
    breadcrumb('ui', 'simulate_fall_pressed');
    addLog('info', 'Simulate Fall pressed (bypasses detectFall stub)');
    sendTrigger('manual');
  }, [addLog, sendTrigger]);

  useEffect(() => {
    const ws = new WebSocketClient(WS_URL, {
      onMessage: handleServerMessage,
      onLog: addLog,
      onStateChange: setConnection,
      getDeviceState: deviceState,
    });
    wsRef.current = ws;
    ws.connect();

    const accel = new AccelerometerMonitor({
      onSample: (sample) => {
        setAccelMagnitude(sample.magnitude);
        const now = Date.now();
        if (now - lastAccelLogRef.current > 1000) {
          lastAccelLogRef.current = now;
          addLog('info', `accel |a| = ${sample.magnitude.toFixed(3)} g`);
        }
      },
      onFallDetected: () => {
        addLog('info', 'detectFall() returned true');
        sendTrigger('fall');
      },
    });
    accelRef.current = accel;
    accel.start();

    return () => {
      ws.close();
      accel.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { status, connection, accelMagnitude, logs, simulateFall };
}
