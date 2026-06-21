import { useCallback, useEffect, useRef, useState } from 'react';
import * as Speech from 'expo-speech';
import type { DemoState } from './types';
import { COUNTDOWN_SECONDS } from './theme';

// Speak a line with a calm, slightly slow voice. Stops any in-progress speech
// first so prompts never overlap. Fails soft where TTS is unavailable.
function say(text: string): void {
  try {
    Speech.stop();
    Speech.speak(text, { rate: 0.95, pitch: 1.0 });
  } catch {
    // no-op: TTS not available on this platform
  }
}

export interface DemoMachine {
  state: DemoState;
  countdown: number; // seconds remaining during check_in
  transcript: string; // simulated elder/voice line for the demo
  trigger: () => void; // simulate a fall -> check_in
  confirmOk: () => void; // elder taps "I'm OK"
  callForHelp: () => void; // elder taps "I need help" (immediate escalate)
  reset: () => void;
}

// A fully self-contained state machine that mirrors the real escalation flow
// (idle -> checking_in -> resolved | escalating -> escalated -> idle) so the
// design can be walked end-to-end on web with no backend.
export function useDemoMachine(): DemoMachine {
  const [state, setState] = useState<DemoState>('idle');
  const [countdown, setCountdown] = useState(COUNTDOWN_SECONDS);
  const [transcript, setTranscript] = useState('');
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const tick = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearAll = useCallback(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (tick.current) {
      clearInterval(tick.current);
      tick.current = null;
    }
  }, []);

  const later = useCallback((fn: () => void, ms: number) => {
    timers.current.push(setTimeout(fn, ms));
  }, []);

  const escalate = useCallback(() => {
    clearAll();
    setState('escalating');
    setTranscript('No clear response — reaching your caretaker.');
    say('I didn’t hear a response. I’m reaching your caretaker now. Help is on the way.');
    later(() => {
      setState('escalated');
      setTranscript('Caretaker notified. Help is on the way.');
      later(() => {
        setState('idle');
        setTranscript('');
        setCountdown(COUNTDOWN_SECONDS);
      }, 4200);
    }, 2600);
  }, [clearAll, later]);

  const trigger = useCallback(() => {
    clearAll();
    setState('checking_in');
    setTranscript('Margaret, are you okay?');
    setCountdown(COUNTDOWN_SECONDS);
    say('Margaret, are you okay? Tap I’m okay, or I need help. I’ll wait ten seconds.');
    tick.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          escalate();
          return 0;
        }
        return c - 1;
      });
    }, 1000);
  }, [clearAll, escalate]);

  const confirmOk = useCallback(() => {
    clearAll();
    setState('resolved');
    setTranscript('“I’m fine, just dropped a cup.”');
    say('Glad you’re okay. I’ve logged it, and I didn’t bother anyone.');
    later(() => {
      setState('idle');
      setTranscript('');
      setCountdown(COUNTDOWN_SECONDS);
    }, 3200);
  }, [clearAll, later]);

  const callForHelp = useCallback(() => {
    setTranscript('“I can’t get up.”');
    say('Okay. I’m calling for help right now.');
    escalate();
  }, [escalate]);

  const reset = useCallback(() => {
    clearAll();
    try {
      Speech.stop();
    } catch {
      // no-op
    }
    setState('idle');
    setTranscript('');
    setCountdown(COUNTDOWN_SECONDS);
  }, [clearAll]);

  // Stop any in-progress speech on unmount.
  useEffect(() => {
    return () => {
      clearAll();
      try {
        Speech.stop();
      } catch {
        // no-op
      }
    };
  }, [clearAll]);

  return { state, countdown, transcript, trigger, confirmOk, callForHelp, reset };
}
