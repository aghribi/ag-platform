"use client";
import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import {
  adminAuthStatus,
  adminLoginBegin,
  adminLoginComplete,
  adminRegisterBegin,
  adminRegisterComplete,
} from "@/lib/admin-api";

// ── WebAuthn helpers ───────────────────────────────────────────────────────────

function b64urlToBuffer(b64: string): ArrayBuffer {
  const padded = b64.replace(/-/g, "+").replace(/_/g, "/").padEnd(b64.length + (4 - (b64.length % 4)) % 4, "=");
  const binary = atob(padded);
  const buf = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) buf[i] = binary.charCodeAt(i);
  return buf.buffer;
}

function bufferToB64url(buf: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(buf)))
    .replace(/\+/g, "-").replace(/\//g, "_").replace(/=/g, "");
}

function encodeCredential(cred: PublicKeyCredential) {
  const response = cred.response as AuthenticatorAttestationResponse | AuthenticatorAssertionResponse;
  const base: Record<string, unknown> = {
    id: cred.id,
    rawId: bufferToB64url(cred.rawId),
    type: cred.type,
  };

  if ("attestationObject" in response) {
    // Registration
    base.response = {
      clientDataJSON: bufferToB64url(response.clientDataJSON),
      attestationObject: bufferToB64url((response as AuthenticatorAttestationResponse).attestationObject),
    };
  } else {
    // Authentication
    const ar = response as AuthenticatorAssertionResponse;
    base.response = {
      clientDataJSON: bufferToB64url(ar.clientDataJSON),
      authenticatorData: bufferToB64url(ar.authenticatorData),
      signature: bufferToB64url(ar.signature),
      userHandle: ar.userHandle ? bufferToB64url(ar.userHandle) : null,
    };
  }
  return base;
}

// ── Page ───────────────────────────────────────────────────────────────────────

export default function AdminLoginPage() {
  const router = useRouter();
  const [registered, setRegistered] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [adminToken, setAdminToken] = useState("");
  const [passkeyLabel, setPasskeyLabel] = useState("MacBook Touch ID");
  const [mode, setMode] = useState<"login" | "setup">("login");

  useEffect(() => {
    const existing = Cookies.get("ag_admin_token");
    if (existing) { router.replace("/admin"); return; }

    adminAuthStatus()
      .then(s => setRegistered(s.registered))
      .catch(() => setRegistered(false));
  }, [router]);

  async function handleLogin() {
    setError("");
    setLoading(true);
    try {
      const options = await adminLoginBegin();

      const publicKey: PublicKeyCredentialRequestOptions = {
        challenge: b64urlToBuffer(options.challenge as string),
        timeout: options.timeout as number | undefined,
        rpId: options.rpId as string | undefined,
        userVerification: options.userVerification as UserVerificationRequirement | undefined,
        allowCredentials: ((options.allowCredentials as Array<Record<string, unknown>>) ?? []).map(c => ({
          type: c.type as PublicKeyCredentialType,
          id: b64urlToBuffer(c.id as string),
        })),
      };

      const cred = await navigator.credentials.get({ publicKey }) as PublicKeyCredential | null;
      if (!cred) throw new Error("Passkey prompt was cancelled");

      const { session_token } = await adminLoginComplete(encodeCredential(cred));
      Cookies.set("ag_admin_token", session_token, { expires: 1 / 3, sameSite: "strict" });
      router.replace("/admin");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister() {
    if (!adminToken.trim()) { setError("Enter your ADMIN_TOKEN first"); return; }
    setError("");
    setLoading(true);
    try {
      const options = await adminRegisterBegin(adminToken);

      const rawUser = options.user as Record<string, unknown>;
      const rawRp = options.rp as Record<string, unknown>;
      const publicKey: PublicKeyCredentialCreationOptions = {
        challenge: b64urlToBuffer(options.challenge as string),
        timeout: options.timeout as number | undefined,
        rp: { id: rawRp.id as string | undefined, name: rawRp.name as string },
        user: {
          id: b64urlToBuffer(rawUser.id as string),
          name: rawUser.name as string,
          displayName: rawUser.displayName as string,
        },
        pubKeyCredParams: options.pubKeyCredParams as PublicKeyCredentialParameters[],
        authenticatorSelection: options.authenticatorSelection as AuthenticatorSelectionCriteria | undefined,
        excludeCredentials: ((options.excludeCredentials as Array<Record<string, unknown>>) ?? []).map(c => ({
          type: c.type as PublicKeyCredentialType,
          id: b64urlToBuffer(c.id as string),
        })),
      };

      const cred = await navigator.credentials.create({ publicKey }) as PublicKeyCredential | null;
      if (!cred) throw new Error("Passkey creation was cancelled");

      await adminRegisterComplete(encodeCredential(cred), adminToken, passkeyLabel);
      setRegistered(true);
      setMode("login");
      setError("");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  if (registered === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg">
        <p className="text-ink-4 text-sm">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm bg-card border border-edge rounded-2xl p-8 shadow-sm">
        <div className="mb-6 text-center">
          <p className="text-xs font-bold text-ink-4 uppercase tracking-widest mb-1">Admin Panel</p>
          <h1 className="text-xl font-bold text-ink">ag-tools</h1>
        </div>

        {!registered || mode === "setup" ? (
          <div className="space-y-4">
            <p className="text-sm text-ink-3 text-center">
              {registered ? "Register an additional passkey" : "No passkey registered yet. Enter your ADMIN_TOKEN to set one up."}
            </p>
            <input
              type="password"
              placeholder="ADMIN_TOKEN"
              value={adminToken}
              onChange={e => setAdminToken(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <input
              type="text"
              placeholder="Passkey label (e.g. MacBook Touch ID)"
              value={passkeyLabel}
              onChange={e => setPasskeyLabel(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink placeholder:text-ink-4 focus:outline-none focus:ring-2 focus:ring-brand"
            />
            <button
              onClick={handleRegister}
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-50"
            >
              {loading ? "Registering…" : "Register passkey"}
            </button>
            {registered && (
              <button
                onClick={() => { setMode("login"); setError(""); }}
                className="w-full py-2 rounded-lg text-sm text-ink-3 hover:text-ink"
              >
                Back to login
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-ink-3 text-center">
              Sign in with your registered passkey to access the admin panel.
            </p>
            <button
              onClick={handleLogin}
              disabled={loading}
              className="w-full py-2.5 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M8 7a5 5 0 114.546 4.978L11 13.5H9.5V15h-1.5v1.5H6.5V15H5v-1.5l.022-.022A5 5 0 018 7zm1 1a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" />
              </svg>
              {loading ? "Waiting for passkey…" : "Sign in with passkey"}
            </button>
            <button
              onClick={() => { setMode("setup"); setError(""); }}
              className="w-full py-2 rounded-lg text-sm text-ink-3 hover:text-ink"
            >
              Register a new passkey
            </button>
          </div>
        )}

        {error && (
          <p className="mt-4 text-xs text-red-500 text-center">{error}</p>
        )}
      </div>
    </div>
  );
}
