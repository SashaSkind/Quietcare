# Quietcare Caretaker Dashboard — UI Plan

A web dashboard for family caretakers to see how their loved one is doing,
manage everyday care (medications, wellness, errands), and handle the rare
emergency. It is a thin, read-mostly layer over the existing FastAPI backend —
all real logic (safety FSM, escalation gate, voice loop) stays server-side.

## Goals

- **Reassurance first.** The default view answers "is mom okay?" in one glance.
- **Everyday value, not just emergencies.** Surface medications, wellness
  trends, and the two-way "call me" bridge so the product earns daily use.
- **Human-in-the-loop for high stakes.** 911 dispatch always requires an
  explicit, audited confirmation click.

## Tech stack

- **React + Vite + TypeScript** (SPA).
- **TailwindCSS** + **shadcn/ui** components, **Lucide** icons.
- **TanStack Query** for data fetching/caching + polling.
- **Recharts** for wellness/adherence visualizations.
- Auth: an admin token (`X-Admin-Token`) held in memory for privileged writes
  (create elder, set medications). Read endpoints are open in the demo.

## Backend endpoints consumed

All already implemented in `server/app/main.py`:

| Concern | Method + Path |
| --- | --- |
| List residents | `GET /elders` |
| Resident profile | `GET /elders/{id}` |
| Event history | `GET /elders/{id}/events?kind=&limit=` |
| Warm recap | `GET /elders/{id}/summary?question=` |
| Weekly wellness | `GET /elders/{id}/wellness?days=7` |
| Medication schedule | `GET` / `PUT /elders/{id}/medications` |
| Manual reminder | `POST /elders/{id}/medications/remind` |
| Adherence stats | `GET /elders/{id}/adherence` |
| Prescription refill | `POST /elders/{id}/refill` |
| Two-way call bridge | `POST /elders/{id}/call-bridge` |
| Pending 911 confirm | `GET /incidents/{id}/confirmation` |
| Approve/reject 911 | `POST /incidents/{id}/confirm_911` |
| Create resident | `POST /elders` (admin) |
| Live updates | `WS /ws` (status/incident stream, future) |

## Screens

### 1. Residents overview (`/`)
- Card grid from `GET /elders` + each `GET /elders/{id}`.
- Each card: name, connection/last-seen, a status pill (All good / Checking in /
  Alerting), and today's medication adherence dot.
- A red banner appears for any resident with a pending 911 confirmation.

### 2. Resident detail (`/elders/:id`)
Tabs:
- **Today** — warm recap (`/summary`), latest incident, status pill, quick
  actions: **Call me** (`/call-bridge`), **Send recap**, **Refill**.
- **Wellness** — `/wellness` summary sentence + Recharts trend (incidents,
  check-ins, activity) over a 7/30-day toggle.
- **Medications** — schedule editor (`GET`/`PUT /medications`), adherence ring
  (`/adherence`), "Remind now" button (`/medications/remind`).
- **History** — timeline from `/events`, filterable by `kind`
  (incident / medication), each entry showing trigger source, transcript, and
  the gate's risk score/level.

### 3. Emergency confirmation modal
- Polls `GET /incidents/{id}/confirmation`; when `status = pending`, shows a
  blocking modal with the reason + evidence.
- **Authorize 911** / **Reject** buttons POST to `/confirm_911` with the token.
- Clearly states that authorization is logged and gated server-side.

### 4. Setup / onboarding (admin)
- Create a resident (`POST /elders`), capture caretaker name/phone, set the
  geofence home anchor + radius, and define the medication schedule.

## Real-time strategy

- Phase 1: TanStack Query polling (overview every 15s, detail every 5s, pending
  confirmations every 3s).
- Phase 2: subscribe to a caretaker-facing `WS /ws` event stream so status and
  incident changes push instantly (server work: add a read-only caretaker
  socket that mirrors session status + bus escalation events).

## Components

- `StatusPill`, `AdherenceRing`, `WellnessChart`, `EventTimeline`,
  `MedicationScheduleEditor`, `EmergencyConfirmModal`, `QuickActionBar`,
  `ResidentCard`.

## Accessibility & tone

- Large type, high contrast, calm color system (greens for normal, amber for
  checking-in, red reserved strictly for active emergencies).
- Plain-language copy everywhere; never show raw FSM states to caretakers.

## Out of scope (v1)

- Multi-caretaker roles/permissions, billing, and historical data export.
- Editing the safety FSM or escalation policy from the UI (server-owned).

## Milestones

1. Scaffold Vite + Tailwind + shadcn; API client + types mirrored from
   `shared/protocol.md`.
2. Residents overview + resident **Today** tab (recap, status, quick actions).
3. Medications tab (schedule CRUD + adherence) and Wellness tab (chart).
4. Emergency confirmation modal with polling.
5. Setup/onboarding flow + geofence anchor.
6. WebSocket live updates (replaces polling where available).
