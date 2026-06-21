import { cn } from '@/lib/utils';
import { STATUS_LABEL } from '@/lib/status';
import type { CareStatus } from '@/lib/types';

const styles: Record<CareStatus, string> = {
  ok: 'bg-ok-soft text-ok-fg',
  checking_in: 'bg-warn-soft text-warn-fg',
  alerting: 'bg-alert-soft text-alert-fg',
};

const dot: Record<CareStatus, string> = {
  ok: 'bg-ok',
  checking_in: 'bg-warn',
  alerting: 'bg-alert',
};

export function StatusPill({ status, className }: { status: CareStatus; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-semibold',
        styles[status],
        className,
      )}
    >
      <span className="relative flex h-2.5 w-2.5">
        {status === 'alerting' && (
          <span className={cn('absolute inline-flex h-full w-full rounded-full opacity-75 animate-pulse-ring', dot[status])} />
        )}
        <span className={cn('relative inline-flex h-2.5 w-2.5 rounded-full', dot[status])} />
      </span>
      {STATUS_LABEL[status]}
    </span>
  );
}
