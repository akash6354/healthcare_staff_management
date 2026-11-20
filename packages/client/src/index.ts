/** Typed client for /api/v1. The access token lives only in memory; the refresh token is an
 *  HttpOnly cookie, renewed through /auth/refresh with a double-submit CSRF header. */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public details: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

const BASE = '/api/v1';
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const listeners = new Set<(signedIn: boolean) => void>();

export function setAccessToken(token: string | null) {
  accessToken = token;
  listeners.forEach((l) => l(Boolean(token)));
}
export function onAuthChange(fn: (signedIn: boolean) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function csrf(): string {
  const m = document.cookie.match(/(?:^|;\s*)oglos_csrf=([^;]+)/);
  return m ? decodeURIComponent(m[1]!) : '';
}

export async function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-CSRF-Token': csrf() },
      });
      if (!r.ok) {
        setAccessToken(null);
        return false;
      }
      const body = (await r.json()) as TokenOut;
      setAccessToken(body.access_token);
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  if (init.body && !(init.body instanceof FormData))
    headers.set('Content-Type', 'application/json');
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'include' });
  } catch {
    throw new ApiError(0, 'NETWORK');
  }
  if (res.status === 401 && retry && !path.startsWith('/auth/')) {
    if (await refreshSession()) return raw(path, init, false);
  }
  return res;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, init);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(res.status, err.code ?? 'GENERIC', err.details ?? {});
  }
  return body as T;
}

export const get = <T>(path: string) => api<T>(path);
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) });
export const put = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'PUT', body: JSON.stringify(body) });
export const patch = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: 'PATCH', body: JSON.stringify(body) });
export const del = <T>(path: string) => api<T>(path, { method: 'DELETE' });
export const upload = <T>(path: string, form: FormData) =>
  api<T>(path, { method: 'POST', body: form });

// ---------- types (mirror the API schemas) ----------

export type I18nMap = Record<string, string>;

export interface TokenOut {
  access_token: string;
  expires_at: number;
  mfa_pending: boolean;
  mfa_token: string | null;
  totp_required: boolean;
}

export interface Me {
  id: string;
  display_name: string;
  employee_code: string;
  preferred_language: 'en' | 'kn' | 'hi';
  hospital: { id: string; code: string; name: string };
  roles: { role: string; scope_type: string; scope_id: string | null }[];
  permissions: Record<string, string>;
  mfa_pending: boolean;
}

export interface ChecklistItem {
  key: string;
  label_i18n: I18nMap;
  required?: boolean;
  icon?: string | null;
}

export interface Task {
  id: string;
  number: number;
  desk_id: string;
  branch_id: string;
  title_i18n: I18nMap;
  instructions_i18n: I18nMap;
  checklist: ChecklistItem[];
  checklist_result: Record<string, boolean> | null;
  requires_before_photo: boolean;
  requires_after_photo: boolean;
  status: 'pending' | 'in_progress' | 'submitted' | 'approved' | 'rejected' | 'cancelled';
  sla_state: 'on_time' | 'overdue' | 'missed' | 'met' | 'late';
  escalation_level: number;
  scheduled_for: string | null;
  due_at: string;
  started_at: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  rework_count: number;
}

export interface Proof {
  id: string;
  phase: 'before' | 'after';
  server_received_at: string;
  url: string | null;
  thumb_url: string | null;
  width: number;
  height: number;
}

export interface Flag {
  id: string;
  task_id: string;
  rule: 'too_fast' | 'duplicate_photo' | 'bulk_close' | 'far_apart';
  details: Record<string, unknown>;
  status: string;
  created_at: string;
}

export interface TaskDetail extends Task {
  proofs: Proof[];
  flags: Flag[];
  desk_name: string | null;
  submitted_by_name: string | null;
}

export interface Dashboard {
  day: string;
  counts: Record<
    | 'total'
    | 'done'
    | 'awaiting_approval'
    | 'in_progress'
    | 'pending'
    | 'overdue'
    | 'missed'
    | 'late'
    | 'cancelled',
    number
  >;
  open_flags: number;
  desks: { id: string; name: string; code: string; total: number; done: number; late: number }[];
}

export interface Desk {
  id: string;
  branch_id: string;
  department_id: string | null;
  floor_id: string | null;
  name: string;
  code: string;
}

export interface Branch {
  id: string;
  name: string;
  code: string;
  address_line: string | null;
}

export interface Notice {
  id: string;
  version: number;
  body_i18n: I18nMap;
  acknowledged: boolean;
}

export interface Checkin {
  id: string;
  user_id: string;
  kind: 'check_in' | 'check_out';
  server_ts: string;
  branch_id: string | null;
  display_name?: string | null;
}

export interface StaffUser {
  id: string;
  employee_code: string;
  display_name: string;
  email: string | null;
  phone: string | null;
  department_id: string | null;
  branch_id: string | null;
  status: string;
  roles: { role: string; scope_type: string; scope_id: string | null }[];
}

export interface RosterEntry {
  id: string;
  user_id: string;
  shift_id: string;
  work_date: string;
  desk_id: string | null;
}

export interface Shift {
  id: string;
  name: string;
  starts_at: string;
  ends_at: string;
}
