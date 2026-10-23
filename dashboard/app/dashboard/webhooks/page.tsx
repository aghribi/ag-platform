"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { listWebhooks, createWebhook, deleteWebhook, type WebhookEndpoint } from "@/lib/api";

const ALL_EVENTS = [
  { value: "docparse.completed", label: "DocParse completed", desc: "Async parse job finished successfully" },
  { value: "docparse.failed",    label: "DocParse failed",    desc: "Async parse job failed" },
  { value: "guardrail.blocked",  label: "Guardrail blocked",  desc: "A check was blocked by a rule or policy" },
  { value: "quota.warning",      label: "Quota warning",      desc: "80% or 95% of monthly quota used" },
];

export default function WebhooksPage() {
  const router = useRouter();
  const [endpoints, setEndpoints] = useState<WebhookEndpoint[]>([]);
  const [newUrl, setNewUrl] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  function token() {
    const t = Cookies.get("ag_token");
    if (!t) { router.replace("/login"); throw new Error("no token"); }
    return t;
  }

  useEffect(() => {
    listWebhooks(token()).then(setEndpoints).catch(() => router.replace("/login"));
  }, []);

  function toggleEvent(ev: string) {
    setSelectedEvents(prev =>
      prev.includes(ev) ? prev.filter(e => e !== ev) : [...prev, ev]
    );
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newUrl || selectedEvents.length === 0) return;
    setCreating(true); setError(""); setNewSecret(null);
    try {
      const created = await createWebhook(token(), newUrl, selectedEvents);
      setNewSecret(created.secret);
      setNewUrl(""); setSelectedEvents([]);
      setEndpoints(await listWebhooks(token()));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("Remove this webhook endpoint?")) return;
    try {
      await deleteWebhook(token(), id);
      setEndpoints(prev => prev.filter(e => e.id !== id));
    } catch {
      setError("Failed to remove endpoint");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-ink">Webhooks</h1>
        <p className="mt-1 text-sm text-ink-3">
          Receive real-time HTTP POST notifications when events occur in your account.
        </p>
      </div>

      {newSecret && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
          <p className="text-sm font-medium text-amber-800 mb-2">
            Webhook created — copy the signing secret now, it won&apos;t be shown again.
            Use it to verify <code className="font-mono text-xs">X-AG-Signature</code> headers.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-white border border-amber-200 rounded-lg px-3 py-2 font-mono break-all">
              {newSecret}
            </code>
            <button
              onClick={() => navigator.clipboard.writeText(newSecret)}
              className="text-xs bg-amber-100 hover:bg-amber-200 text-amber-800 px-3 py-2 rounded-lg font-medium"
            >Copy</button>
          </div>
          <button onClick={() => setNewSecret(null)} className="mt-2 text-xs text-amber-600 hover:underline">Dismiss</button>
        </div>
      )}

      <form onSubmit={handleCreate} className="bg-card rounded-xl border border-edge p-5 space-y-4">
        <h2 className="text-sm font-semibold text-ink">Add endpoint</h2>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <input
          type="url"
          placeholder="https://your-server.com/webhook"
          value={newUrl}
          onChange={e => setNewUrl(e.target.value)}
          required
          className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <div>
          <p className="text-xs font-medium text-ink-3 mb-2">Events to subscribe</p>
          <div className="space-y-2">
            {ALL_EVENTS.map(ev => (
              <label key={ev.value} className="flex items-start gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={selectedEvents.includes(ev.value)}
                  onChange={() => toggleEvent(ev.value)}
                  className="mt-0.5 accent-sky-600"
                />
                <div>
                  <p className="text-sm text-ink font-medium">{ev.label}</p>
                  <p className="text-xs text-ink-4">{ev.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>
        <button
          type="submit"
          disabled={creating || !newUrl || selectedEvents.length === 0}
          className="bg-brand hover:bg-brand-hi disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
        >
          {creating ? "Creating…" : "Add endpoint"}
        </button>
      </form>

      <div className="bg-card rounded-xl border border-edge divide-y divide-edge-2">
        {endpoints.length === 0 && (
          <p className="text-sm text-ink-4 text-center py-8">No webhook endpoints configured</p>
        )}
        {endpoints.map(ep => (
          <div key={ep.id} className="px-5 py-4 flex items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="text-sm font-medium text-ink truncate">{ep.url}</p>
              <div className="flex flex-wrap gap-1 mt-1.5">
                {ep.events.map(ev => (
                  <span key={ev} className="text-xs bg-sky-50 text-sky-700 border border-sky-200 px-1.5 py-0.5 rounded-md">
                    {ev}
                  </span>
                ))}
              </div>
              <p className="text-xs text-ink-4 mt-1">Added {new Date(ep.created_at).toLocaleDateString()}</p>
            </div>
            <button
              onClick={() => handleDelete(ep.id)}
              className="shrink-0 text-xs text-red-500 hover:text-red-700 hover:underline"
            >
              Remove
            </button>
          </div>
        ))}
      </div>

      <div className="bg-card rounded-xl border border-edge p-5">
        <h2 className="text-sm font-semibold text-ink mb-3">Payload format</h2>
        <pre className="text-xs bg-inset rounded-lg p-4 overflow-x-auto text-ink-2">{`POST https://your-server.com/webhook
Content-Type: application/json
X-AG-Signature: sha256=<hmac-hex>

{
  "event": "docparse.completed",
  "timestamp": "2026-05-17T10:00:00Z",
  "data": { ... }
}`}</pre>
        <p className="text-xs text-ink-4 mt-3">
          Verify the signature: <code className="font-mono">HMAC-SHA256(secret, raw_body_bytes)</code>
        </p>
      </div>
    </div>
  );
}
