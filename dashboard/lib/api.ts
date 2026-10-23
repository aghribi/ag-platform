import { API_URL as BASE } from "./config";

function authHeaders(token: string) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export async function signup(email: string, password: string): Promise<{ message: string }> {
  const r = await fetch(`${BASE}/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Signup failed");
  return r.json() as Promise<{ message: string }>;
}

export async function login(email: string, password: string) {
  const r = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Login failed");
  return r.json() as Promise<{ access_token: string }>;
}

export async function verifyEmail(token: string): Promise<{ access_token: string }> {
  const r = await fetch(`${BASE}/auth/verify-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Verification failed");
  return r.json() as Promise<{ access_token: string }>;
}

export async function requestPasswordReset(email: string) {
  const r = await fetch(`${BASE}/auth/password-reset/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  });
  if (!r.ok) throw new Error("Request failed");
}

export async function confirmPasswordReset(token: string, new_password: string) {
  const r = await fetch(`${BASE}/auth/password-reset/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, new_password }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Reset failed");
}

export async function getMe(token: string) {
  const r = await fetch(`${BASE}/auth/me`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Unauthorized");
  return r.json() as Promise<{ id: string; email: string; monthly_token_count: number; monthly_period: string | null }>;
}

export async function listKeys(token: string) {
  const r = await fetch(`${BASE}/keys`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load keys");
  return r.json() as Promise<{ id: string; name: string; prefix: string; is_active: boolean; scope: string | null; expires_at: string | null; last_used_at: string | null; created_at: string }[]>;
}

export async function createKey(token: string, name: string, scope?: string | null, expires_in_days?: number | null) {
  const r = await fetch(`${BASE}/keys`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ name, scope: scope ?? null, expires_in_days: expires_in_days ?? null }),
  });
  if (!r.ok) throw new Error("Failed to create key");
  return r.json() as Promise<{ id: string; name: string; key: string; prefix: string; scope: string | null; expires_at: string | null; created_at: string }>;
}

export async function revokeKey(token: string, id: string) {
  const r = await fetch(`${BASE}/keys/${id}`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to revoke key");
}

export async function getPiiVaultStats(apiKey: string) {
  const r = await fetch(`${BASE}/v1/pii-vault/stats`, { headers: authHeaders(apiKey) });
  if (!r.ok) throw new Error("Failed to load stats");
  return r.json() as Promise<{ total_entries: number; monthly_usage: number; monthly_period: string | null; quota: number }>;
}

export async function getPiiVaultMeStats(token: string) {
  const r = await fetch(`${BASE}/v1/pii-vault/me/stats`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load stats");
  return r.json() as Promise<{ total_entries: number; monthly_usage: number; monthly_period: string | null; quota: number }>;
}

export async function getEvalStats(token: string) {
  const r = await fetch(`${BASE}/v1/eval/me/stats`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load eval stats");
  return r.json() as Promise<{ monthly_usage: number; monthly_period: string; quota: number }>;
}

export type GuardrailAuditItem = { id: string; text_preview: string; direction: string; passed: boolean; blocked_by: string | null; created_at: string };

export async function getGuardrailAuditLog(token: string, limit = 50) {
  const r = await fetch(`${BASE}/v1/guardrail/me/audit?limit=${limit}`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load audit log");
  return r.json() as Promise<GuardrailAuditItem[]>;
}

export async function getGuardrailStats(token: string) {
  const r = await fetch(`${BASE}/v1/guardrail/me/stats`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load guardrail stats");
  return r.json() as Promise<{ monthly_usage: number; monthly_period: string; quota: number }>;
}

export async function getDocStats(token: string) {
  const r = await fetch(`${BASE}/v1/doc/me/stats`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load docparse stats");
  return r.json() as Promise<{ monthly_usage: number; monthly_period: string; quota: number }>;
}

export async function getUsage(token: string) {
  const r = await fetch(`${BASE}/auth/me/usage`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load usage");
  return r.json() as Promise<{ period: string; total: number; by_product: { product: string; units: number }[] }>;
}

export async function updateSettings(token: string, quota_warn_threshold: number) {
  const r = await fetch(`${BASE}/auth/me/settings`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ quota_warn_threshold }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to update settings");
  return r.json();
}

export async function downloadUsageCsv(token: string): Promise<void> {
  const r = await fetch(`${BASE}/auth/me/usage/export`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to export usage data");
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  a.href = url;
  a.download = `ag-tools_usage_${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function changePassword(token: string, currentPassword: string, newPassword: string) {
  const r = await fetch(`${BASE}/auth/me/password`, {
    method: "PATCH",
    headers: authHeaders(token),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to change password");
  return r.json() as Promise<{ ok: boolean }>;
}

export async function deleteVaultData(token: string) {
  const r = await fetch(`${BASE}/auth/me/vault`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to delete vault data");
  return r.json() as Promise<{ ok: boolean }>;
}

export async function deleteAccount(token: string) {
  const r = await fetch(`${BASE}/auth/me`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to delete account");
  return r.json() as Promise<{ ok: boolean }>;
}

// ── Orgs ──────────────────────────────────────────────────────────────────────

export type OrgResponse = { id: string; name: string; seat_limit: number; referral_code: string; member_count: number; monthly_token_count: number; monthly_period: string | null; created_at: string; usage: Record<"pii_vault" | "evalforge" | "guardrail" | "docparse" | "llm_judge", { used: number; limit: number }>; };
export type MemberResponse = { user_id: string; email: string; role: string; joined_at: string };
export type InviteResponse = { id: string; email: string; invited_by: string; created_at: string; expires_at: string; accepted: boolean };

export async function getMyOrg(token: string) {
  const r = await fetch(`${BASE}/orgs/me`, { headers: authHeaders(token) });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error("Failed to load org");
  return r.json() as Promise<OrgResponse>;
}

export async function createOrg(token: string, name: string) {
  const r = await fetch(`${BASE}/orgs`, { method: "POST", headers: authHeaders(token), body: JSON.stringify({ name }) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to create org");
  return r.json() as Promise<OrgResponse>;
}

export async function listMembers(token: string) {
  const r = await fetch(`${BASE}/orgs/me/members`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load members");
  return r.json() as Promise<MemberResponse[]>;
}

export async function removeMember(token: string, userId: string) {
  const r = await fetch(`${BASE}/orgs/me/members/${userId}`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to remove member");
}

export async function listInvites(token: string) {
  const r = await fetch(`${BASE}/orgs/me/invites`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load invites");
  return r.json() as Promise<InviteResponse[]>;
}

export async function createInvite(token: string, email: string) {
  const r = await fetch(`${BASE}/orgs/me/invites`, { method: "POST", headers: authHeaders(token), body: JSON.stringify({ email }) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to send invite");
  return r.json() as Promise<InviteResponse>;
}

export async function cancelInvite(token: string, inviteId: string) {
  const r = await fetch(`${BASE}/orgs/me/invites/${inviteId}`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to cancel invite");
}

export async function acceptInvite(token: string, inviteToken: string) {
  const r = await fetch(`${BASE}/orgs/accept/${inviteToken}`, { method: "POST", headers: authHeaders(token) });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to accept invite");
  return r.json() as Promise<{ message: string; org_id: string }>;
}

// ── Webhooks ──────────────────────────────────────────────────────────────────

export type WebhookEndpoint = { id: string; url: string; events: string[]; secret: string | null; is_active: boolean; created_at: string };

export async function listWebhooks(token: string) {
  const r = await fetch(`${BASE}/webhooks`, { headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to load webhooks");
  return r.json() as Promise<WebhookEndpoint[]>;
}

export async function createWebhook(token: string, url: string, events: string[]) {
  const r = await fetch(`${BASE}/webhooks`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ url, events }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to create webhook");
  return r.json() as Promise<WebhookEndpoint>;
}

export async function deleteWebhook(token: string, id: string) {
  const r = await fetch(`${BASE}/webhooks/${id}`, { method: "DELETE", headers: authHeaders(token) });
  if (!r.ok) throw new Error("Failed to delete webhook");
}

export type PolicyRule = { type: "keyword" | "regex"; pattern: string; action: "block" | "flag"; message?: string };
export type Policy = { id: string; name: string; rules: PolicyRule[]; is_active: boolean; created_at: string };

export async function listPolicies(apiKey: string) {
  const r = await fetch(`${BASE}/v1/guardrail/policies`, { headers: authHeaders(apiKey) });
  if (!r.ok) throw new Error("Failed to load policies");
  return r.json() as Promise<Policy[]>;
}

export async function createPolicy(apiKey: string, name: string, rules: PolicyRule[]) {
  const r = await fetch(`${BASE}/v1/guardrail/policies`, {
    method: "POST",
    headers: authHeaders(apiKey),
    body: JSON.stringify({ name, rules }),
  });
  if (!r.ok) throw new Error((await r.json()).detail ?? "Failed to create policy");
  return r.json() as Promise<Policy>;
}

export async function deletePolicy(apiKey: string, id: string) {
  const r = await fetch(`${BASE}/v1/guardrail/policies/${id}`, { method: "DELETE", headers: authHeaders(apiKey) });
  if (!r.ok) throw new Error("Failed to delete policy");
}
