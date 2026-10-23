"use client";
import React, { useEffect, useState } from "react";
import Cookies from "js-cookie";
import { fetchAdminMetrics, type AdminMetrics } from "@/lib/admin-api";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-card border border-edge rounded-xl p-5">
      <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink">{value}</p>
      {sub && <p className="text-xs text-ink-3 mt-0.5">{sub}</p>}
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="text-sm font-semibold text-ink-4 uppercase tracking-wider">{children}</h2>;
}

export default function AdminMetricsPage() {
  const [data, setData] = useState<AdminMetrics | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = Cookies.get("ag_admin_token") ?? "";
    fetchAdminMetrics(token).then(setData).catch(e => setError(e.message));
  }, []);

  if (error) return <p className="text-red-500 text-sm">{error}</p>;
  if (!data) return <p className="text-ink-4 text-sm">Loading…</p>;

  const totalAiCost  = data.ai_usage.reduce((s, r) => s + r.cost_usd, 0);

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-xl font-bold text-ink">Metrics</h1>
        <p className="text-sm text-ink-3 mt-0.5">Storage · AI costs · Usage</p>
      </div>

      {/* ── Summary cards ── */}
      <div className="grid grid-cols-2 gap-4">
        <StatCard label="AI cost (all-time)" value={`$${totalAiCost.toFixed(4)}`} sub="USD" />
        <StatCard label="Vault entries" value={(data.storage?.vault_entries ?? 0).toLocaleString()} sub={`${data.storage?.vault_mb ?? 0} MB`} />
      </div>

      {/* ── Storage ── */}
      <div className="space-y-3">
        <SectionTitle>Storage</SectionTitle>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard label="Vault entries" value={(data.storage?.vault_entries ?? 0).toLocaleString()} />
          <StatCard label="Vault size" value={`${data.storage?.vault_mb ?? 0} MB`} sub={`${(data.storage?.vault_bytes ?? 0).toLocaleString()} bytes`} />
          <StatCard label="Usage log events" value={(data.storage?.usage_log_events ?? 0).toLocaleString()} />
        </div>
      </div>

      {/* ── AI token usage + cost by month ── */}
      <div className="space-y-3">
        <SectionTitle>AI token usage &amp; cost</SectionTitle>
        {data.ai_usage.length === 0 ? (
          <p className="text-ink-4 text-sm">No AI calls logged yet — usage will appear here after the first LLM call.</p>
        ) : (
          <div className="bg-card border border-edge rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-inset text-xs text-ink-4 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-2.5 text-left">Month</th>
                  <th className="px-5 py-2.5 text-right">Calls</th>
                  <th className="px-5 py-2.5 text-right">Input tokens</th>
                  <th className="px-5 py-2.5 text-right">Output tokens</th>
                  <th className="px-5 py-2.5 text-right">Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {data.ai_usage.map(m => (
                  <React.Fragment key={m.month}>
                    <tr className="border-t border-edge bg-inset/30">
                      <td className="px-5 py-2.5 font-semibold text-ink" colSpan={1}>{m.month}</td>
                      <td className="px-5 py-2.5 text-right font-semibold text-ink">{m.calls.toLocaleString()}</td>
                      <td className="px-5 py-2.5 text-right font-semibold text-ink">{m.input_tokens.toLocaleString()}</td>
                      <td className="px-5 py-2.5 text-right font-semibold text-ink">{m.output_tokens.toLocaleString()}</td>
                      <td className="px-5 py-2.5 text-right font-semibold text-brand">${m.cost_usd.toFixed(4)}</td>
                    </tr>
                    {m.by_product.map((p, i) => (
                      <tr key={i} className="border-t border-edge/50 hover:bg-inset/50">
                        <td className="px-5 py-2 text-ink-4 pl-10 text-xs">{p.product} · {p.model.split("-").slice(0, 2).join("-")}</td>
                        <td className="px-5 py-2 text-right text-xs text-ink-4">{p.calls.toLocaleString()}</td>
                        <td className="px-5 py-2 text-right text-xs text-ink-4">{p.input_tokens.toLocaleString()}</td>
                        <td className="px-5 py-2 text-right text-xs text-ink-4">{p.output_tokens.toLocaleString()}</td>
                        <td className="px-5 py-2 text-right text-xs text-ink-3">${p.cost_usd.toFixed(4)}</td>
                      </tr>
                    ))}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Top users ── */}
      {data.top_users.length > 0 && (
        <div className="space-y-3">
          <SectionTitle>Top users by usage this period</SectionTitle>
          <div className="bg-card border border-edge rounded-xl overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-inset text-xs text-ink-4 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-2.5 text-left">Email</th>
                  <th className="px-5 py-2.5 text-right">Total usage</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-edge">
                {data.top_users.map(u => (
                  <tr key={u.id} className="hover:bg-inset/50">
                    <td className="px-5 py-3 text-ink font-medium truncate max-w-[260px]">{u.email}</td>
                    <td className="px-5 py-3 text-right text-ink">{u.total_usage.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
