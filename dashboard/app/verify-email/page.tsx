"use client";
import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { verifyEmail } from "@/lib/api";

function VerifyEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get("token") ?? "";

  const [status, setStatus] = useState<"verifying" | "success" | "error">("verifying");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setErrorMsg("Missing verification token. Please use the link from your email.");
      return;
    }
    verifyEmail(token)
      .then(({ access_token }) => {
        Cookies.set("ag_token", access_token, { expires: 7, secure: true, sameSite: "strict" });
        setStatus("success");
        setTimeout(() => router.push("/dashboard"), 2000);
      })
      .catch((err: unknown) => {
        setStatus("error");
        setErrorMsg(err instanceof Error ? err.message : "Verification failed. The link may have expired.");
      });
  }, [token, router]);

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
          <span className="text-xl font-bold text-ink tracking-tight">ag-tools</span>
        </div>

        <div className="bg-card rounded-xl shadow-sm border border-edge p-6 text-center space-y-3">
          {status === "verifying" && (
            <>
              <div className="text-3xl animate-pulse">⏳</div>
              <p className="font-semibold text-ink">Verifying your email…</p>
            </>
          )}
          {status === "success" && (
            <>
              <div className="text-3xl">✅</div>
              <p className="font-semibold text-ink">Email confirmed!</p>
              <p className="text-sm text-ink-3">Redirecting to your dashboard…</p>
            </>
          )}
          {status === "error" && (
            <>
              <div className="text-3xl">❌</div>
              <p className="font-semibold text-ink">Verification failed</p>
              <p className="text-sm text-red-600">{errorMsg}</p>
              <Link href="/signup" className="block text-sm text-brand hover:underline font-medium pt-2">
                Sign up again
              </Link>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  );
}
