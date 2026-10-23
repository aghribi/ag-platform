"use client";
import React, { useRef, useState } from "react";
import Cookies from "js-cookie";
import { adminCompose, fetchAdminUsers } from "@/lib/admin-api";

export default function AdminComposePage() {
  const [to, setTo] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const token = Cookies.get("ag_admin_token") ?? "";

  function handleToChange(val: string) {
    setTo(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (val.length < 2) { setSuggestions([]); return; }
    debounceRef.current = setTimeout(async () => {
      try {
        const data = await fetchAdminUsers(token);
        const matches = data.users
          .filter(u => u.email.toLowerCase().includes(val.toLowerCase()))
          .map(u => u.email)
          .slice(0, 6);
        setSuggestions(matches);
        setShowSuggestions(matches.length > 0);
      } catch {
        setSuggestions([]);
      }
    }, 300);
  }

  async function handleSend() {
    if (!to.trim() || !subject.trim() || !body.trim()) return;
    setSending(true);
    setToast(null);
    try {
      await adminCompose(token, to.trim(), subject.trim(), body.trim());
      setToast({ msg: `Email sent to ${to}`, ok: true });
      setSubject("");
      setBody("");
    } catch (e: unknown) {
      setToast({ msg: e instanceof Error ? e.message : "Send failed", ok: false });
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-ink">Compose</h1>
        <p className="text-sm text-ink-3 mt-0.5">Send a freeform email from the platform sender address</p>
      </div>

      {toast && (
        <div className={`px-4 py-2.5 rounded-lg text-sm font-medium border ${
          toast.ok
            ? "bg-green-500/10 border-green-500/20 text-green-400"
            : "bg-red-500/10 border-red-500/20 text-red-400"
        }`}>
          {toast.msg}
        </div>
      )}

      <div className="bg-card border border-edge rounded-xl p-6 space-y-4">
        {/* To */}
        <div className="relative">
          <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">To</label>
          <input
            type="email"
            value={to}
            onChange={e => handleToChange(e.target.value)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            onFocus={() => suggestions.length > 0 && setShowSuggestions(true)}
            placeholder="recipient@example.com"
            className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand"
          />
          {showSuggestions && (
            <ul className="absolute z-10 mt-1 w-full bg-card border border-edge rounded-lg shadow-lg overflow-hidden">
              {suggestions.map(s => (
                <li
                  key={s}
                  onMouseDown={() => { setTo(s); setSuggestions([]); setShowSuggestions(false); }}
                  className="px-3 py-2 text-sm text-ink hover:bg-inset cursor-pointer"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Subject */}
        <div>
          <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">Subject</label>
          <input
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            placeholder="Your subject line"
            className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand"
          />
        </div>

        {/* Body */}
        <div>
          <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">Message</label>
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={10}
            placeholder="Write your message here. Plain text — line breaks are preserved."
            className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand resize-y font-mono"
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          <p className="text-xs text-ink-4">{body.length} chars</p>
          <button
            onClick={handleSend}
            disabled={sending || !to.trim() || !subject.trim() || !body.trim()}
            className="px-5 py-2 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-40 flex items-center gap-2"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
            {sending ? "Sending…" : "Send email"}
          </button>
        </div>
      </div>
    </div>
  );
}
