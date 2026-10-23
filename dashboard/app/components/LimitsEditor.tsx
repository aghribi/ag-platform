"use client";
import React, { useState } from "react";
import { setLimits, type LimitKey, type Limits } from "@/lib/admin-api";

const FIELDS: { key: LimitKey; product: keyof Limits; label: string }[] = [
  { key: "pii_limit",       product: "pii_vault",    label: "PII tokens / mo" },
  { key: "eval_limit",      product: "evalforge",    label: "Eval runs / mo" },
  { key: "guardrail_limit", product: "guardrail",    label: "Guardrail checks / mo" },
  { key: "doc_limit",       product: "docparse",     label: "Doc pages / mo" },
  { key: "llm_judge_limit", product: "llm_judge",    label: "LLM judge calls / mo" },
  { key: "schema_slots",    product: "schema_slots", label: "DocParse schemas" },
];

/** Edit the monthly limits of a user or an organisation. An empty field resets it to the default. */
export default function LimitsEditor({
  token, kind, id, limits, seatLimit, onSaved,
}: {
  token: string;
  kind: "users" | "orgs";
  id: string;
  limits: Limits;
  seatLimit?: number;
  onSaved: () => void;
}) {
  const initial: Record<string, string> = Object.fromEntries(
    FIELDS.map(f => [f.key, limits[f.product].custom ? String(limits[f.product].limit) : ""]),
  );
  if (kind === "orgs") initial.seat_limit = seatLimit !== undefined ? String(seatLimit) : "";
  const [values, setValues] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function save() {
    setBusy(true); setMsg("");
    const body: Record<string, number | null> = {};
    for (const [k, v] of Object.entries(values)) {
      if (v !== initial[k]) body[k] = v.trim() === "" ? null : Number(v);
    }
    try {
      await setLimits(token, kind, id, body);
      setMsg("Saved");
      onSaved();
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : "Failed");
    }
    setBusy(false);
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {FIELDS.map(f => (
          <label key={f.key} className="text-xs text-ink-3 space-y-1">
            <span>{f.label}</span>
            <input
              type="number" min={0}
              value={values[f.key]}
              placeholder={limits[f.product].custom ? "default" : `default ${limits[f.product].limit}`}
              onChange={e => setValues(v => ({ ...v, [f.key]: e.target.value }))}
              className="w-full px-2 py-1.5 rounded-md bg-inset border border-edge text-sm text-ink"
            />
          </label>
        ))}
        {kind === "orgs" && (
          <label className="text-xs text-ink-3 space-y-1">
            <span>Seats</span>
            <input
              type="number" min={1}
              value={values.seat_limit}
              onChange={e => setValues(v => ({ ...v, seat_limit: e.target.value }))}
              className="w-full px-2 py-1.5 rounded-md bg-inset border border-edge text-sm text-ink"
            />
          </label>
        )}
      </div>
      <div className="flex items-center gap-3">
        <button
          onClick={save}
          disabled={busy}
          className="px-3 py-1.5 rounded-lg bg-brand text-white text-xs font-semibold disabled:opacity-40"
        >
          {busy ? "Saving…" : "Save limits"}
        </button>
        <span className="text-xs text-ink-4">Leave a field empty to use the default.</span>
        {msg && <span className="text-xs text-ink-3">{msg}</span>}
      </div>
    </div>
  );
}
