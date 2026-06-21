// Shared types for the elder-facing design preview.
// These power a self-contained demo state machine (no backend) so the
// listening orb, fall check-in, and escalation can be shown end-to-end on web.

export type DemoState =
  | 'idle' // ambient listening, all good
  | 'checking_in' // a trigger fired: "are you okay?" + countdown
  | 'resolved' // elder confirmed they are fine
  | 'escalating' // reaching the caretaker
  | 'escalated'; // caretaker notified, help on the way

export type OrbMode = 'idle' | 'listening' | 'urgent' | 'calm';

export interface Theme {
  name: string;
  tagline: string;
  // Backgrounds keyed by mood.
  bg: string;
  bgUrgent: string;
  // Orb palette (outermost -> innermost glow layers).
  orbIdle: string[];
  orbListening: string[];
  orbUrgent: string[];
  // Text.
  textPrimary: string;
  textSecondary: string;
  // Actions.
  ok: string;
  okText: string;
  danger: string;
  dangerText: string;
  // Accent used for rings / progress.
  accent: string;
  // Optional web font stack.
  fontFamily: string;
}
