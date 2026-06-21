import { useState } from 'react';
import { PhoneCall, RefreshCw, ShoppingCart, Loader2, Check } from 'lucide-react';
import { useCallBridge, useRefill } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import { qk } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { AgentReplayLink } from './AgentReplayLink';

export function QuickActionBar({ id }: { id: string }) {
  const qc = useQueryClient();
  const callBridge = useCallBridge(id);
  const refill = useRefill(id);
  const [medName, setMedName] = useState('');
  const [showRefill, setShowRefill] = useState(false);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button variant="default" onClick={() => callBridge.mutate()} disabled={callBridge.isPending}>
          {callBridge.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />}
          Call me
        </Button>
        <Button
          variant="outline"
          onClick={() => qc.invalidateQueries({ queryKey: qk.summary(id) })}
        >
          <RefreshCw className="h-4 w-4" /> Refresh recap
        </Button>
        <Button variant="outline" onClick={() => setShowRefill((s) => !s)}>
          <ShoppingCart className="h-4 w-4" /> Refill a prescription
        </Button>
      </div>

      {callBridge.data && (
        <p className="text-sm text-muted-foreground">
          {callBridge.data.prompted
            ? 'Asked her device to call you — it should ring shortly.'
            : "Her device isn't connected right now; we'll prompt as soon as it is."}
        </p>
      )}

      {showRefill && (
        <div className="flex gap-2">
          <Input
            placeholder="Medication to refill (e.g. Lisinopril)"
            value={medName}
            onChange={(e) => setMedName(e.target.value)}
          />
          <Button
            onClick={() => medName && refill.mutate({ medication: medName })}
            disabled={!medName || refill.isPending}
          >
            {refill.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Start
          </Button>
        </div>
      )}

      {refill.data && <AgentReplayLink task={refill.data.task} />}
    </div>
  );
}
