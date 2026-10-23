"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await login(email, password);
      Cookies.set("ag_token", access_token, { expires: 7, secure: true, sameSite: "strict" });
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
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
            <p className="mt-0.5 text-sm text-ink-3">Sign in to your account</p>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="bg-card rounded-xl shadow-sm border border-edge p-6 space-y-4">
          {error && <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2">{error}</p>}
          <div>
            <label className="block text-sm font-medium text-ink-2 mb-1">Email</label>
            <input
              type="email" required value={email} onChange={e => setEmail(e.target.value)}
              className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink-2 mb-1">Password</label>
            <input
              type="password" required value={password} onChange={e => setPassword(e.target.value)}
              className="w-full rounded-lg border border-edge-3 bg-card px-3 py-2 text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full bg-brand hover:bg-brand-hi disabled:opacity-50 text-white font-medium py-2 rounded-lg text-sm transition-colors"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
          <p className="text-center">
            <Link href="/forgot-password" className="text-xs text-ink-3 hover:text-brand hover:underline">Forgot password?</Link>
          </p>
        </form>
        <p className="mt-4 text-center text-sm text-ink-3">
          No account?{" "}
          <Link href="/signup" className="text-brand hover:underline font-medium">Sign up</Link>
        </p>
      </div>
    </div>
  );
}
