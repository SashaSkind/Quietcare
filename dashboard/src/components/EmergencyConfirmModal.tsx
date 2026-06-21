import { useState } from 'react';
import { Siren, ShieldX, PhoneCall, Loader2 } from 'lucide-react';
import { useConfirm911 } from '@/lib/api';
import { Dialog } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/**
 * Blocking, human-in-the-loop 911 confirmation. Authorization is gated
 * server-side by a one-time token (delivered out-of-band to the caretaker),
 * so we collect it here before allowing dispatch.
 */
export function EmergencyConfirmModal({
  elderId,
  elderName,
  reason,
  onResolved,
}: {
  elderId: string;
  elderName: string;
  reason?: string;
  onResolved?: () => void;
}) {
  const confirm = useConfirm911(elderId);
  const [token, setToken] = useState('');

  const act = (approve: boolean) =>
    confirm.mutate({ token, approve }, { onSuccess: () => onResolved?.() });

  return (
    <Dialog open dismissable={false} className="max-w-md border-alert/40">
      <div className="flex flex-col items-center text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-alert-soft">
          <Siren className="h-7 w-7 text-alert" />
        </div>
        <h2 className="mt-3 text-xl font-bold text-alert-fg">Emergency dispatch pending</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Quietcare wants to call 911 for <strong>{elderName}</strong>.
        </p>
      </div>

      <div className="mt-4 rounded-lg border border-alert/30 bg-alert-soft/50 p-3 text-sm text-alert-fg">
        {reason || 'A possible emergency was detected and could not be resolved with the resident.'}
      </div>

      <div className="mt-4 space-y-2">
        <label className="text-sm font-medium">Authorization token</label>
        <Input
          placeholder="Paste the one-time confirmation token"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Authorization is logged and gated server-side. Dispatch only proceeds with a valid token.
        </p>
      </div>

      {confirm.isError && (
        <p className="mt-2 text-sm text-alert">{(confirm.error as Error).message}</p>
      )}

      <div className="mt-5 flex gap-3">
        <Button
          variant="outline"
          className="flex-1"
          onClick={() => act(false)}
          disabled={!token || confirm.isPending}
        >
          <ShieldX className="h-4 w-4" /> Reject
        </Button>
        <Button
          variant="alert"
          className="flex-1"
          onClick={() => act(true)}
          disabled={!token || confirm.isPending}
        >
          {confirm.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />}
          Authorize 911
        </Button>
      </div>
    </Dialog>
  );
}
