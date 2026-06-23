import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { audioManager } from '../audio/audioManager';
import { cameraManager } from '../camera/cameraManager';
import { ELDER_ID, WS_URL } from '../config';
import { SAMPLE_AUDIO_B64 } from '../assets/sampleAudio';
import { COUNTDOWN_SECONDS } from '../design/theme';
import type { DemoMachine } from '../design/useDemoMachine';
import type { DemoState } from '../design/types';
import { breadcrumb, captureException } from '../sentry';
import type { AudioProbeResultMessage, DeviceState, ServerMessage, TriggerSource } from '../types';
import { WebSocketClient, type ConnectionState } from '../ws/WebSocketClient';

type AudioSceneResult = AudioProbeResultMessage['audio_scene'];

export interface ElderWebSocketState {
  machine: DemoMachine;
  connection: ConnectionState;
  voice: string;
  agentMode: string;
  scene: AudioSceneResult | null;
  sendFallTrigger: () => void;
}

function deviceState(): DeviceState {
  return { battery: 1, connectivity: 'wifi' };
}

function formatAudioScene(scene: AudioSceneResult | null): string {
  if (!scene || scene.tags.length === 0) return '';
  return scene.tags
    .slice(0, 2)
    .map((tag) => `${tag.label} ${(tag.score * 100).toFixed(0)}%`)
    .join(' · ');
}

export function useElderWebSocket(): ElderWebSocketState {
  const [connection, setConnection] = useState<ConnectionState>('closed');
  const [state, setState] = useState<DemoState>('idle');
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [transcript, setTranscript] = useState('');
  const [voice, setVoice] = useState('');
  const [agentMode, setAgentMode] = useState('Connecting backend WebSocket…');
  const [scene, setScene] = useState<AudioSceneResult | null>(null);

  const wsRef = useRef<WebSocketClient | null>(null);
  const stateRef = useRef<DemoState>('idle');
  const playbackRef = useRef<Promise<void>>(Promise.resolve());
  const activePromptIdRef = useRef<string | null>(null);
  const queuedTranscriptRef = useRef<string | null>(null);
  const answeredPromptsRef = useRef<Set<string>>(new Set());
  const probeInFlightRef = useRef(false);
  const conversingRef = useRef(false);
  const countdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const resetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  const clearCountdown = useCallback(() => {
    if (countdownTimerRef.current) {
      clearInterval(countdownTimerRef.current);
      countdownTimerRef.current = null;
    }
  }, []);

  const scheduleIdle = useCallback(() => {
    if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
    resetTimerRef.current = setTimeout(() => {
      setState('idle');
      setCountdown(COUNTDOWN_SECONDS);
      setTranscript('');
      setAgentMode('Agent asleep · say “Hey Quietcare”');
    }, 3200);
  }, []);

  const startCountdown = useCallback(
    (durationMs: number) => {
      clearCountdown();
      setCountdown(Math.max(1, Math.ceil(durationMs / 1000)));
      countdownTimerRef.current = setInterval(() => {
        setCountdown((c) => Math.max(0, c - 1));
      }, 1000);
    },
    [clearCountdown],
  );

  const sendPromptTranscript = useCallback((text: string) => {
    const promptId = activePromptIdRef.current;
    if (!promptId) {
      queuedTranscriptRef.current = text;
      setVoice(`queued: ${text}`);
      return;
    }
    answeredPromptsRef.current.add(promptId);
    activePromptIdRef.current = null;
    clearCountdown();
    setTranscript(text);
    wsRef.current?.send({
      type: 'audio_response',
      elder_id: ELDER_ID,
      ts: new Date().toISOString(),
      prompt_id: promptId,
      audio_clip_b64: null,
      transcript: text,
    });
  }, [clearCountdown]);

  const sendTrigger = useCallback(async (source: TriggerSource, note?: string) => {
    breadcrumb('ui', `ws_trigger_${source}`);
    setState('checking_in');
    setTranscript('Backend agent is checking in…');
    setAgentMode('Backend elder-agent running');
    setVoice(`ws trigger: ${source}`);
    const buffered = audioManager.getRecentAudioB64();
    const audio_clip_b64 = buffered ?? SAMPLE_AUDIO_B64;
    let frame_b64: string | null = null;
    try {
      frame_b64 = await cameraManager.captureFrameB64();
    } catch (err) {
      captureException(err, { stage: 'frame_capture', source });
    }
    wsRef.current?.send({
      type: 'trigger',
      elder_id: ELDER_ID,
      ts: new Date().toISOString(),
      trigger_source: source,
      audio_clip_b64,
      frame_b64,
      device_state: deviceState(),
      note: note ?? null,
      location: null,
    });
  }, []);

  const sendFallTrigger = useCallback(() => {
    void sendTrigger('fall');
  }, [sendTrigger]);

  const handleProbeResult = useCallback((msg: AudioProbeResultMessage) => {
    probeInFlightRef.current = false;
    setScene(msg.audio_scene);
    const heard = msg.transcript.trim();
    const sceneText = formatAudioScene(msg.audio_scene);
    if (!heard) {
      if (sceneText) setVoice(`YAMNet: ${sceneText}`);
      return;
    }
    if (stateRef.current !== 'idle') {
      setVoice(`heard: ${heard}`);
      return;
    }
    if (!msg.wants_attention) {
      setAgentMode('Agent asleep · say “Hey Quietcare”');
      setVoice(`heard: ${heard} · wake word needed`);
      return;
    }
    if (conversingRef.current) return;
    conversingRef.current = true;
    setAgentMode('Wake word heard · asking backend over WS');
    setVoice(`wake: ${heard}`);
    wsRef.current?.send({
      type: 'voice_conversation',
      elder_id: ELDER_ID,
      ts: new Date().toISOString(),
      transcript: heard,
    });
  }, []);

  const handleServerMessage = useCallback(
    (msg: ServerMessage) => {
      switch (msg.type) {
        case 'speak': {
          setState('checking_in');
          setAgentMode('Backend elder-agent speaking');
          setTranscript(msg.text || 'Quietcare is checking in…');
          const playback = audioManager.playBase64Audio(msg.audio_b64).catch((err) => {
            setVoice(`speak playback failed: ${String(err)}`);
            captureException(err, { stage: 'ws_speak' });
          });
          playbackRef.current = playback;
          break;
        }
        case 'listen': {
          setState('checking_in');
          setAgentMode('Backend listening over WebSocket');
          activePromptIdRef.current = msg.prompt_id;
          startCountdown(msg.duration_ms);
          const queued = queuedTranscriptRef.current;
          if (queued) {
            queuedTranscriptRef.current = null;
            sendPromptTranscript(queued);
            break;
          }
          playbackRef.current.finally(() => {
            audioManager
              .recordAudioBase64(msg.duration_ms)
              .then((audio_clip_b64) => {
                if (answeredPromptsRef.current.has(msg.prompt_id)) return;
                activePromptIdRef.current = null;
                clearCountdown();
                wsRef.current?.send({
                  type: 'audio_response',
                  elder_id: ELDER_ID,
                  ts: new Date().toISOString(),
                  prompt_id: msg.prompt_id,
                  audio_clip_b64,
                });
              })
              .catch((err) => {
                setVoice(`listen/record failed: ${String(err)}`);
                captureException(err, { stage: 'ws_listen', prompt_id: msg.prompt_id });
              });
          });
          break;
        }
        case 'status': {
          if (msg.state === 'checking_in') {
            setState('checking_in');
            setAgentMode('Backend incident flow active');
          } else if (msg.state === 'escalating') {
            clearCountdown();
            setState('escalating');
            setTranscript('Reaching your caretaker.');
            setAgentMode('Backend escalating to caretaker');
          } else if (msg.state === 'resolved') {
            clearCountdown();
            setState('resolved');
            setTranscript('Backend resolved the check-in.');
            setAgentMode('Check-in resolved by backend');
            scheduleIdle();
          } else {
            clearCountdown();
            setState('idle');
            setTranscript('');
            setAgentMode('Agent asleep · say “Hey Quietcare”');
          }
          break;
        }
        case 'audio_probe_result':
          handleProbeResult(msg);
          break;
        case 'voice_conversation_reply': {
          setAgentMode(msg.action === 'escalated' ? 'Escalating help request' : 'Backend agent replying');
          setVoice(`${msg.action === 'escalated' ? 'alert' : 'agent'}: ${msg.reply_text}`);
          if (msg.action === 'escalated') {
            setState('escalating');
            setTranscript(msg.reply_text);
          }
          audioManager
            .playBase64Audio(msg.audio_b64)
            .catch((err) => {
              setVoice(`reply playback failed: ${String(err)}`);
              captureException(err, { stage: 'ws_voice_reply' });
            })
            .finally(() => {
              conversingRef.current = false;
              if (msg.action !== 'escalated') setAgentMode('Agent asleep · say “Hey Quietcare”');
            });
          break;
        }
        case 'ack':
          break;
        default:
          break;
      }
    },
    [clearCountdown, handleProbeResult, scheduleIdle, sendPromptTranscript, startCountdown],
  );

  useEffect(() => {
    const ws = new WebSocketClient(WS_URL, {
      onMessage: handleServerMessage,
      onLog: () => undefined,
      onStateChange: (next) => {
        setConnection(next);
        if (next === 'open') setAgentMode('Agent asleep · say “Hey Quietcare”');
        if (next !== 'open') setAgentMode(`Backend WebSocket ${next}`);
      },
      getDeviceState: deviceState,
    });
    wsRef.current = ws;
    ws.connect();

    const unsubscribe = audioManager.onAudioSegment((audio_clip_b64) => {
      if (stateRef.current !== 'idle' || probeInFlightRef.current || conversingRef.current) return;
      probeInFlightRef.current = true;
      setTimeout(() => {
        probeInFlightRef.current = false;
      }, 8000);
      wsRef.current?.send({
        type: 'audio_probe',
        elder_id: ELDER_ID,
        ts: new Date().toISOString(),
        audio_clip_b64,
      });
    });

    audioManager
      .requestMicrophoneAccess()
      .then((granted) => {
        if (!granted) {
          setVoice('mic permission denied');
          return;
        }
        audioManager.startRollingBuffer();
        setVoice('mic on ✓ WebSocket live');
      })
      .catch((err) => setVoice(`mic err: ${String(err)}`));

    return () => {
      ws.close();
      unsubscribe();
      clearCountdown();
      if (resetTimerRef.current) clearTimeout(resetTimerRef.current);
      void audioManager.stopRollingBuffer();
    };
  }, [clearCountdown, handleServerMessage]);

  const machine = useMemo<DemoMachine>(
    () => ({
      state,
      countdown,
      transcript,
      trigger: () => void sendTrigger('fall', 'Manual Simulate Fall button.'),
      confirmOk: () => sendPromptTranscript("I'm okay."),
      callForHelp: () => sendPromptTranscript("I need help. I can't get up."),
      reset: () => {
        clearCountdown();
        setState('idle');
        setCountdown(COUNTDOWN_SECONDS);
        setTranscript('');
      },
    }),
    [clearCountdown, countdown, sendPromptTranscript, sendTrigger, state, transcript],
  );

  return { machine, connection, voice, agentMode, scene, sendFallTrigger };
}
