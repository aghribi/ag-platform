"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { acceptInvite, login, signup } from "@/lib/api";

export default function JoinPage() {
  const { token } = useParams<{ token: string }>();
  const router = useRouter();
  const [step, setStep] = useState<"loading" | "auth" | "verify" | "accepting" | "done" | "error">("loading");
  const [mode, setMode] = useState<"login" | "signup">("signup");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const existing = Cookies.get("ag_token");
    if (existing) {
      acceptToken(existing);
    } else {
      setStep("auth");
    }
  }, []);

  async function acceptToken(jwt: string) {
    setStep("accepting");
    try {
      await acceptInvite(jwt, token);
      setStep("done");
      setTimeout(() => router.push("/dashboard/team"), 2000);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to accept invite");
      setStep("error");
    }
  }

  async function handleAuth() {
    setError("");
    try {
      if (mode === "signup") {
        await signup(email, password);
        setStep("verify");
        return;
      }
      const r = await login(email, password);
      const jwt = r.access_token;
      Cookies.set("ag_token", jwt, { expires: 7 });
      await acceptToken(jwt);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Authentication failed");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md bg-surface border border-border rounded-2xl p-8 space-y-6">
        <div className="text-center">
          <span className="text-3xl">🤝</span>
          <h1 className="text-xl font-semibold text-ink-1 mt-3">Join your team on ag-tools</h1>
        </div>

        {step === "loading" && (
          <p className="text-center text-ink-3 text-sm">Checking…</p>
        )}

        {step === "auth" && (
          <div className="space-y-4">
            <p className="text-sm text-ink-3 text-center">
              {mode === "signup" ? "Create an ag-tools account to accept this invitation." : "Log in to accept this invitation."}
            </p>

            {error && <p className="text-red-500 text-sm text-center">{error}</p>}

            <input
              className="w-full border border-border rounded-lg px-3 py-2.5 text-sm bg-background"
              placeholder="Email"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
            />
            <input
              className="w-full border border-border rounded-lg px-3 py-2.5 text-sm bg-background"
              placeholder="Password"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleAuth()}
            />
            <button
              onClick={handleAuth}
              className="w-full bg-brand text-white py-2.5 rounded-lg text-sm font-medium hover:bg-brand-hi"
            >
              {mode === "signup" ? "Create account & join team" : "Log in & join team"}
            </button>
            <p className="text-center text-xs text-ink-4">
              {mode === "signup" ? "Already have an account?" : "New to ag-tools?"}{" "}
              <button
                onClick={() => setMode(mode === "signup" ? "login" : "signup")}
                className="text-brand hover:underline"
              >
                {mode === "signup" ? "Log in" : "Sign up"}
              </button>
            </p>
          </div>
        )}

        {step === "verify" && (
          <div className="text-center space-y-3">
            <div className="text-3xl">✉️</div>
            <p className="font-semibold text-ink">Check your email</p>
            <p className="text-sm text-ink-3">
              We sent a confirmation link to <span className="font-medium text-ink">{email}</span>.
              Confirm your email, then return to this page and log in to accept the invitation.
            </p>
            <button onClick={() => { setMode("login"); setStep("auth"); }} className="text-sm text-brand hover:underline font-medium pt-2 block mx-auto">
              I&apos;ve confirmed — log in
            </button>
          </div>
        )}

        {step === "accepting" && (
          <p className="text-center text-ink-3 text-sm">Joining team…</p>
        )}

        {step === "done" && (
          <div className="text-center space-y-2">
            <p className="text-green-600 font-medium">You've joined the team!</p>
            <p className="text-sm text-ink-3">Redirecting to your team dashboard…</p>
          </div>
        )}

        {step === "error" && (
          <div className="text-center space-y-3">
            <p className="text-red-500 text-sm">{error}</p>
            <button
              onClick={() => router.push("/dashboard")}
              className="text-sm text-brand hover:underline"
            >
              Go to dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
