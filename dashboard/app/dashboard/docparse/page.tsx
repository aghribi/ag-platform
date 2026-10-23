"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { getDocStats } from "@/lib/api";
import { API_URL, isApiKey } from "@/lib/config";

type Stats = { monthly_usage: number; monthly_period: string; quota: number };
type Job = { job_id: string; status: string; schema_name: string; created_at: string; completed_at: string | null; error: string | null };

const SCHEMAS = [
  { name: "invoice",          label: "Invoice",           fields: "invoice_number, vendor, amount, due_date, line_items" },
  { name: "loan_application", label: "Loan Application",  fields: "applicant, loan_amount, income, employment, credit_score" },
  { name: "w2",               label: "W-2 Tax Form",      fields: "employee, employer, tax_year, wages, federal_tax" },
  { name: "nda",              label: "NDA",               fields: "parties, effective_date, duration, governing_law" },
  { name: "contract",         label: "Contract",          fields: "parties, dates, value, governing_law, termination" },
];

const STATUS_COLORS: Record<string, string> = {
  pending:    "bg-yellow-50 text-yellow-700",
  processing: "bg-blue-50 text-blue-700",
  completed:  "bg-green-50 text-green-700",
  failed:     "bg-red-50 text-red-700",
};

const BASE = API_URL;

export default function DocParsePage() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const token = Cookies.get("ag_token");
    if (!token) { router.replace("/login"); return; }
    getDocStats(token).then(setStats).catch(() => setError("Could not load stats."));
  }, [router]);

  async function loadJobs(key: string) {
    const r = await fetch(`${BASE}/v1/doc/jobs`, { headers: { Authorization: `Bearer ${key}` } });
    if (r.ok) setJobs(await r.json());
  }

  function handleKeySubmit(e: React.FormEvent) {
    e.preventDefault();
    if (isApiKey(apiKey)) loadJobs(apiKey);
  }

  const usagePct = stats ? Math.min(100, Math.round((stats.monthly_usage / stats.quota) * 100)) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{background:"rgba(52,211,153,0.1)",border:"1px solid rgba(52,211,153,0.2)"}}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="#34d399"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd"/></svg>
        </div>
        <div>
          <h1 className="text-2xl font-bold text-ink">DocParse</h1>
          <p className="mt-0.5 text-sm text-ink-3">LLM-powered structured extraction — sync for short docs, async queue + webhook for large PDFs.</p>
        </div>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{error}</div>}

      {stats && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Extractions this month" value={stats.monthly_usage.toLocaleString()} sub={stats.monthly_period} />
            <StatCard label="Monthly limit" value={stats.quota.toLocaleString()} sub="units / month" />
            <StatCard label="Built-in schemas" value="5" sub="+ custom fields" />
          </div>

          <div className="bg-card rounded-xl border border-edge p-5 space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-ink-3">Monthly quota</span>
              <span className="font-medium text-ink">{stats.monthly_usage.toLocaleString()} / {stats.quota.toLocaleString()}</span>
            </div>
            <div className="h-2 bg-inset rounded-full overflow-hidden">
              <div className={`h-full rounded-full transition-all ${usagePct > 80 ? "bg-red-500" : "bg-brand"}`} style={{ width: `${usagePct}%` }} />
            </div>
            <p className="text-xs text-ink-4">{usagePct}% used this month</p>
          </div>
        </>
      )}

      {/* Built-in schemas */}
      <div className="bg-card rounded-xl border border-edge divide-y divide-edge-2">
        <div className="px-5 py-3">
          <p className="text-xs text-ink-3 font-medium uppercase tracking-wide">Built-in schemas</p>
        </div>
        {SCHEMAS.map(s => (
          <div key={s.name} className="px-5 py-3">
            <p className="text-sm font-medium text-ink">{s.label}</p>
            <p className="text-xs text-ink-4 mt-0.5 font-mono">{s.fields}</p>
          </div>
        ))}
      </div>

      {/* Async jobs */}
      <div className="bg-card rounded-xl border border-edge p-5 space-y-4">
        <div>
          <h2 className="text-sm font-semibold text-ink">Async Jobs</h2>
          <p className="text-xs text-ink-3 mt-0.5">Jobs submitted via POST /v1/doc/jobs. Enter your API key to view recent jobs.</p>
        </div>

        {!isApiKey(apiKey) ? (
          <form onSubmit={handleKeySubmit} className="flex gap-2">
            <input type="text" placeholder="ag_live_..." value={apiKey} onChange={e => setApiKey(e.target.value)}
              className="flex-1 text-sm bg-inset border border-edge rounded-lg px-3 py-2 text-ink placeholder:text-ink-4 focus:outline-none focus:border-brand" />
            <button type="submit" className="bg-brand text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-brand-hi transition-colors">Load</button>
          </form>
        ) : jobs.length === 0 ? (
          <p className="text-xs text-ink-4">No async jobs yet.</p>
        ) : (
          <div className="divide-y divide-edge-2 border border-edge rounded-lg overflow-hidden">
            {jobs.map(j => (
              <div key={j.job_id} className="flex items-center justify-between px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-ink font-mono">{j.job_id.slice(0, 8)}…</p>
                  <p className="text-xs text-ink-3">{j.schema_name} · {new Date(j.created_at).toLocaleString()}</p>
                  {j.error && <p className="text-xs text-red-500 mt-0.5">{j.error}</p>}
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${STATUS_COLORS[j.status] ?? "bg-inset text-ink-3"}`}>
                  {j.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Quick start — sync (short docs)</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`import httpx

client = httpx.Client(
    base_url="${API_URL}",
    headers={"Authorization": "Bearer ag_live_..."},
)

resp = client.post("/v1/doc/extract", json={
    "schema_name": "invoice",
    "text": "Invoice #INV-2024-001 from Acme Corp...\\nTotal due: $1,250.00",
})
print(resp.json())
# {"schema_name": "invoice", "fields": {"invoice_number": {"value": "INV-2024-001", ...}}}`}</pre>
      </div>

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Quick start — async queue (large PDFs)</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`import time, httpx

client = httpx.Client(
    base_url="${API_URL}",
    headers={"Authorization": "Bearer ag_live_..."},
)

# Submit job — returns immediately with job_id
job = client.post("/v1/doc/jobs", json={
    "schema_name": "contract",
    "text": long_pdf_text,               # pass extracted text from pdfplumber
    "webhook_url": "https://yourapp.com/webhooks/docparse",  # optional
}).json()

# Poll until done
while job["status"] in ("pending", "processing"):
    time.sleep(2)
    job = client.get(f"/v1/doc/jobs/{job['job_id']}").json()

print(job["result"])  # {"parties": {"value": [...], "confidence": 0.97}, ...}

# Or receive via webhook — no polling needed:
# POST https://yourapp.com/webhooks/docparse
# {"job_id": "...", "status": "completed", "schema_name": "contract", "fields": {...}}`}</pre>
      </div>

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Custom fields</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`resp = client.post("/v1/doc/extract", json={
    "text": "...",
    "fields": [
        {"name": "patient_name", "description": "Full name of the patient", "required": True},
        {"name": "diagnosis",    "description": "Primary diagnosis code (ICD-10)", "type": "string"},
        {"name": "visit_date",   "description": "Date of the visit", "type": "date"},
    ],
})`}</pre>
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
