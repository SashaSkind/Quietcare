import { useState } from 'react';
import { ShieldCheck, ShieldAlert, Loader2 } from 'lucide-react';
import { useSecurityScan } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const SEVERITY_STYLE: Record<string, string> = {
  safe: 'text-ok-fg bg-ok-soft',
  low: 'text-ok-fg bg-ok-soft',
  medium: 'text-warn-fg bg-warn-soft',
  high: 'text-alert-fg bg-alert-soft',
  critical: 'text-alert-fg bg-alert-soft',
};

export function SecurityScanCard() {
  const [url, setUrl] = useState('');
  const scan = useSecurityScan();
  const result = scan.data;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <ShieldCheck className="h-5 w-5 text-primary" /> MCP security posture
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Run an ArmorIQ vulnerability scan against an MCP endpoint (admin token required).
        </p>
        <div className="flex gap-2">
          <Input
            placeholder="https://mcp.example.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <Button onClick={() => url && scan.mutate(url)} disabled={!url || scan.isPending}>
            {scan.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Scan'}
          </Button>
        </div>
        {scan.isError && (
          <p className="text-sm text-alert">{(scan.error as Error).message}</p>
        )}
        {result && (
          <div className="rounded-lg border border-border p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-medium">
                {result.severity_level === 'safe' ? (
                  <ShieldCheck className="h-4 w-4 text-ok" />
                ) : (
                  <ShieldAlert className="h-4 w-4 text-alert" />
                )}
                {result.url}
              </span>
              <span
                className={
                  'rounded-full px-2.5 py-0.5 text-xs font-semibold ' +
                  (SEVERITY_STYLE[result.severity_level] ?? 'bg-muted text-muted-foreground')
                }
              >
                {result.severity_level}
              </span>
            </div>
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <div className="flex justify-between"><dt>Vulnerability score</dt><dd className="font-medium text-foreground">{result.vulnerability_score}</dd></div>
              <div className="flex justify-between"><dt>MCP endpoints</dt><dd className="font-medium text-foreground">{result.mcp_endpoints}</dd></div>
              <div className="flex justify-between"><dt>Chain attacks</dt><dd className="font-medium text-foreground">{result.chain_attacks_detected}</dd></div>
              <div className="flex justify-between"><dt>Reachable hosts</dt><dd className="font-medium text-foreground">{result.reachable_hosts}/{result.scanned_hosts}</dd></div>
            </dl>
            {result.mocked && <p className="mt-2 text-xs text-muted-foreground">simulated result (no ArmorIQ key configured)</p>}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
