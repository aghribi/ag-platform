"use client";
import { useState, useEffect, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import { confirmPasswordReset } from "@/lib/api";

function ResetPasswordForm() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!token) setError("Missing or invalid reset link.");
  }, [token]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) { setError("Password must be at least 8 characters."); return; }
    if (password !== confirm) { setError("Passwords do not match."); return; }
    setLoading(true);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
      setTimeout(() => router.push("/login"), 2500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Reset failed. The link may have expired.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center flex flex-col items-center gap-3">
          <svg width="44" height="44" viewBox="0 0 44 44" fill="none" aria-label="ag-tools">
            <rect width="44" height="44" rx="11" fill="#0c1a2e"/>
            <circle cx="22" cy="22" r="13" stroke="#0ea5e9" strokeWidth="2.5" strokeDasharray="68 14" strokeLinecap="round" transform="rotate(-30 22 22)"/>
            <circle cx="22" cy="22" r="5" fill="#0ea5e9"/>
            <circle cx="32" cy="13" r="3" fill="#d946ef"/>
          </svg>
          <div>
            <h1 className="text-xl font-bold text-ink tracking-tight">ag-tools</h1>
            <p className="mt-0.5 text-sm text-ink-3">Choose a new password</p>
          </div>
        </div>
        <div className="bg-card rounded-xl shadow-sm border border-edge p-6">
          {done ? (
            <p className="text-sm text-green-700 bg-green-50 rounded-lg px-3 py-3 text-center">
              Password updated. Redirecting to sign in…
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
              <div>
                <label className="block text-sm font-medium text-ink-2 mb-1">New password</label>
                <input
                  type="password" required value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-ink-2 mb-1">Confirm password</label>
                <input
                  type="password" required value={confirm} onChange={e => setConfirm(e.target.value)}
                  className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
                />
              </div>
              <button
                type="submit" disabled={loading || !token}
                className="w-full bg-brand hover:bg-brand-hi disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
              >
                {loading ? "Updating…" : "Set new password"}
              </button>
            </form>
          )}
        </div>
        <p className="mt-4 text-center text-sm text-ink-3">
          <Link href="/login" className="text-brand hover:underline font-medium">Back to sign in</Link>
        </p>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
