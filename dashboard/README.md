# Quietcare — Caretaker Dashboard

A calm, read-mostly web dashboard for family caretakers. It answers "is mom
okay?" at a glance, surfaces everyday care (medications, wellness, the two-way
"call me" bridge), and handles the rare emergency with an explicit,
human-in-the-loop 911 confirmation. It is a thin layer over the existing
FastAPI backend — all real logic (safety FSM, escalation gate, voice loop)
stays server-side.

## Stack

- **React + Vite + TypeScript** (SPA)
- **TailwindCSS** with a calm status palette (green normal · amber checking-in · red emergency)
- **TanStack Query** for fetching/caching + polling
- **Recharts** for wellness visualization
- **Lucide** icons
- Lightweight in-house UI primitives (`src/components/ui/*`) in the shadcn style

## Run it

```bash
# 1) Start the backend (from repo root) — runs fully on mocks with no keys:
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000

# 2) Start the dashboard:
cd dashboard
npm install
npm run dev            # http://localhost:5273
```

In dev, requests to `/api/*` are proxied to the backend (default
`http://localhost:8000`, override with `VITE_API_TARGET`). See `.env.example`.

## Configuration

- `VITE_API_BASE` — API base path/origin (default `/api`, which uses the dev proxy).
- `VITE_API_TARGET` — where the dev proxy forwards `/api` (default `http://localhost:8000`).
- **Admin token** — set in the header ("Admin" button). Held in this browser only
  and sent as `X-Admin-Token` for privileged writes (create resident, edit
  medication schedule, security scan).

## Screens

- **Residents (`/`)** — card grid with status pill, last activity, and a med dot.
  A red banner appears for any resident with a pending 911 confirmation.
- **Resident detail (`/elders/:id`)** — tabs:
  - **Today** — warm recap (`/summary`), latest check-in, quick actions
    (**Call me** → `/call-bridge`, **Refresh recap**, **Refill** → `/refill`,
    which reveals a Browserbase "Watch the agent" replay link).
  - **Wellness** — `/wellness` summary + 7/30-day trend chart + metric tiles.
  - **Medications** — schedule editor (`GET`/`PUT /medications`, admin),
    "Remind now" (`/medications/remind`), and an adherence ring (`/adherence`).
  - **History** — timeline from `/events`, filterable by incident / medication.
- **Trust (`/trust`)** — live provider status (`/health`, real vs mock) and an
  ArmorIQ MCP security scan (`/admin/security-scan`, admin).

## Real-time

Phase 1 (implemented): TanStack Query polling — overview 15s, detail 5s,
pending confirmations 3s. Phase 2 (future): subscribe to a caretaker-facing
`WS /ws` stream to push status/incident changes instantly.

## Safety

911 dispatch is gated server-side by a one-time confirmation token. The
emergency modal collects that token and POSTs to `/incidents/{id}/confirm_911`;
authorization is logged and never client-only.

## Out of scope (v1)

Multi-caretaker roles/permissions, billing, data export, and editing the safety
FSM / escalation policy from the UI (server-owned). The setup/onboarding
(create resident + geofence anchor) and WebSocket live updates are planned next.
