import { Link } from 'react-router-dom';
import { ChevronRight, Pill } from 'lucide-react';
import { useElder, useEvents, useConfirmation } from '@/lib/api';
import { careStatus, lastSeen } from '@/lib/status';
import { timeAgo } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { StatusPill } from './StatusPill';
import { Skeleton } from '@/components/ui/skeleton';
import type { MedicationEvent } from '@/lib/types';

export function ResidentCard({ id }: { id: string }) {
  const elder = useElder(id);
  const { data: events } = useEvents(id);
  const { data: confirmation } = useConfirmation(id);

  const hasPending = confirmation?.status === 'pending';
  const status = careStatus(events, !!hasPending);
  const name = elder.data?.profile?.name ?? id;

  const lastMed = events
    ?.filter((e): e is MedicationEvent => (e as MedicationEvent).kind === 'medication')
    .at(-1);

  return (
    <Link to={`/elders/${id}`}>
      <Card className="group relative overflow-hidden p-5 transition-shadow hover:shadow-md">
        {hasPending && <div className="absolute inset-x-0 top-0 h-1 bg-alert" />}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-lg font-bold text-primary">
              {name.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <h3 className="text-lg font-semibold leading-tight">{name}</h3>
              {elder.isLoading ? (
                <Skeleton className="mt-1 h-4 w-24" />
              ) : (
                <p className="text-sm text-muted-foreground">
                  last activity {timeAgo(lastSeen(events))}
                </p>
              )}
            </div>
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </div>
        <div className="mt-4 flex items-center justify-between">
          <StatusPill status={status} />
          {lastMed && (
            <span
              className={
                'inline-flex items-center gap-1 text-sm ' +
                (lastMed.status === 'confirmed' ? 'text-ok-fg' : 'text-warn-fg')
              }
            >
              <Pill className="h-4 w-4" />
              {lastMed.status === 'confirmed' ? 'meds on track' : 'missed a dose'}
            </span>
          )}
        </div>
      </Card>
    </Link>
  );
}
