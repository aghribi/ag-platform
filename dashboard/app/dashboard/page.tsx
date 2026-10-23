"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import {
  getMe, getUsage, updateSettings, downloadUsageCsv,
  getPiiVaultMeStats, getEvalStats, getGuardrailStats, getDocStats,
} from "@/lib/api";
import { CONTACT_EMAIL, DOCS_URL } from "@/lib/config";

type ProductStats = { monthly_usage: number; quota: number };

const PRODUCT_META = [
  { key: "pii_vault" as const,  label: "PII Vault",  unit: "tokens",  color: "#0ea5e9", href: "/dashboard/pii-vault" },
  { key: "evalforge" as const,  label: "EvalForge",  unit: "runs",    color: "#d946ef", href: "/dashboard/eval" },
  { key: "guardrail" as const,  label: "Guardrail",  unit: "checks",  color: "#ef4444", href: "/dashboard/guardrail" },
  { key: "docparse" as const,   label: "DocParse",   unit: "pages",   color: "#34d399", href: "/dashboard/docparse" },
];

function QuotaBar({
  label, used, quota, unit, color,
}: {
  label: string; used: number; quota: number; unit: string; color: string;
}) {
  const pct = quota > 0 ? Math.min(100, Math.round((used / quota) * 100)) : 0;
  const isWarning = pct >= 80;
  return (
    <div className={`rounded-xl border p-4 space-y-3 ${isWarning ? "border-amber-300 bg-amber-50" : "border-edge bg-card"}`}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-ink">{label}</span>
        <span className="text-xs text-ink-3">{used.toLocaleString()} / {quota.toLocaleString()} {unit}</span>
      </div>
      <div className="h-2 bg-inset rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: pct >= 95 ? "#ef4444" : pct >= 80 ? "#f59e0b" : color }}
        />
      </div>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-medium ${pct >= 95 ? "text-red-600" : pct >= 80 ? "text-amber-700" : "text-ink-4"}`}>
          {pct}% used
        </span>
        {isWarning && (
          <a
            href={`mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(`Higher ${label} limit`)}`}
            className="text-xs font-medium text-amber-800 hover:text-amber-900 underline underline-offset-2"
          >
            Request a higher limit →
          </a>
        )}
      </div>
    </div>
  );
}

const PRODUCTS = [
  {
    name: "PII Vault", href: "/dashboard/pii-vault", description: "Tokenize PII in AI pipelines",
    color: "#0ea5e9", icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="#0ea5e9"><path fillRule="evenodd" d="M9.661 2.237a.531.531 0 01.678 0 11.947 11.947 0 007.078 2.749.5.5 0 01.479.425c.069.52.104 1.05.104 1.589 0 5.162-3.26 9.563-7.834 11.256a.48.48 0 01-.332 0C5.26 16.563 2 12.162 2 7c0-.538.035-1.069.104-1.589a.5.5 0 01.48-.425 11.947 11.947 0 007.077-2.749z" clipRule="evenodd"/></svg>,
  },
  {
    name: "EvalForge", href: "/dashboard/eval", description: "Eval runner for LLM apps",
    color: "#d946ef", icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="#d946ef"><path d="M15.5 2A1.5 1.5 0 0014 3.5v13a1.5 1.5 0 003 0v-13A1.5 1.5 0 0015.5 2zM9.5 6A1.5 1.5 0 008 7.5v9a1.5 1.5 0 003 0v-9A1.5 1.5 0 009.5 6zM3.5 10A1.5 1.5 0 002 11.5v5a1.5 1.5 0 003 0v-5A1.5 1.5 0 003.5 10z"/></svg>,
  },
  {
    name: "Guardrail", href: "/dashboard/guardrail", description: "Runtime safety proxy",
    color: "#ef4444", icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="#ef4444"><path fillRule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clipRule="evenodd"/></svg>,
  },
  {
    name: "DocParse", href: "/dashboard/docparse", description: "Structured document extraction",
    color: "#34d399", icon: <svg width="18" height="18" viewBox="0 0 20 20" fill="#34d399"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd"/></svg>,
  },
];

export default function DashboardHome() {
  const router = useRouter();
  const [user, setUser] = useState<{ email: string; monthly_token_count: number; monthly_period: string | null } | null>(null);
  const [usage, setUsage] = useState<{ period: string; total: number; by_product: { product: string; units: number }[] } | null>(null);
  const [productStats, setProductStats] = useState<Record<string, ProductStats>>({});
  const [warnThreshold, setWarnThreshold] = useState(80);
  const [savingThreshold, setSavingThreshold] = useState(false);
  const [thresholdSaved, setThresholdSaved] = useState(false);

  useEffect(() => {
    const t = Cookies.get("ag_token");
    if (!t) { router.replace("/login"); return; }
    getMe(t).then(setUser).catch(() => router.replace("/login"));
    getUsage(t).then(setUsage).catch(() => {});
    Promise.allSettled([
      getPiiVaultMeStats(t).then(s => ({ pii_vault: s })),
      getEvalStats(t).then(s => ({ evalforge: s })),
      getGuardrailStats(t).then(s => ({ guardrail: s })),
      getDocStats(t).then(s => ({ docparse: s })),
    ]).then(results => {
      const merged: Record<string, ProductStats> = {};
      for (const r of results) {
        if (r.status === "fulfilled") Object.assign(merged, r.value);
      }
      setProductStats(merged);
    });
  }, [router]);

  async function handleSaveThreshold() {
    const t = Cookies.get("ag_token");
    if (!t) return;
    setSavingThreshold(true);
    try {
      await updateSettings(t, warnThreshold);
      setThresholdSaved(true);
      setTimeout(() => setThresholdSaved(false), 2000);
    } catch { /* ignore */ }
    setSavingThreshold(false);
  }

  function handleExportUsage() {
    const t = Cookies.get("ag_token");
    if (!t) return;
    downloadUsageCsv(t).catch(() => {});
  }

  const hasAnyStats = Object.keys(productStats).length > 0;

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-ink">Dashboard</h1>
          {user && (
            <p className="mt-1 text-sm text-ink-3">
              {user.email}
              {user.monthly_period && (
                <> · {user.monthly_token_count.toLocaleString()} total units this month</>
              )}
            </p>
          )}
        </div>

      </div>

      {/* Getting started — shown until the user makes their first API call */}
      {usage !== null && usage.total === 0 && (
        <div className="bg-card rounded-xl border border-brand/30 p-5 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-base">🚀</span>
            <h2 className="text-sm font-semibold text-ink">Get started in 2 minutes</h2>
          </div>
          <ol className="space-y-3">
            <li className="flex items-start gap-3">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand text-white text-xs font-bold flex items-center justify-center mt-0.5">1</span>
              <div>
                <p className="text-sm font-medium text-ink">Create an API key</p>
                <p className="text-xs text-ink-3 mt-0.5">Go to <Link href="/dashboard/keys" className="text-brand hover:underline font-medium">API Keys →</Link> and click &quot;Create&quot;. Copy it — it&apos;s shown only once.</p>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand text-white text-xs font-bold flex items-center justify-center mt-0.5">2</span>
              <div>
                <p className="text-sm font-medium text-ink">Install the SDK</p>
                <code className="inline-block mt-1 text-xs bg-inset border border-edge-3 rounded-md px-2 py-1 font-mono text-ink-2">pip install ag-pii-vault</code>
              </div>
            </li>
            <li className="flex items-start gap-3">
              <span className="flex-shrink-0 w-5 h-5 rounded-full bg-brand text-white text-xs font-bold flex items-center justify-center mt-0.5">3</span>
              <div>
                <p className="text-sm font-medium text-ink">Make your first call</p>
                <p className="text-xs text-ink-3 mt-0.5">
                  See the <a href={DOCS_URL} target="_blank" rel="noopener" className="text-brand hover:underline font-medium">quickstart guide →</a> or open an interactive{" "}
                  <a href="https://github.com/aghribi/ag-notebooks" target="_blank" rel="noopener" className="text-brand hover:underline font-medium">Jupyter notebook →</a>
                </p>
              </div>
            </li>
          </ol>
        </div>
      )}

      {/* Per-product quota bars */}
      {hasAnyStats && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">Quota this month</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {PRODUCT_META.map(pm => {
              const s = productStats[pm.key];
              if (!s) return null;
              return (
                <QuotaBar
                  key={pm.key}
                  label={pm.label}
                  used={s.monthly_usage}
                  quota={s.quota}
                  unit={pm.unit}
                  color={pm.color}
                />
              );
            })}
          </div>
        </div>
      )}

      {/* Usage breakdown */}
      {usage && usage.total > 0 && (
        <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-ink">Usage breakdown</h2>
            <span className="text-xs text-ink-4">{usage.period}</span>
          </div>
          <div className="space-y-2">
            {usage.by_product.map(p => {
              const pct = Math.round((p.units / usage.total) * 100);
              const meta = PRODUCT_META.find(m => m.key === p.product);
              return (
                <div key={p.product}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-ink-2">{meta?.label ?? p.product}</span>
                    <span className="text-ink-3">{p.units.toLocaleString()} · {pct}%</span>
                  </div>
                  <div className="h-1.5 bg-inset rounded-full overflow-hidden">
                    <div className="h-full rounded-full" style={{ width: `${pct}%`, background: meta?.color ?? "#6366f1" }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="text-xs text-ink-4 pt-1">Total: {usage.total.toLocaleString()} units</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {PRODUCTS.map(p => (
          <div key={p.name} className="bg-card rounded-xl border border-edge hover:border-brand transition-colors p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: `color-mix(in srgb, ${p.color} 12%, transparent)`, border: `1px solid color-mix(in srgb, ${p.color} 25%, transparent)` }}>
                  {p.icon}
                </div>
                <div>
                  <h2 className="font-semibold text-ink">{p.name}</h2>
                  <p className="text-sm text-ink-3">{p.description}</p>
                </div>
              </div>
              <span className="text-xs font-medium bg-green-50 text-green-700 px-2 py-0.5 rounded-full shrink-0 ml-2">Live</span>
            </div>
            <Link href={p.href} className="mt-4 inline-block text-sm font-medium text-brand hover:underline">
              Open →
            </Link>
          </div>
        ))}
      </div>

      {/* Settings */}
      <div className="bg-card rounded-xl border border-edge p-6 space-y-5">
        <h2 className="font-semibold text-ink">Settings</h2>
        <div className="space-y-2">
          <label className="text-sm font-medium text-ink-2">Quota warning threshold</label>
          <p className="text-xs text-ink-4">Email alert when usage reaches this percentage of your monthly quota.</p>
          <div className="flex flex-wrap items-center gap-3">
            <input
              type="range" min={10} max={95} step={5}
              value={warnThreshold}
              onChange={e => setWarnThreshold(parseInt(e.target.value))}
              className="flex-1 accent-sky-600"
            />
            <span className="text-sm font-medium text-ink w-10 text-right">{warnThreshold}%</span>
            <button
              onClick={handleSaveThreshold}
              disabled={savingThreshold}
              className="bg-brand hover:bg-brand-hi disabled:opacity-50 text-white px-3 py-1.5 rounded-lg text-xs font-medium"
            >
              {thresholdSaved ? "Saved!" : savingThreshold ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
        <div className="pt-2 border-t border-edge flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-ink">Export usage history</p>
            <p className="text-xs text-ink-4">Download a CSV of all API calls (last 10,000).</p>
          </div>
          <button onClick={handleExportUsage} className="text-sm text-brand hover:underline font-medium">
            Download CSV
          </button>
        </div>
      </div>
    </div>
  );
}
