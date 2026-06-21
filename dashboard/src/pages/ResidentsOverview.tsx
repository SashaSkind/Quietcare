import { Link } from 'react-router-dom';
import { useQueries } from '@tanstack/react-query';
import { AlertTriangle, Users } from 'lucide-react';
import { useElderIds, api, qk } from '@/lib/api';
import { ApiError } from '@/lib/api';
import { ResidentCard } from '@/components/ResidentCard';
import { Skeleton } from '@/components/ui/skeleton';

function PendingBanner({ ids }: { ids: string[] }) {
  const results = useQueries({
    queries: ids.map((id) => ({
      queryKey: qk.confirmation(id),
      queryFn: async () => {
        try {
          return await api.confirmation(id);
        } catch (e) {
          if (e instanceof ApiError && e.status === 404) return null;
          throw e;
        }
      },
      refetchInterval: 3000,
    })),
  });
  const pending = ids.filter((_, i) => results[i].data?.status === 'pending');
  if (pending.length === 0) return null;
  return (
    <div className="mb-6 flex items-center gap-3 rounded-xl border border-alert/40 bg-alert-soft px-4 py-3 text-alert-fg">
      <AlertTriangle className="h-5 w-5 shrink-0" />
      <div className="flex-1 text-sm font-medium">
        {pending.length === 1
          ? 'A resident needs an emergency decision.'
          : `${pending.length} residents need emergency decisions.`}
      </div>
      <Link
        to={`/elders/${pending[0]}`}
        className="rounded-lg bg-alert px-3 py-1.5 text-sm font-semibold text-white hover:bg-alert/90"
      >
        Review now
      </Link>
    </div>
  );
}

export function ResidentsOverview() {
  const { data: ids, isLoading, isError } = useElderIds();

  return (
    <div>
      <div className="mb-6 flex items-center gap-2">
        <Users className="h-6 w-6 text-primary" />
        <h1 className="text-2xl font-bold">Residents</h1>
      </div>

      {ids && ids.length > 0 && <PendingBanner ids={ids} />}

      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36 w-full rounded-xl" />
          ))}
        </div>
      )}

      {isError && (
        <div className="rounded-xl border border-dashed border-border p-10 text-center">
          <p className="font-medium">Can't reach the backend.</p>
          <p className="mt-1 text-sm text-muted-foreground">
            Start the FastAPI server and set <code>VITE_API_TARGET</code> (default
            <code> http://localhost:8000</code>).
          </p>
        </div>
      )}

      {ids && ids.length === 0 && (
        <div className="rounded-xl border border-dashed border-border p-10 text-center text-muted-foreground">
          No residents yet. Add one from the backend or the setup flow.
        </div>
      )}

      {ids && ids.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ids.map((id) => (
            <ResidentCard key={id} id={id} />
          ))}
        </div>
      )}
    </div>
  );
}
