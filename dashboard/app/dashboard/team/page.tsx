"use client";
import { useEffect, useState, Suspense } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import {
  getMyOrg, createOrg, listMembers, removeMember,
  listInvites, createInvite, cancelInvite,
  OrgResponse, MemberResponse, InviteResponse,
} from "@/lib/api";
import { APP_URL } from "@/lib/config";

function TeamPageInner() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [org, setOrg] = useState<OrgResponse | null>(null);
  const [members, setMembers] = useState<MemberResponse[]>([]);
  const [invites, setInvites] = useState<InviteResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const t = Cookies.get("ag_token");
    if (!t) { router.push("/login"); return; }
    setToken(t);
    loadData(t);
  }, []);

  async function loadData(t: string) {
    setLoading(true);
    try {
      const o = await getMyOrg(t);
      setOrg(o);
      if (o) {
        const [m, i] = await Promise.all([listMembers(t), listInvites(t)]);
        setMembers(m);
        setInvites(i.filter(inv => !inv.accepted));
      }
    } catch { /* ignore */ }
    setLoading(false);
  }

  async function handleCreate() {
    if (!orgName.trim()) return;
    setCreating(true); setError("");
    try {
      const o = await createOrg(token, orgName.trim());
      setOrg(o); setOrgName("");
      await loadData(token);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
    setCreating(false);
  }

  async function handleInvite() {
    if (!inviteEmail.trim()) return;
    setInviting(true); setError("");
    try {
      await createInvite(token, inviteEmail.trim());
      setInviteEmail("");
      await loadData(token);
    } catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
    setInviting(false);
  }

  async function handleRemove(userId: string) {
    if (!confirm("Remove this member?")) return;
    try { await removeMember(token, userId); await loadData(token); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
  }

  async function handleCancelInvite(id: string) {
    try { await cancelInvite(token, id); await loadData(token); }
    catch (e: unknown) { setError(e instanceof Error ? e.message : "Error"); }
  }

  function copyReferral() {
    if (!org) return;
    const url = `${APP_URL}/signup?ref=${org.referral_code}`;
    navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) return <div className="p-8 text-ink-3">Loading…</div>;


  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-8">
      {error && <div className="text-red-500 text-sm">{error}</div>}

      {/* ── No org yet ── */}
      {!org && (
        <div className="bg-surface border border-border rounded-2xl p-6 space-y-4">
          <h1 className="text-xl font-semibold text-ink-1">Create your team</h1>
          <p className="text-sm text-ink-3">
            Members of a team share its monthly limits.
          </p>
          <div className="flex flex-wrap gap-3">
            <input
              className="flex-1 min-w-0 border border-border rounded-lg px-3 py-2 text-sm bg-background"
              placeholder="Team name"
              value={orgName}
              onChange={e => setOrgName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleCreate()}
            />
            <button
              onClick={handleCreate}
              disabled={creating || !orgName.trim()}
              className="bg-brand text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-hi disabled:opacity-50"
            >
              {creating ? "Creating…" : "Create"}
            </button>
          </div>
        </div>
      )}

      {/* ── Org exists ── */}
      {org && (
        <>
          {/* Header */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
              <div>
                <h1 className="text-xl font-semibold text-ink-1">{org.name}</h1>
                <p className="text-sm text-ink-3 mt-0.5">
                  {org.member_count}/{org.seat_limit} seats
                </p>
              </div>
            </div>

            {/* Per-product quota bars */}
            {(
              <div className="space-y-2 pt-1">
                <p className="text-xs text-ink-3">Shared quota: {org.monthly_period ?? "this month"}</p>
                {[
                  { label: "PII Vault", ...org.usage.pii_vault, unit: "tokens" },
                  { label: "EvalForge", ...org.usage.evalforge, unit: "runs" },
                  { label: "Guardrail", ...org.usage.guardrail, unit: "checks" },
                  { label: "DocParse", ...org.usage.docparse, unit: "pages" },
                ].map(({ label, used, limit, unit }) => (
                  <div key={label} className="space-y-0.5">
                    <div className="flex justify-between text-xs text-ink-3">
                      <span>{label}</span>
                      <span>{used.toLocaleString()} / {limit.toLocaleString()} {unit}</span>
                    </div>
                    <div className="h-1 bg-border rounded-full overflow-hidden">
                      <div
                        className="h-full bg-brand rounded-full transition-all"
                        style={{ width: `${limit > 0 ? Math.min(100, (used / limit) * 100) : 0}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Referral link */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-3">
            <h2 className="font-medium text-ink-1">Referral link</h2>
            <p className="text-sm text-ink-3">
              Share this link to invite colleagues to sign up.
            </p>
            <div className="flex flex-wrap gap-2">
              <code className="flex-1 min-w-0 bg-background border border-border rounded-lg px-3 py-2 text-xs text-ink-2 truncate">
                {APP_URL}/signup?ref={org.referral_code}
              </code>
              <button
                onClick={copyReferral}
                className="px-4 py-2 rounded-lg border border-border text-sm text-ink-2 hover:bg-surface transition-colors"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
            </div>
          </div>

          {/* Members */}
          <div className="bg-surface border border-border rounded-2xl p-6 space-y-4">
            <h2 className="font-medium text-ink-1">Members</h2>
            <div className="divide-y divide-border">
              {members.map(m => (
                <div key={m.user_id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm text-ink-1">{m.email}</p>
                    <p className="text-xs text-ink-4 capitalize">{m.role}</p>
                  </div>
                  {m.role !== "owner" && (
                    <button
                      onClick={() => handleRemove(m.user_id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
            </div>

            {/* Invite */}
            {org.member_count < org.seat_limit && (
              <div className="pt-2 flex flex-wrap gap-2">
                <input
                  className="flex-1 min-w-0 border border-border rounded-lg px-3 py-2 text-sm bg-background"
                  placeholder="colleague@lab.eu"
                  type="email"
                  value={inviteEmail}
                  onChange={e => setInviteEmail(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleInvite()}
                />
                <button
                  onClick={handleInvite}
                  disabled={inviting || !inviteEmail.trim()}
                  className="bg-brand text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-brand-hi disabled:opacity-50"
                >
                  {inviting ? "Sending…" : "Invite"}
                </button>
              </div>
            )}
          </div>

          {/* Pending invites */}
          {invites.length > 0 && (
            <div className="bg-surface border border-border rounded-2xl p-6 space-y-3">
              <h2 className="font-medium text-ink-1">Pending invitations</h2>
              <div className="divide-y divide-border">
                {invites.map(inv => (
                  <div key={inv.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm text-ink-1">{inv.email}</p>
                      <p className="text-xs text-ink-4">
                        Expires {new Date(inv.expires_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={() => handleCancelInvite(inv.id)}
                      className="text-xs text-ink-4 hover:text-red-500"
                    >
                      Cancel
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function TeamPage() {
  return (
    <Suspense fallback={<div className="p-8 text-ink-3">Loading…</div>}>
      <TeamPageInner />
    </Suspense>
  );
}
