import { useState } from 'react';
import { KeyRound, Check } from 'lucide-react';
import { getAdminToken, setAdminToken } from '@/lib/api';
import { Dialog } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

/** Lets a caretaker hold the admin token in memory for privileged writes. */
export function AdminTokenButton() {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(getAdminToken());
  const isSet = !!getAdminToken();

  return (
    <>
      <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
        <KeyRound className="h-4 w-4" />
        {isSet ? 'Admin: on' : 'Admin'}
        {isSet && <Check className="h-3.5 w-3.5 text-ok" />}
      </Button>
      <Dialog open={open} onClose={() => setOpen(false)} className="max-w-sm">
        <h2 className="text-lg font-semibold">Admin token</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Required for privileged writes (create resident, edit medication schedule, security scan).
          Held in this browser only.
        </p>
        <Input
          className="mt-3"
          type="password"
          placeholder="X-Admin-Token"
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => { setAdminToken(''); setValue(''); setOpen(false); }}>
            Clear
          </Button>
          <Button onClick={() => { setAdminToken(value); setOpen(false); }}>Save</Button>
        </div>
      </Dialog>
    </>
  );
}
