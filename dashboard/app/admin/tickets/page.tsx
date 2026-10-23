"use client";
import React, { useCallback, useEffect, useState } from "react";
import Cookies from "js-cookie";
import {
  fetchAdminTickets,
  updateTicket,
  deleteTicket,
  adminCompose,
  type SupportTicket,
} from "@/lib/admin-api";

const STATUS_COLORS: Record<string, string> = {
  open:    "bg-red-500/15 text-red-400",
  handled: "bg-amber-500/15 text-amber-400",
  closed:  "bg-ink-4/20 text-ink-4",
};

const FILTERS = ["", "open", "handled", "closed"] as const;

function TicketRow({
  ticket,
  onUpdate,
  onDelete,
}: {
  ticket: SupportTicket;
  onUpdate: (id: string, status: string, note?: string) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [expanded, setExpanded] = useState(false);
  const [note, setNote] = useState(ticket.admin_note ?? "");
  const [replyTo, setReplyTo] = useState(ticket.email);
  const [replySubject, setReplySubject] = useState(`Re: ${ticket.subject}`);
  const [replyBody, setReplyBody] = useState("");
  const [showReply, setShowReply] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const token = Cookies.get("ag_admin_token") ?? "";

  async function doStatus(status: string) {
    setBusy(true);
    try { await onUpdate(ticket.id, status, note || undefined); }
    finally { setBusy(false); }
  }

  async function saveNote() {
    setBusy(true);
    try { await onUpdate(ticket.id, ticket.status, note); setToast("Note saved"); setTimeout(() => setToast(""), 2000); }
    finally { setBusy(false); }
  }

  async function sendReply() {
    if (!replyBody.trim()) return;
    setBusy(true);
    try {
      await adminCompose(token, replyTo, replySubject, replyBody);
      setToast("Reply sent"); setTimeout(() => setToast(""), 2500);
      setShowReply(false);
      setReplyBody("");
      if (ticket.status === "open") await onUpdate(ticket.id, "handled", note || undefined);
    } catch (e: unknown) {
      setToast(e instanceof Error ? e.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <tr
        className="hover:bg-inset/50 cursor-pointer border-b border-edge"
        onClick={() => setExpanded(e => !e)}
      >
        <td className="px-4 py-3">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STATUS_COLORS[ticket.status]}`}>
            {ticket.status}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-ink font-medium truncate max-w-[180px]">{ticket.email}</td>
        <td className="px-4 py-3 text-sm text-ink truncate max-w-[260px]">{ticket.subject}</td>
        <td className="px-4 py-3 text-xs text-ink-4 whitespace-nowrap">
          {ticket.created_at ? new Date(ticket.created_at).toLocaleDateString() : "—"}
        </td>
        <td className="px-4 py-3 text-xs text-ink-4">{expanded ? "▲" : "▼"}</td>
      </tr>

      {expanded && (
        <tr className="bg-inset border-b border-edge">
          <td colSpan={5} className="px-4 py-5">
            <div className="space-y-4">
              {toast && <p className="text-xs font-medium text-brand">{toast}</p>}

              {/* Message */}
              <div className="bg-card border border-edge rounded-lg p-4">
                <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider mb-2">Message</p>
                <p className="text-sm text-ink whitespace-pre-wrap">{ticket.message}</p>
              </div>

              {/* Admin note */}
              <div>
                <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1.5">Admin note</p>
                <textarea
                  value={note}
                  onChange={e => setNote(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-card border border-edge text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brand resize-none"
                  placeholder="Internal note…"
                />
                <button
                  onClick={saveNote}
                  disabled={busy}
                  className="mt-1 px-3 py-1 rounded-lg text-xs font-semibold border border-edge text-ink-3 hover:border-brand hover:text-brand transition-colors disabled:opacity-40"
                >
                  Save note
                </button>
              </div>

              {/* Status actions */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs text-ink-4 font-semibold uppercase tracking-wider w-16">Status</span>
                {["open", "handled", "closed"].map(s => (
                  <button
                    key={s}
                    disabled={busy || ticket.status === s}
                    onClick={() => doStatus(s)}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold border transition-colors disabled:opacity-40 ${
                      ticket.status === s
                        ? "bg-brand/20 border-brand text-brand"
                        : "border-edge text-ink-3 hover:border-brand hover:text-brand"
                    }`}
                  >
                    {s}
                  </button>
                ))}
                <button
                  disabled={busy}
                  onClick={() => onDelete(ticket.id)}
                  className="ml-auto px-3 py-1 rounded-lg text-xs font-semibold border border-edge text-ink-4 hover:border-red-500 hover:text-red-400 transition-colors disabled:opacity-40"
                >
                  Delete
                </button>
              </div>

              {/* Reply */}
              <div>
                {!showReply ? (
                  <button
                    onClick={() => setShowReply(true)}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-brand text-white"
                  >
                    Reply by email
                  </button>
                ) : (
                  <div className="space-y-2 border border-edge rounded-lg p-4 bg-card">
                    <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider">Reply</p>
                    <input
                      type="text"
                      value={replyTo}
                      onChange={e => setReplyTo(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brand"
                    />
                    <input
                      type="text"
                      value={replySubject}
                      onChange={e => setReplySubject(e.target.value)}
                      className="w-full px-3 py-1.5 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brand"
                    />
                    <textarea
                      value={replyBody}
                      onChange={e => setReplyBody(e.target.value)}
                      rows={5}
                      autoFocus
                      className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-1 focus:ring-brand resize-none"
                      placeholder="Your reply…"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={sendReply}
                        disabled={busy || !replyBody.trim()}
                        className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-brand text-white disabled:opacity-40"
                      >
                        {busy ? "Sending…" : "Send & mark handled"}
                      </button>
                      <button
                        onClick={() => setShowReply(false)}
                        className="px-3 py-1.5 rounded-lg text-xs text-ink-3 hover:text-ink border border-edge"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AdminTicketsPage() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [open, setOpen] = useState(0);
  const [filter, setFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = Cookies.get("ag_admin_token") ?? "";

  const load = useCallback(async (status: string) => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminTickets(token, status || undefined);
      setTickets(data.tickets);
      setOpen(data.open);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(filter); }, [filter, load]);

  async function handleUpdate(id: string, status: string, note?: string) {
    await updateTicket(token, id, status, note);
    await load(filter);
  }

  async function handleDelete(id: string) {
    await deleteTicket(token, id);
    await load(filter);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-bold text-ink">Tickets</h1>
          <p className="text-sm text-ink-3 mt-0.5">
            {open > 0 ? <span className="text-red-400 font-semibold">{open} open</span> : "No open tickets"}
          </p>
        </div>

        <div className="flex rounded-lg border border-edge overflow-hidden text-xs font-semibold">
          {FILTERS.map(f => (
            <button
              key={f || "all"}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 transition-colors ${
                filter === f ? "bg-brand text-white" : "bg-card text-ink-3 hover:bg-inset"
              }`}
            >
              {f || "All"}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-red-500 text-sm">{error}</p>}

      {loading ? (
        <p className="text-ink-4 text-sm">Loading…</p>
      ) : tickets.length === 0 ? (
        <div className="bg-card border border-edge rounded-xl p-12 text-center">
          <p className="text-ink-4 text-sm">No tickets{filter ? ` with status "${filter}"` : ""}.</p>
        </div>
      ) : (
        <div className="bg-card border border-edge rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-inset text-xs text-ink-4 uppercase tracking-wider">
              <tr>
                <th className="px-4 py-2.5 text-left">Status</th>
                <th className="px-4 py-2.5 text-left">From</th>
                <th className="px-4 py-2.5 text-left">Subject</th>
                <th className="px-4 py-2.5 text-left">Date</th>
                <th className="px-4 py-2.5"></th>
              </tr>
            </thead>
            <tbody>
              {tickets.map(t => (
                <TicketRow key={t.id} ticket={t} onUpdate={handleUpdate} onDelete={handleDelete} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
