import { ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { IntegrationStatusBar } from '@/components/IntegrationStatusBar';
import { SecurityScanCard } from '@/components/SecurityScanCard';

export function TrustPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">Trust &amp; integrations</h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Live provider status</CardTitle>
        </CardHeader>
        <CardContent>
          <IntegrationStatusBar />
          <p className="mt-3 text-sm text-muted-foreground">
            Green badges are wired to live sponsor services; grey badges are running on a safe mock.
          </p>
        </CardContent>
      </Card>

      <SecurityScanCard />
    </div>
  );
}
