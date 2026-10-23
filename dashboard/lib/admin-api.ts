import { API_URL as BASE } from "./config";

function adminHeaders(token: string) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export type QuotaProduct = "pii" | "eval" | "guardrail" | "doc";

export interface AdminStats {
  users: { total: number };
  orgs: number;
}

export type LimitKey = "pii_limit" | "eval_limit" | "guardrail_limit" | "doc_limit" | "llm_judge_limit" | "schema_slots";
export type Limits = Record<"pii_vault" | "evalforge" | "guardrail" | "docparse" | "llm_judge" | "schema_slots", { limit: number; custom: boolean }>;

export interface AdminUser {
  id: string;
  email: string;
  org_id: string | null;
  monthly_period: string | null;
  monthly_token_count: number;
  quota: Record<QuotaProduct, { used: number; limit: number; topup: number }>;
  custom_limits: boolean;
  created_at: string | null;
}

export interface AdminOrg {
  id: string;
  name: string;
  seat_limit: number;
  seats_used: number;
  limits: Limits;
  monthly_period: string | null;
  pii_tokens_mo: number;
  eval_runs_mo: number;
  guardrail_checks_mo: number;
  doc_pages_mo: number;
  created_at: string | null;
}

// ── WebAuthn auth status ───────────────────────────────────────────────────────

export async function adminAuthStatus() {
  const r = await fetch(`${BASE}/admin-auth/status`);
  if (!r.ok) throw new Error("Failed to get auth status");
  return r.json() as Promise<{ registered: boolean; count: number; labels: string[] }>;
}

export async function adminLoginBegin() {
  const r = await fetch(`${BASE}/admin-auth/login/begin`, { method: "POST" });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Login begin failed");
  return r.json() as Promise<Record<string, unknown>>;
}

export async function adminLoginComplete(credential: Record<string, unknown>) {
  const r = await fetch(`${BASE}/admin-auth/login/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(credential),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Login failed");
  return r.json() as Promise<{ session_token: string }>;
}

export async function adminRegisterBegin(adminToken: string) {
  const r = await fetch(`${BASE}/admin-auth/register/begin`, {
    method: "POST",
    headers: { "X-Admin-Token": adminToken },
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Register begin failed");
  return r.json() as Promise<Record<string, unknown>>;
}

export async function adminRegisterComplete(
  credential: Record<string, unknown>,
  adminToken: string,
  label: string,
) {
  const r = await fetch(`${BASE}/admin-auth/register/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Admin-Token": adminToken },
    body: JSON.stringify({ ...credential, label }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Register failed");
  return r.json() as Promise<{ ok: boolean; label: string }>;
}

// ── Admin operations ───────────────────────────────────────────────────────────

export async function fetchAdminStats(token: string): Promise<AdminStats> {
  const r = await fetch(`${BASE}/admin/stats`, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json();
}

export async function fetchAdminUsers(token: string): Promise<{ total: number; users: AdminUser[] }> {
  const r = await fetch(`${BASE}/admin/users`, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json();
}

// A value of null resets that limit to the default.
export async function setLimits(
  token: string,
  kind: "users" | "orgs",
  id: string,
  limits: Partial<Record<LimitKey | "seat_limit", number | null>>,
) {
  const r = await fetch(`${BASE}/admin/${kind}/${id}/limits`, {
    method: "PATCH",
    headers: adminHeaders(token),
    body: JSON.stringify(limits),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to update limits");
  return r.json();
}

export async function fetchAdminUser(token: string, userId: string): Promise<{ limits: Limits } & Record<string, unknown>> {
  const r = await fetch(`${BASE}/admin/users/${userId}`, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Failed to load user");
  return r.json();
}

export async function grantTopup(
  token: string,
  userId: string,
  product: QuotaProduct,
  units: number,
) {
  const r = await fetch(`${BASE}/admin/users/${userId}/grant-topup`, {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify({ product, units }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to grant topup");
  return r.json();
}

export async function resetUserQuota(token: string, userId: string) {
  const r = await fetch(`${BASE}/admin/users/${userId}/reset-quota`, {
    method: "POST",
    headers: adminHeaders(token),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to reset quota");
  return r.json();
}

export async function fetchAdminOrgs(token: string): Promise<{ total: number; orgs: AdminOrg[] }> {
  const r = await fetch(`${BASE}/admin/orgs`, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json();
}

// ── Metrics ───────────────────────────────────────────────────────────────────

export interface TopUser {
  id: string;
  email: string;
  total_usage: number;
}

export interface AIUsageMonth {
  month: string;
  calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  by_product: { product: string; model: string; input_tokens: number; output_tokens: number; calls: number; cost_usd: number }[];
}

export interface AdminMetrics {
  storage: { vault_entries: number; vault_bytes: number; vault_mb: number; usage_log_events: number };
  ai_usage: AIUsageMonth[];
  top_users: TopUser[];
}

export async function fetchAdminMetrics(token: string): Promise<AdminMetrics> {
  const r = await fetch(`${BASE}/admin/metrics`, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json();
}

// ── Compose ───────────────────────────────────────────────────────────────────

export async function adminCompose(token: string, to: string, subject: string, body: string) {
  const r = await fetch(`${BASE}/admin/compose`, {
    method: "POST",
    headers: adminHeaders(token),
    body: JSON.stringify({ to, subject, body }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Send failed");
  return r.json() as Promise<{ ok: boolean }>;
}

// ── Tickets ───────────────────────────────────────────────────────────────────

export interface SupportTicket {
  id: string;
  user_id: string | null;
  email: string;
  subject: string;
  message: string;
  status: "open" | "handled" | "closed";
  admin_note: string | null;
  created_at: string | null;
  handled_at: string | null;
  closed_at: string | null;
}

export async function fetchAdminTickets(
  token: string,
  status?: string,
): Promise<{ total: number; open: number; tickets: SupportTicket[] }> {
  const url = status ? `${BASE}/admin/tickets?status=${status}` : `${BASE}/admin/tickets`;
  const r = await fetch(url, { headers: adminHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json();
}

export async function updateTicket(
  token: string,
  ticketId: string,
  status: string,
  adminNote?: string,
): Promise<SupportTicket> {
  const r = await fetch(`${BASE}/admin/tickets/${ticketId}`, {
    method: "PATCH",
    headers: adminHeaders(token),
    body: JSON.stringify({ status, admin_note: adminNote }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Update failed");
  return r.json();
}

export async function deleteTicket(token: string, ticketId: string) {
  const r = await fetch(`${BASE}/admin/tickets/${ticketId}`, {
    method: "DELETE",
    headers: adminHeaders(token),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Delete failed");
  return r.json();
}
