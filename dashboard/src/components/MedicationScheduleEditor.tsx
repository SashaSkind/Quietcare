import { useEffect, useState } from 'react';
import { Plus, Trash2, Save, Bell, Loader2, Check } from 'lucide-react';
import { useMedications, useSetMedications, useRemind, getAdminToken } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import type { MedicationItem } from '@/lib/types';

export function MedicationScheduleEditor({ id }: { id: string }) {
  const { data, isLoading } = useMedications(id);
  const save = useSetMedications(id);
  const remind = useRemind(id);
  const [rows, setRows] = useState<MedicationItem[]>([]);
  const [remindingIdx, setRemindingIdx] = useState<number | null>(null);

  useEffect(() => {
    if (data) setRows(data);
  }, [data]);

  const hasAdmin = !!getAdminToken();

  const update = (i: number, patch: Partial<MedicationItem>) =>
    setRows((r) => r.map((row, idx) => (idx === i ? { ...row, ...patch } : row)));
  const remove = (i: number) => setRows((r) => r.filter((_, idx) => idx !== i));
  const add = () => setRows((r) => [...r, { name: '', time: '09:00', dose: '' }]);

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  return (
    <div className="space-y-3">
      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground">No medications scheduled yet.</p>
      )}
      {rows.map((row, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-2">
          <Input
            className="min-w-[10rem] flex-1"
            placeholder="Medication name"
            value={row.name}
            onChange={(e) => update(i, { name: e.target.value })}
          />
          <Input
            type="time"
            className="w-32"
            value={row.time}
            onChange={(e) => update(i, { time: e.target.value })}
          />
          <Input
            className="w-28"
            placeholder="Dose"
            value={row.dose ?? ''}
            onChange={(e) => update(i, { dose: e.target.value })}
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setRemindingIdx(i);
              remind.mutate(row, { onSettled: () => setRemindingIdx(null) });
            }}
            disabled={!row.name || remind.isPending}
            title="Send this reminder to her device now"
          >
            {remindingIdx === i && remind.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Bell className="h-4 w-4" />
            )}
            Remind now
          </Button>
          <Button variant="ghost" size="icon" onClick={() => remove(i)} title="Remove">
            <Trash2 className="h-4 w-4 text-muted-foreground" />
          </Button>
        </div>
      ))}

      <div className="flex items-center justify-between pt-1">
        <Button variant="outline" size="sm" onClick={add}>
          <Plus className="h-4 w-4" /> Add medication
        </Button>
        <Button
          onClick={() => save.mutate(rows.filter((r) => r.name.trim()))}
          disabled={save.isPending}
        >
          {save.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : save.isSuccess ? (
            <Check className="h-4 w-4" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save schedule
        </Button>
      </div>

      {!hasAdmin && (
        <p className="text-xs text-muted-foreground">
          Saving requires an admin token (set it in the header). Reminders work without one.
        </p>
      )}
      {save.isError && (
        <p className="text-sm text-alert">{(save.error as Error).message}</p>
      )}
      {remind.isError && (
        <p className="text-sm text-alert">Reminder failed: {(remind.error as Error).message}</p>
      )}
      {remind.data && (
        <p className="text-sm text-muted-foreground">
          Reminder sent — logged as <strong>{remind.data.event.status}</strong>.
        </p>
      )}
    </div>
  );
}
