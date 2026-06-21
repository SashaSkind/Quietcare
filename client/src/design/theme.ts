import type { Theme } from './types';

// ============================================================================
// DESIGN A — "Aurora"  (calm / medical-trust)
// Soft gradient orb, slow breathing, muted teal + deep navy, large legible type.
// Swapped per branch: design-b-pulse and design-c-halo override this file.
// ============================================================================

export const DESIGN_ID = 'aurora';

export const theme: Theme = {
  name: 'Aurora',
  tagline: 'Calm, clinical trust',
  bg: '#0b1f2a',
  bgUrgent: '#2a0f14',
  orbIdle: ['rgba(45,212,191,0.10)', 'rgba(45,212,191,0.18)', 'rgba(94,234,212,0.30)', 'rgba(153,246,228,0.95)'],
  orbListening: ['rgba(56,189,248,0.12)', 'rgba(56,189,248,0.22)', 'rgba(125,211,252,0.38)', 'rgba(186,230,253,0.98)'],
  orbUrgent: ['rgba(248,113,113,0.12)', 'rgba(248,113,113,0.24)', 'rgba(252,165,165,0.42)', 'rgba(254,202,202,0.98)'],
  textPrimary: '#f0fdfa',
  textSecondary: '#7dd3c4',
  ok: '#2dd4bf',
  okText: '#04201b',
  danger: '#f87171',
  dangerText: '#2a0f14',
  accent: '#5eead4',
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "SF Pro Display", "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
};

export const COUNTDOWN_SECONDS = 10;
