import type { Theme } from './types';

// ============================================================================
// DESIGN C — "Halo"  (premium / ambient)
// Glassy deep-violet canvas with a circular audio-reactive waveform orb and
// refined motion. Feels like a calm, high-end ambient companion.
// ============================================================================

export const DESIGN_ID = 'halo';

export const theme: Theme = {
  name: 'Halo',
  tagline: 'Premium, ambient',
  bg: '#0c0a1f',
  bgUrgent: '#1e0a18',
  orbIdle: ['rgba(167,139,250,0.06)', 'rgba(167,139,250,0.16)', 'rgba(192,132,252,0.4)', '#c4b5fd'],
  orbListening: ['rgba(129,140,248,0.08)', 'rgba(129,140,248,0.22)', 'rgba(165,180,252,0.5)', '#a5b4fc'],
  orbUrgent: ['rgba(251,113,133,0.10)', 'rgba(251,113,133,0.28)', 'rgba(253,164,175,0.55)', '#fb7185'],
  textPrimary: '#f5f3ff',
  textSecondary: '#a5a3c4',
  ok: '#34d399',
  okText: '#022c22',
  danger: '#fb7185',
  dangerText: '#2a0a14',
  accent: '#c084fc',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
};

export const COUNTDOWN_SECONDS = 10;
