"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { getPiiVaultMeStats } from "@/lib/api";
import { API_URL } from "@/lib/config";

type Stats = { total_entries: number; monthly_usage: number; monthly_period: string | null; quota: number };

export default function PiiVaultPage() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = Cookies.get("ag_token");
    if (!token) { router.replace("/login"); return; }
    getPiiVaultMeStats(token)
      .then(setStats)
      .catch(() => setError("Could not load vault stats."));
  }, [router]);

  const usagePct = stats ? Math.min(100, Math.round((stats.monthly_usage / stats.quota) * 100)) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{background:"rgba(14,165,233,0.1)",border:"1px solid rgba(14,165,233,0.2)"}}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="#0ea5e9"><path fillRule="evenodd" d="M9.661 2.237a.531.531 0 01.678 0 11.947 11.947 0 007.078 2.749.5.5 0 01.479.425c.069.52.104 1.05.104 1.589 0 5.162-3.26 9.563-7.834 11.256a.48.48 0 01-.332 0C5.26 16.563 2 12.162 2 7c0-.538.035-1.069.104-1.589a.5.5 0 01.48-.425 11.947 11.947 0 007.077-2.749z" clipRule="evenodd"/></svg>
        </div>
        <div>
          <h1 className="text-2xl font-bold text-ink">PII Vault</h1>
          <p className="mt-0.5 text-sm text-ink-3">Hosted token vault for your AI pipelines.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{error}</div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Total entries" value={stats.total_entries.toLocaleString()} />
            <StatCard label="This month" value={stats.monthly_usage.toLocaleString()} sub={stats.monthly_period ?? ""} />
            <StatCard label="Monthly limit" value={stats.quota.toLocaleString()} sub="units / month" />
          </div>

          <div className="bg-card rounded-xl border border-edge p-5 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-ink-3">Monthly quota</span>
              <span className="font-medium text-ink">{stats.monthly_usage.toLocaleString()} / {stats.quota.toLocaleString()}</span>
            </div>
            <div className="h-2 bg-inset rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${usagePct > 80 ? "bg-red-500" : "bg-brand"}`}
                style={{ width: `${usagePct}%` }}
              />
            </div>
            <p className="text-xs text-ink-4">{usagePct}% used this month</p>
          </div>
        </>
      )}

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Quick start — SDK proxy</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`pip install ag-pii-vault

from ag_pii_vault import SafeOpenAI, HostedVault

client = SafeOpenAI(
    api_key="sk-...",
    vault_key="your-hmac-secret",
    vault=HostedVault(api_key="ag_live_..."),
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Summarize for John Smith, john@acme.com"}],
)
# John Smith / john@acme.com never reached OpenAI — stored in your vault.`}</pre>
      </div>

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Quick start — hosted API with FPE</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`import httpx

client = httpx.Client(
    base_url="${API_URL}",
    headers={"Authorization": "Bearer ag_live_..."},
)

# Tokenize: detect PII → replace with format-preserving fakes
result = client.post("/v1/pii-vault/tokenize", json={
    "text": "Invoice for John Smith, john@acme.com. Card: 4111111111111111",
    "format_preserving": True,
    "subject_id": "user_42",          # optional — for DSAR deletion
}).json()

print(result["text"])
# "Invoice for Laura Torres, coolbear847@mailbox.net. Card: 4827364918273647"

print(result["entities"])
# [{"entity_type": "PERSON", "original": "John Smith",
#   "replacement": "Laura Torres", ...}, ...]

# Send result["text"] to your LLM — no real PII transmitted.

# Restore original values later
original = client.post("/v1/pii-vault/detokenize", json={
    "text": result["text"],
}).json()["text"]
# "Invoice for John Smith, john@acme.com. Card: 4111111111111111"`}</pre>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub, capitalize }: { label: string; value: string; sub?: string; capitalize?: boolean }) {
  return (
    <div className="bg-card rounded-xl border border-edge p-5">
      <p className="text-xs text-ink-3 font-medium uppercase tracking-wide">{label}</p>
      <p className={`text-2xl font-bold text-ink mt-1 ${capitalize ? "capitalize" : ""}`}>{value}</p>
      {sub && <p className="text-xs text-ink-4 mt-0.5">{sub}</p>}
    </div>
  );
}
