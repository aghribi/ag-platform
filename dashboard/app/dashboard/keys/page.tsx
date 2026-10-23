"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { listKeys, createKey, revokeKey } from "@/lib/api";

type Key = {
  id: string; name: string; prefix: string; is_active: boolean;
  scope: string | null; expires_at: string | null;
  last_used_at: string | null; created_at: string;
};

const SCOPES = [
  { value: "", label: "All products" },
  { value: "pii-vault", label: "PII Vault only" },
  { value: "eval",      label: "EvalForge only" },
  { value: "guardrail", label: "Guardrail only" },
  { value: "docparse",  label: "DocParse only" },
];

const EXPIRY_OPTIONS = [
  { value: "",    label: "Never expires" },
  { value: "30",  label: "30 days" },
  { value: "90",  label: "90 days" },
  { value: "365", label: "1 year" },
];

export default function KeysPage() {
  const router = useRouter();
  const [keys, setKeys] = useState<Key[]>([]);
  const [newName, setNewName] = useState("");
  const [newScope, setNewScope] = useState("");
  const [newExpiry, setNewExpiry] = useState("");
  const [newKey, setNewKey] = useState<{ key: string; name: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function token() {
    const t = Cookies.get("ag_token");
    if (!t) { router.replace("/login"); throw new Error("no token"); }
    return t;
  }

  useEffect(() => {
    listKeys(token()).then(setKeys).catch(() => router.replace("/login"));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!newName.trim()) return;
    setLoading(true); setError("");
    try {
      const created = await createKey(
        token(),
        newName.trim(),
        newScope || null,
        newExpiry ? parseInt(newExpiry) : null,
      );
      setNewKey({ key: created.key, name: created.name });
      setNewName(""); setNewScope(""); setNewExpiry("");
      setKeys(await listKeys(token()));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleRevoke(id: string) {
    if (!confirm("Revoke this key? This cannot be undone.")) return;
    try {
      await revokeKey(token(), id);
      setKeys(k => k.filter(x => x.id !== id));
    } catch {
      setError("Failed to revoke key");
    }
  }

  function scopeLabel(scope: string | null) {
    if (!scope) return null;
    return SCOPES.find(s => s.value === scope)?.label ?? scope;
  }

  function expiryLabel(expires_at: string | null) {
    if (!expires_at) return null;
    const d = new Date(expires_at);
    const now = new Date();
    if (d < now) return "Expired";
    return `Expires ${d.toLocaleDateString()}`;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{background:"rgba(14,165,233,0.1)",border:"1px solid rgba(14,165,233,0.2)"}}>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="#0ea5e9"><path fillRule="evenodd" d="M8 7a5 5 0 114.546 4.978L11 13.5H9.5V15h-1.5v1.5H6.5V15H5v-1.5l.022-.022A5 5 0 018 7zm1 1a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd"/></svg>
        </div>
        <div>
          <h1 className="text-2xl font-bold text-ink">API Keys</h1>
          <p className="mt-0.5 text-sm text-ink-3">Use these keys to authenticate SDK calls from your application.</p>
        </div>
      </div>

      {newKey && (
        <div className="bg-inset border border-edge-3 rounded-xl p-4">
          <p className="text-sm font-medium text-ink-2 mb-2">Key created — copy it now, it won&apos;t be shown again.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 text-xs bg-card text-ink border border-edge-3 rounded-lg px-3 py-2 font-mono break-all">{newKey.key}</code>
            <button
              onClick={() => { navigator.clipboard.writeText(newKey.key); }}
              className="text-xs bg-brand-lo hover:bg-edge-3 text-ink-2 px-3 py-2 rounded-lg font-medium"
            >Copy</button>
          </div>
          <button onClick={() => setNewKey(null)} className="mt-2 text-xs text-ink-3 hover:underline">Dismiss</button>
        </div>
      )}

      <form onSubmit={handleCreate} className="bg-card rounded-xl border border-edge p-5 space-y-3">
        <h2 className="text-sm font-semibold text-ink">Create new key</h2>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <input
          type="text" placeholder="Key name (e.g. production)" value={newName}
          onChange={e => setNewName(e.target.value)} required maxLength={64}
          className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
        />
        <div className="flex flex-wrap gap-3">
          <select
            value={newScope}
            onChange={e => setNewScope(e.target.value)}
            className="flex-1 rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {SCOPES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          <select
            value={newExpiry}
            onChange={e => setNewExpiry(e.target.value)}
            className="flex-1 rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {EXPIRY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <button
            type="submit" disabled={loading}
            className="bg-brand hover:bg-brand-hi disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm font-medium"
          >
            {loading ? "Creating…" : "Create"}
          </button>
        </div>
      </form>

      <div className="bg-card rounded-xl border border-edge divide-y divide-edge-2">
        {keys.length === 0 && (
          <p className="text-sm text-ink-4 text-center py-8">No keys yet</p>
        )}
        {keys.map(k => (
          <div key={k.id} className="flex items-center justify-between gap-3 px-5 py-4 min-w-0">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-ink">{k.name}</p>
                {k.scope && (
                  <span className="text-xs bg-sky-50 text-sky-700 border border-sky-200 px-1.5 py-0.5 rounded-md">
                    {scopeLabel(k.scope)}
                  </span>
                )}
              </div>
              <p className="text-xs text-ink-4 font-mono mt-0.5">{k.prefix}••••••••</p>
              <div className="flex gap-3 mt-0.5">
                {k.last_used_at && (
                  <p className="text-xs text-ink-4">Last used {new Date(k.last_used_at).toLocaleDateString()}</p>
                )}
                {k.expires_at && (
                  <p className={`text-xs ${new Date(k.expires_at) < new Date() ? "text-red-500" : "text-ink-4"}`}>
                    {expiryLabel(k.expires_at)}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => handleRevoke(k.id)}
              className="text-xs text-red-500 hover:text-red-700 hover:underline"
            >
              Revoke
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
