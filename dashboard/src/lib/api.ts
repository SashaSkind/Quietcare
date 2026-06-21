import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from '@tanstack/react-query';
import type {
  AdherenceResponse,
  CallBridgeResponse,
  Confirm911Response,
  ConfirmationResponse,
  CreateElderBody,
  CreateElderResponse,
  ElderDetail,
  EventsResponse,
  HealthResponse,
  ListEldersResponse,
  MedicationItem,
  MedicationsResponse,
  RefillResponse,
  RemindResponse,
  ScanResult,
  SummaryResponse,
  WellnessResponse,
} from './types';

const API_BASE = (import.meta.env.VITE_API_BASE ?? '/api').replace(/\/$/, '');

// ---- Admin token (held in memory + localStorage for privileged writes) ------

const ADMIN_KEY = 'qc_admin_token';
export function getAdminToken(): string {
  try {
    return localStorage.getItem(ADMIN_KEY) ?? '';
  } catch {
    return '';
  }
}
export function setAdminToken(token: string): void {
  try {
    if (token) localStorage.setItem(ADMIN_KEY, token);
    else localStorage.removeItem(ADMIN_KEY);
  } catch {
    /* ignore */
  }
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  admin?: boolean;
  signal?: AbortSignal;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (opts.admin) {
    const token = getAdminToken();
    if (token) headers['X-Admin-Token'] = token;
  }
  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = (data && (data.detail || data.message)) || detail;
    } catch {
      /* non-json error */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ============================================================================
// Raw API surface
// ============================================================================

export const api = {
  health: () => request<HealthResponse>('/health'),
  listElders: () => request<ListEldersResponse>('/elders'),
  getElder: (id: string) => request<ElderDetail>(`/elders/${id}`),
  events: (id: string, kind?: string, limit = 50) =>
    request<EventsResponse>(
      `/elders/${id}/events?limit=${limit}${kind ? `&kind=${kind}` : ''}`,
    ),
  summary: (id: string, question?: string) =>
    request<SummaryResponse>(
      `/elders/${id}/summary${question ? `?question=${encodeURIComponent(question)}` : ''}`,
    ),
  wellness: (id: string, days = 7) =>
    request<WellnessResponse>(`/elders/${id}/wellness?days=${days}`),
  medications: (id: string) =>
    request<MedicationsResponse>(`/elders/${id}/medications`),
  setMedications: (id: string, medications: MedicationItem[]) =>
    request<MedicationsResponse>(`/elders/${id}/medications`, {
      method: 'PUT',
      body: { medications },
      admin: true,
    }),
  remind: (id: string, med: MedicationItem) =>
    request<RemindResponse>(`/elders/${id}/medications/remind`, {
      method: 'POST',
      body: med,
    }),
  adherence: (id: string) =>
    request<AdherenceResponse>(`/elders/${id}/adherence`),
  refill: (id: string, medication: string, pharmacy_url?: string) =>
    request<RefillResponse>(`/elders/${id}/refill`, {
      method: 'POST',
      body: { medication, pharmacy_url },
    }),
  callBridge: (id: string) =>
    request<CallBridgeResponse>(`/elders/${id}/call-bridge`, { method: 'POST' }),
  confirmation: (id: string) =>
    request<ConfirmationResponse>(`/incidents/${id}/confirmation`),
  confirm911: (id: string, token: string, approve: boolean) =>
    request<Confirm911Response>(`/incidents/${id}/confirm_911`, {
      method: 'POST',
      body: { token, approve },
    }),
  createElder: (body: CreateElderBody) =>
    request<CreateElderResponse>('/elders', {
      method: 'POST',
      body,
      admin: true,
    }),
  securityScan: (url: string) =>
    request<ScanResult>('/admin/security-scan', {
      method: 'POST',
      body: { url },
      admin: true,
    }),
};

// ============================================================================
// Query keys + polling intervals (per UI plan: overview 15s, detail 5s,
// pending confirmations 3s).
// ============================================================================

export const qk = {
  health: ['health'] as const,
  elders: ['elders'] as const,
  elder: (id: string) => ['elder', id] as const,
  events: (id: string, kind?: string) => ['events', id, kind ?? 'all'] as const,
  summary: (id: string) => ['summary', id] as const,
  wellness: (id: string, days: number) => ['wellness', id, days] as const,
  medications: (id: string) => ['medications', id] as const,
  adherence: (id: string) => ['adherence', id] as const,
  confirmation: (id: string) => ['confirmation', id] as const,
};

const POLL = { overview: 15_000, detail: 5_000, confirmation: 3_000 };

// ============================================================================
// Hooks
// ============================================================================

export function useHealth() {
  return useQuery({
    queryKey: qk.health,
    queryFn: () => api.health(),
    refetchInterval: 30_000,
  });
}

export function useElderIds() {
  return useQuery({
    queryKey: qk.elders,
    queryFn: () => api.listElders().then((r) => r.elders),
    refetchInterval: POLL.overview,
  });
}

export function useElder(id: string, opts?: Partial<UseQueryOptions<ElderDetail>>) {
  return useQuery({
    queryKey: qk.elder(id),
    queryFn: () => api.getElder(id),
    refetchInterval: POLL.overview,
    ...opts,
  });
}

export function useEvents(id: string, kind?: string, limit = 50) {
  return useQuery({
    queryKey: qk.events(id, kind),
    queryFn: () => api.events(id, kind, limit).then((r) => r.events),
    refetchInterval: POLL.detail,
  });
}

export function useSummary(id: string, question?: string) {
  return useQuery({
    queryKey: qk.summary(id),
    queryFn: () => api.summary(id, question).then((r) => r.summary),
    refetchInterval: 60_000,
  });
}

export function useWellness(id: string, days = 7) {
  return useQuery({
    queryKey: qk.wellness(id, days),
    queryFn: () => api.wellness(id, days),
    refetchInterval: 60_000,
  });
}

export function useMedications(id: string) {
  return useQuery({
    queryKey: qk.medications(id),
    queryFn: () => api.medications(id).then((r) => r.medications),
    refetchInterval: POLL.detail,
  });
}

export function useAdherence(id: string) {
  return useQuery({
    queryKey: qk.adherence(id),
    queryFn: () => api.adherence(id).then((r) => r.adherence),
    refetchInterval: POLL.detail,
  });
}

/** Polls every 3s; 404 (no pending confirmation) is treated as "none". */
export function useConfirmation(id: string) {
  return useQuery({
    queryKey: qk.confirmation(id),
    queryFn: async () => {
      try {
        return await api.confirmation(id);
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    refetchInterval: POLL.confirmation,
  });
}

export function useSetMedications(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (medications: MedicationItem[]) => api.setMedications(id, medications),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.medications(id) }),
  });
}

export function useRemind(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (med: MedicationItem) => api.remind(id, med),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.adherence(id) });
      qc.invalidateQueries({ queryKey: qk.events(id) });
    },
  });
}

export function useRefill(id: string) {
  return useMutation({
    mutationFn: (vars: { medication: string; pharmacy_url?: string }) =>
      api.refill(id, vars.medication, vars.pharmacy_url),
  });
}

export function useCallBridge(id: string) {
  return useMutation({ mutationFn: () => api.callBridge(id) });
}

export function useConfirm911(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: { token: string; approve: boolean }) =>
      api.confirm911(id, vars.token, vars.approve),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.confirmation(id) });
      qc.invalidateQueries({ queryKey: qk.events(id) });
    },
  });
}

export function useSecurityScan() {
  return useMutation({ mutationFn: (url: string) => api.securityScan(url) });
}
