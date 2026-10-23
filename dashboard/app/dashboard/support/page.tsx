"use client";
import React, { useState } from "react";
import Cookies from "js-cookie";

import { API_URL as BASE, DOCS_URL } from "@/lib/config";

const TICKET_TYPES = [
  { value: "bug",        label: "Bug report",          desc: "Something isn't working as expected" },
  { value: "feature",    label: "Feature request",     desc: "Suggest an improvement or new capability" },
  { value: "quota",      label: "Higher limit",        desc: "Request a higher monthly limit for a product" },
  { value: "other",      label: "Other",               desc: "Anything else" },
] as const;

type TicketType = (typeof TICKET_TYPES)[number]["value"];

export default function SupportPage() {
  const [ticketType, setTicketType] = useState<TicketType>("bug");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!subject.trim() || !message.trim()) return;
    setSending(true);
    setError("");
    try {
      const token = Cookies.get("ag_token") ?? "";
      const r = await fetch(`${BASE}/support/ticket/me`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ subject: subject.trim(), message: message.trim(), ticket_type: ticketType }),
      });
      if (!r.ok) throw new Error((await r.json()).detail ?? "Submission failed");
      setDone(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSending(false);
    }
  }

  if (done) {
    return (
      <div className="max-w-lg">
        <div className="bg-card border border-edge rounded-2xl p-10 text-center space-y-3">
          <div className="text-3xl">✓</div>
          <h2 className="text-lg font-bold text-ink">Ticket submitted</h2>
          <p className="text-sm text-ink-3">We received your message and will get back to you at your account email. Typical response time is 24–48 hours.</p>
          <button
            onClick={() => { setDone(false); setSubject(""); setMessage(""); setTicketType("bug"); }}
            className="mt-2 px-4 py-2 rounded-lg text-sm text-ink-3 border border-edge hover:border-brand hover:text-brand transition-colors"
          >
            Submit another
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Support</h1>
        <p className="text-sm text-ink-3 mt-0.5">Report an issue, request a feature, or reach out for commercial assistance.</p>
      </div>

      <div className="bg-card border border-edge rounded-xl p-6 space-y-5">
        {/* Type selector */}
        <div>
          <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider mb-2">Type</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {TICKET_TYPES.map(t => (
              <button
                key={t.value}
                onClick={() => setTicketType(t.value)}
                className={`text-left px-4 py-3 rounded-lg border transition-colors ${
                  ticketType === t.value
                    ? "border-brand bg-brand/5 text-ink"
                    : "border-edge text-ink-3 hover:border-brand/50 hover:text-ink"
                }`}
              >
                <p className="text-sm font-semibold">{t.label}</p>
                <p className="text-xs text-ink-4 mt-0.5">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Subject */}
        <div>
          <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">Subject</label>
          <input
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="Short summary of your request"
            className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand"
          />
        </div>

        {/* Message */}
        <div>
          <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">Message</label>
          <textarea
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={7}
            placeholder={
              ticketType === "bug"
                ? "Steps to reproduce, expected vs actual behaviour, SDK version…"
                : ticketType === "feature"
                ? "Describe the feature and your use case…"
                : ticketType === "quota"
                ? "Which product, what limit you need, and what for…"
                : "Your message…"
            }
            className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand resize-y"
          />
        </div>

        {error && <p className="text-xs text-red-500">{error}</p>}

        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-ink-4">We reply to your account email.</p>
          <button
            onClick={handleSubmit}
            disabled={sending || !subject.trim() || !message.trim()}
            className="px-5 py-2 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-40"
          >
            {sending ? "Submitting…" : "Submit ticket"}
          </button>
        </div>
      </div>

      {/* Quick links */}
      <div className="bg-card border border-edge rounded-xl p-5 space-y-2">
        <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider">Before submitting</p>
        <ul className="text-sm text-ink-3 space-y-1">
          <li>→ Check the <a href={DOCS_URL} target="_blank" rel="noopener" className="text-brand hover:underline">documentation</a> for common questions</li>
          <li>→ SDK bugs: include the package name, version, and a minimal reproducer</li>
        </ul>
      </div>
    </div>
  );
}
