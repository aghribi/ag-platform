"use client";
import React, { useCallback, useEffect, useState } from "react";
import Cookies from "js-cookie";
import {
  fetchAdminUser,
  fetchAdminUsers,
  grantTopup,
  resetUserQuota,
  type AdminUser,
  type Limits,
  type QuotaProduct,
} from "@/lib/admin-api";
import LimitsEditor from "@/app/components/LimitsEditor";

function QuotaBar({ used, limit, topup }: { used: number; limit: number; topup: number }) {
  const pct = limit > 0 ? Math.min((used / limit) * 100, 100) : 0;
  const color = pct >= 95 ? "bg-red-500" : pct >= 80 ? "bg-amber-500" : "bg-brand";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 h-1.5 bg-inset rounded-full overflow-hidden">
        <div className={`${color} h-full rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-ink-4 whitespace-nowrap">{pct.toFixed(0)}%{topup > 0 ? ` +${topup}` : ""}</span>
    </div>
  );
}

function UserRow({
  user,
  token,
  onAction,
}: {
  user: AdminUser;
  token: string;
  onAction: (userId: string, action: string, extra?: unknown) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [limits, setLimitsState] = useState<Limits | null>(null);

  function loadLimits() {
    fetchAdminUser(token, user.id).then(u => setLimitsState(u.limits)).catch(() => {});
  }

  useEffect(() => { if (expanded) loadLimits(); }, [expanded]);

  async function doAction(action: string, extra?: unknown) {
    setBusy(true);
    try {
      await onAction(user.id, action, extra);
    } finally {
      setBusy(false);
    }
  }

  const products: QuotaProduct[] = ["pii", "eval", "guardrail", "doc"];
  const productLabels: Record<QuotaProduct, string> = {
    pii: "PII", eval: "Eval", guardrail: "Guard", doc: "Doc",
  };
  const topupUnits: Record<QuotaProduct, number> = {
    pii: 100_000, eval: 10_000, guardrail: 50_000, doc: 2_500,
  };

  return (
    <>
      <tr
        className="hover:bg-inset/50 cursor-pointer border-b border-edge"
        onClick={() => setExpanded(e => !e)}
      >
        <td className="px-4 py-3 text-sm font-medium text-ink truncate max-w-[220px]">
          {user.email}
        </td>
        <td className="px-4 py-3 text-xs text-ink-3">
          {user.custom_limits ? "custom" : "default"}
        </td>
        <td className="px-4 py-3">
          <div className="space-y-1">
            {products.map(p => (
              <div key={p} className="flex items-center gap-2">
                <span className="text-xs text-ink-4 w-10">{productLabels[p]}</span>
                <QuotaBar {...user.quota[p]} />
              </div>
            ))}
          </div>
        </td>
        <td className="px-4 py-3 text-xs text-ink-4">
          {user.created_at ? new Date(user.created_at).toLocaleDateString() : "—"}
        </td>
        <td className="px-4 py-3 text-xs text-ink-4">
          <span className={`w-1.5 h-1.5 rounded-full inline-block mr-1 ${expanded ? "bg-brand" : "bg-ink-4/40"}`} />
          {expanded ? "▲" : "▼"}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-inset border-b border-edge">
          <td colSpan={5} className="px-4 py-4">
            <div className="space-y-4">
              {/* Limits */}
              <div className="space-y-2">
                <span className="text-xs text-ink-4 font-semibold uppercase tracking-wider">Monthly limits</span>
                {user.org_id && <p className="text-xs text-ink-4">This user is in an organisation: the organisation limits apply. Edit them on the overview page.</p>}
                {limits ? (
                  <LimitsEditor token={token} kind="users" id={user.id} limits={limits} onSaved={() => { loadLimits(); onAction(user.id, "refresh"); }} />
                ) : <p className="text-xs text-ink-4">Loading…</p>}
              </div>

              {/* Grant topup */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-4 font-semibold uppercase tracking-wider w-20">Extra units</span>
                {products.map(p => (
                  <button
                    key={p}
                    disabled={busy}
                    onClick={() => doAction("topup", { product: p, units: topupUnits[p] })}
                    className="px-3 py-1 rounded-lg text-xs font-semibold border border-edge text-ink-3 hover:border-brand hover:text-brand transition-colors disabled:opacity-40"
                    title={`+${topupUnits[p].toLocaleString()} ${productLabels[p]}`}
                  >
                    +{productLabels[p]}
                  </button>
                ))}
              </div>

              {/* Reset quota */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-4 font-semibold uppercase tracking-wider w-20">Quota</span>
                <button
                  disabled={busy}
                  onClick={() => doAction("reset")}
                  className="px-3 py-1 rounded-lg text-xs font-semibold border border-edge text-ink-3 hover:border-red-500 hover:text-red-400 transition-colors disabled:opacity-40"
                >
                  Reset monthly
                </button>
              </div>

              {/* Info */}
              <div className="text-xs text-ink-4 space-y-0.5">
                <p>ID: {user.id}</p>
                {user.org_id && <p>Org: {user.org_id}</p>}
                <p>Period: {user.monthly_period ?? "—"}</p>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const token = Cookies.get("ag_admin_token") ?? "";

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminUsers(token);
      setUsers(data.users);
      setTotal(data.total);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error loading users");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(""), 3000);
  }

  async function handleAction(userId: string, action: string, extra?: unknown) {
    try {
      if (action === "refresh") {
        showToast("Limits updated");
      } else if (action === "topup") {
        const { product, units } = extra as { product: QuotaProduct; units: number };
        await grantTopup(token, userId, product, units);
        showToast(`Extra units granted: ${units.toLocaleString()} ${product}`);
      } else if (action === "reset") {
        await resetUserQuota(token, userId);
        showToast("Quota reset");
      }
      await load();
    } catch (e: unknown) {
      showToast((e instanceof Error ? e.message : "Action failed") + " ✗");
    }
  }

  const filtered = search
    ? users.filter(u => u.email.toLowerCase().includes(search.toLowerCase()))
    : users;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-ink">Users</h1>
          <p className="text-sm text-ink-3 mt-0.5">{total} total</p>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="text"
            placeholder="Search email…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>
      </div>

      {toast && (
        <div className="px-4 py-2.5 rounded-lg bg-brand/10 border border-brand/20 text-sm text-brand font-medium">
          {toast}
        </div>
      )}

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {loading ? (
        <p className="text-ink-4 text-sm">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-ink-4 text-sm">No users found.</p>
      ) : (
        <div className="bg-card border border-edge rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-inset text-xs text-ink-4 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2.5 text-left">Email</th>
                <th className="px-4 py-2.5 text-left">Limits</th>
                <th className="px-4 py-2.5 text-left">Quota</th>
                <th className="px-4 py-2.5 text-left">Joined</th>
                <th className="px-4 py-2.5 text-left"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <UserRow key={u.id} user={u} token={token} onAction={handleAction} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
