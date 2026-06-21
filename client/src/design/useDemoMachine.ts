import { useCallback, useEffect, useRef, useState } from 'react';
import type { DemoState } from './types';
import { COUNTDOWN_SECONDS } from './theme';

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
    later(() => {
      setState('idle');
      setTranscript('');
      setCountdown(COUNTDOWN_SECONDS);
    }, 3200);
  }, [clearAll, later]);

  const callForHelp = useCallback(() => {
    setTranscript('“I can’t get up.”');
    escalate();
  }, [escalate]);

  const reset = useCallback(() => {
    clearAll();
    setState('idle');
    setTranscript('');
    setCountdown(COUNTDOWN_SECONDS);
  }, [clearAll]);

  useEffect(() => clearAll, [clearAll]);

  return { state, countdown, transcript, trigger, confirmOk, callForHelp, reset };
}
