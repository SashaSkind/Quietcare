import type { Theme } from './types';

// ============================================================================
// DESIGN B — "Pulse"  (high-contrast / accessible)
// Bold, near-black canvas with a crisp concentric-ring orb, bright electric
// accents, and oversized type/targets for elder legibility (per the styling
// note: large text, simple controls, high contrast).
// ============================================================================

export const DESIGN_ID = 'pulse';

export const theme: Theme = {
  name: 'Pulse',
  tagline: 'High-contrast, accessible',
  bg: '#000000',
  bgUrgent: '#1a0000',
  // For Pulse the orb is drawn as crisp rings; these arrays still feed the core
  // gradient/glow fallback (outer -> inner).
  orbIdle: ['rgba(34,211,238,0.06)', 'rgba(34,211,238,0.16)', 'rgba(34,211,238,0.45)', '#22d3ee'],
  orbListening: ['rgba(163,230,53,0.08)', 'rgba(163,230,53,0.20)', 'rgba(163,230,53,0.55)', '#a3e635'],
  orbUrgent: ['rgba(239,68,68,0.10)', 'rgba(239,68,68,0.28)', 'rgba(239,68,68,0.6)', '#ef4444'],
  textPrimary: '#ffffff',
  textSecondary: '#a3b3bd',
  ok: '#22d3ee',
  okText: '#001b20',
  danger: '#ef4444',
  dangerText: '#ffffff',
  accent: '#22d3ee',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
};

export const COUNTDOWN_SECONDS = 10;
