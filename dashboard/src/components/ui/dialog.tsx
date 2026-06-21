import * as React from 'react';
import { cn } from '@/lib/utils';

export function Dialog({
  open,
  onClose,
  children,
  dismissable = true,
  className,
}: {
  open: boolean;
  onClose?: () => void;
  children: React.ReactNode;
  dismissable?: boolean;
  className?: string;
}) {
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && dismissable) onClose?.();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, dismissable, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => dismissable && onClose?.()}
      />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          'relative z-10 w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-xl',
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}
