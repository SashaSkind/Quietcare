import { useHealth } from '@/lib/api';
import { humanize } from '@/lib/utils';
import { CheckCircle2, CircleDashed, Wifi } from 'lucide-react';

const LABELS: Record<string, string> = {
  llm: 'LLM',
  audio_scene: 'Audio scene',
  policy_gate: 'Policy gate',
  security_scan: 'Security scan',
};
const label = (key: string) => LABELS[key] ?? humanize(key);

/** Small badge row proving which sponsor providers are wired live vs mock. */
export function IntegrationStatusBar() {
  const { data, isError } = useHealth();
  const providers = data?.providers ?? {};
  const entries = Object.entries(providers);

  if (isError) {
    return (
      <div className="text-sm text-muted-foreground">
        Backend not reachable — set <code>VITE_API_TARGET</code>.
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="mr-1 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Wifi className="h-4 w-4" /> Integrations
      </span>
      {entries.length === 0 && <span className="text-sm text-muted-foreground">loading…</span>}
      {entries.map(([key, name]) => {
        const live = !/mock/i.test(name);
        return (
          <span
            key={key}
            title={`${label(key)}: ${name}`}
            className={
              'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ' +
              (live
                ? 'border-ok/30 bg-ok-soft text-ok-fg'
                : 'border-border bg-muted text-muted-foreground')
            }
          >
            {live ? <CheckCircle2 className="h-3 w-3" /> : <CircleDashed className="h-3 w-3" />}
            {label(key)}
          </span>
        );
      })}
    </div>
  );
}
