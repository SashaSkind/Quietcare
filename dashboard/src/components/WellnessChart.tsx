import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { humanize } from '@/lib/utils';
import type { WellnessTrends } from '@/lib/types';

const SOURCE_COLOR: Record<string, string> = {
  fall: '#dc2626',
  audio_event: '#ea580c',
  inactivity: '#d97706',
  geofence: '#7c3aed',
  scheduled: '#0284c7',
  manual: '#0891b2',
  unknown: '#94a3b8',
};

export function WellnessChart({ trends }: { trends: WellnessTrends }) {
  const data = Object.entries(trends.by_trigger_source).map(([source, count]) => ({
    source,
    label: humanize(source),
    count,
  }));

  if (data.length === 0) {
    return (
      <div className="flex h-56 flex-col items-center justify-center rounded-xl border border-dashed border-border text-center text-muted-foreground">
        <p className="text-base font-medium text-foreground">A quiet week — that's a good thing.</p>
        <p className="text-sm">No incidents or check-ins recorded in this window.</p>
      </div>
    );
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eef2f7" />
          <XAxis dataKey="label" tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
          <Tooltip
            cursor={{ fill: '#f1f5f9' }}
            contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0', fontSize: 13 }}
          />
          <Bar dataKey="count" radius={[6, 6, 0, 0]} name="Events">
            {data.map((d) => (
              <Cell key={d.source} fill={SOURCE_COLOR[d.source] ?? '#0284c7'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
