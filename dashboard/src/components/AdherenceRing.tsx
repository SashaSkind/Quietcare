import type { AdherenceSummary } from '@/lib/types';

export function AdherenceRing({
  data,
  size = 132,
  stroke = 12,
}: {
  data: AdherenceSummary;
  size?: number;
  stroke?: number;
}) {
  const rate = data.adherence_rate;
  const pct = rate == null ? 0 : Math.round(rate * 100);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - (rate ?? 0));
  const color = pct >= 90 ? '#16a34a' : pct >= 70 ? '#d97706' : '#dc2626';

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e5e7eb" strokeWidth={stroke} />
        {data.total > 0 && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.6s ease' }}
          />
        )}
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-2xl font-bold tabular-nums">
          {data.total > 0 ? `${pct}%` : '—'}
        </span>
        <span className="text-xs text-muted-foreground">
          {data.total > 0 ? `${data.confirmed}/${data.total} taken` : 'no doses yet'}
        </span>
      </div>
    </div>
  );
}
