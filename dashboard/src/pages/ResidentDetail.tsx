import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, HeartPulse, Quote } from 'lucide-react';
import {
  useElder,
  useEvents,
  useSummary,
  useWellness,
  useAdherence,
  useConfirmation,
} from '@/lib/api';
import { careStatus, latestIncident } from '@/lib/status';
import { formatTime } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { StatusPill } from '@/components/StatusPill';
import { QuickActionBar } from '@/components/QuickActionBar';
import { WellnessChart } from '@/components/WellnessChart';
import { MedicationScheduleEditor } from '@/components/MedicationScheduleEditor';
import { AdherenceRing } from '@/components/AdherenceRing';
import { EventTimeline } from '@/components/EventTimeline';
import { EmergencyConfirmModal } from '@/components/EmergencyConfirmModal';

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-border p-3 text-center">
      <div className="text-2xl font-bold tabular-nums">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

export function ResidentDetail() {
  const { id = '' } = useParams();
  const elder = useElder(id);
  const { data: events } = useEvents(id);
  const summary = useSummary(id);
  const { data: confirmation } = useConfirmation(id);
  const [days, setDays] = useState<7 | 30>(7);
  const wellness = useWellness(id, days);
  const adherence = useAdherence(id);
  const [historyKind, setHistoryKind] = useState<'all' | 'incident' | 'medication'>('all');

  const name = elder.data?.profile?.name ?? id;
  const hasPending = confirmation?.status === 'pending';
  const status = careStatus(events, !!hasPending);
  const incident = latestIncident(events);

  const filteredEvents = (events ?? []).filter((e) =>
    historyKind === 'all' ? true : (e as { kind?: string }).kind === historyKind,
  );

  return (
    <div>
      <Link to="/" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All residents
      </Link>

      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-xl font-bold text-primary">
            {name.slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h1 className="text-2xl font-bold leading-tight">{name}</h1>
            <p className="text-sm text-muted-foreground">
              {elder.data?.profile?.age ? `${elder.data.profile.age} · ` : ''}
              {(elder.data?.profile?.conditions ?? []).join(', ') || 'no conditions on file'}
            </p>
          </div>
        </div>
        <StatusPill status={status} />
      </div>

      <Tabs defaultValue="today">
        <TabsList>
          <TabsTrigger value="today">Today</TabsTrigger>
          <TabsTrigger value="wellness">Wellness</TabsTrigger>
          <TabsTrigger value="medications">Medications</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        {/* TODAY */}
        <TabsContent value="today">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Quote className="h-4 w-4 text-primary" /> How {name.split(' ')[0]} is doing
                </CardTitle>
              </CardHeader>
              <CardContent>
                {summary.isLoading ? (
                  <Skeleton className="h-16 w-full" />
                ) : (
                  <p className="text-lg leading-relaxed">{summary.data || 'No update available yet.'}</p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Latest check-in</CardTitle>
              </CardHeader>
              <CardContent>
                {incident ? (
                  <div className="space-y-1 text-sm">
                    <p className="font-medium">
                      {incident.escalated ? 'Escalated to caretaker' : 'Resolved calmly'}
                    </p>
                    {incident.last_transcript && (
                      <p className="italic text-muted-foreground">“{incident.last_transcript}”</p>
                    )}
                    <p className="text-xs text-muted-foreground">{formatTime(incident.ts)}</p>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No check-ins recorded — all quiet.</p>
                )}
              </CardContent>
            </Card>
          </div>

          <Card className="mt-4">
            <CardHeader>
              <CardTitle className="text-base">Quick actions</CardTitle>
            </CardHeader>
            <CardContent>
              <QuickActionBar id={id} />
            </CardContent>
          </Card>
        </TabsContent>

        {/* WELLNESS */}
        <TabsContent value="wellness">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base">
                <HeartPulse className="h-4 w-4 text-primary" /> Wellness trend
              </CardTitle>
              <div className="flex gap-1">
                {([7, 30] as const).map((d) => (
                  <Button
                    key={d}
                    size="sm"
                    variant={days === d ? 'default' : 'outline'}
                    onClick={() => setDays(d)}
                  >
                    {d}d
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {wellness.isLoading || !wellness.data ? (
                <Skeleton className="h-56 w-full" />
              ) : (
                <>
                  <p className="text-base leading-relaxed">{wellness.data.summary}</p>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <Metric label="check-ins" value={wellness.data.trends.check_ins} />
                    <Metric label="incidents" value={wellness.data.trends.incidents} />
                    <Metric label="escalations" value={wellness.data.trends.escalations} />
                    <Metric label="wandering" value={wellness.data.trends.wandering_alerts} />
                  </div>
                  <WellnessChart trends={wellness.data.trends} />
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* MEDICATIONS */}
        <TabsContent value="medications">
          <div className="grid gap-4 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="text-base">Schedule</CardTitle>
              </CardHeader>
              <CardContent>
                <MedicationScheduleEditor id={id} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Adherence</CardTitle>
              </CardHeader>
              <CardContent className="flex justify-center">
                {adherence.data ? (
                  <AdherenceRing data={adherence.data} />
                ) : (
                  <Skeleton className="h-32 w-32 rounded-full" />
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* HISTORY */}
        <TabsContent value="history">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle className="text-base">History</CardTitle>
              <div className="flex gap-1">
                {(['all', 'incident', 'medication'] as const).map((k) => (
                  <Button
                    key={k}
                    size="sm"
                    variant={historyKind === k ? 'default' : 'outline'}
                    onClick={() => setHistoryKind(k)}
                  >
                    {k === 'all' ? 'All' : k === 'incident' ? 'Incidents' : 'Medications'}
                  </Button>
                ))}
              </div>
            </CardHeader>
            <CardContent>
              <EventTimeline events={filteredEvents} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {hasPending && (
        <EmergencyConfirmModal
          elderId={id}
          elderName={name}
          reason={confirmation?.reason}
        />
      )}
    </div>
  );
}
