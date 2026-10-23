"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { getEvalStats } from "@/lib/api";
import { API_URL } from "@/lib/config";

type Stats = { monthly_usage: number; monthly_period: string; quota: number };

export default function EvalPage() {
  const router = useRouter();
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = Cookies.get("ag_token");
    if (!token) { router.replace("/login"); return; }
    getEvalStats(token).then(setStats).catch(() => setError("Could not load stats."));
  }, [router]);

  const usagePct = stats ? Math.min(100, Math.round((stats.monthly_usage / stats.quota) * 100)) : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{background:"rgba(217,70,239,0.1)",border:"1px solid rgba(217,70,239,0.2)"}}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="#d946ef"><path d="M15.5 2A1.5 1.5 0 0014 3.5v13a1.5 1.5 0 003 0v-13A1.5 1.5 0 0015.5 2zM9.5 6A1.5 1.5 0 008 7.5v9a1.5 1.5 0 003 0v-9A1.5 1.5 0 009.5 6zM3.5 10A1.5 1.5 0 002 11.5v5a1.5 1.5 0 003 0v-5A1.5 1.5 0 003.5 10z"/></svg>
        </div>
        <div>
          <h1 className="text-2xl font-bold text-ink">EvalForge</h1>
          <p className="mt-0.5 text-sm text-ink-3">Eval runner for LLM applications — score outputs against expected answers.</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">{error}</div>
      )}

      {stats && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="Evals this month" value={stats.monthly_usage.toLocaleString()} sub={stats.monthly_period} />
            <StatCard label="Monthly limit" value={stats.quota.toLocaleString()} sub="units / month" />
            <StatCard label="Scorers" value="4" sub="exact · rouge_l · regex · llm_judge" />
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
        <h2 className="text-sm font-semibold text-ink">Quick start — hosted API</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`import httpx

client = httpx.Client(
    base_url="${API_URL}",
    headers={"Authorization": "Bearer ag_live_..."},
)

# Deterministic scorer
resp = client.post("/v1/eval/score", json={
    "scorer": "rouge_l",
    "threshold": 0.6,
    "cases": [
        {"input": "Capital of France?",
         "output": "The capital of France is Paris.",
         "expected": "Paris"},
    ],
})

# LLM judge scorer (GPT-4o-mini, subjective tasks)
resp = client.post("/v1/eval/score", json={
    "scorer": "llm_judge",
    "threshold": 0.7,
    "criteria": "Is the answer concise, accurate, and professional?",
    "cases": [
        {"input": "Summarise our refund policy.",
         "output": "Refunds are processed within 5 business days."},
    ],
})
print(resp.json())
# {"scorer": "llm_judge", "mean_score": 0.92, "pass_rate": 1.0,
#  "results": [{"score": 0.92, "rationale": "Clear and professional.", ...}]}`}</pre>
      </div>

      <div className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Quick start — Python SDK</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2 font-mono">{`pip install ag-evalforge

from ag_evalforge import run_eval, EvalCase, RougeScorer

report = run_eval(
    cases=[
        EvalCase(input="Capital of France?", output="Paris", expected="Paris"),
    ],
    scorer=RougeScorer(threshold=0.6),
)
print(report.summary())`}</pre>
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
