"use client";

import { useEffect, useState } from "react";
import { STATUS_URL } from "@/lib/config";

/**
 * Tells the visitor when the backend is having problems, instead of leaving
 * them with a blank page or a spinner that never resolves.
 *
 * Reads the authoritative status feed rather than watching this page's own
 * requests, so it reports what is genuinely broken and needs no changes to the
 * API layer. The feed is served from Cloudflare's edge with no dependency on
 * the backend, so it is reachable exactly when the backend is not.
 *
 * If the feed itself is unreachable we render NOTHING — a status page we cannot
 * reach is not evidence of an outage, and false alarms train people to ignore
 * the banner.
 */

const STATUS_FEED = `${STATUS_URL}/api`;
const POLL_MS = 60_000;
const WATCHED = ["ag-api"];

type Target = { name: string; ok: boolean };
type Feed = { targets?: Record<string, Target> };

export default function ServiceBanner() {
  const [down, setDown] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch(STATUS_FEED, { cache: "no-store" });
        if (!res.ok) return;
        const feed: Feed = await res.json();
        const t = feed.targets || {};
        const broken = WATCHED.some((id) => t[id] && !t[id].ok);
        if (!cancelled) setDown(broken);
      } catch {
        /* unreachable feed — stay quiet */
      }
    }
    check();
    const timer = setInterval(check, POLL_MS);
    return () => { cancelled = true; clearInterval(timer); };
  }, []);

  if (!down) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        background: "#fdf3e0", color: "#7a4f00",
        borderBottom: "1px solid #e3c07a", fontSize: "0.875rem",
      }}
    >
      <div style={{ maxWidth: "72rem", margin: "0 auto", padding: "0.6rem 1rem", display: "flex", flexWrap: "wrap", gap: "0.5rem", alignItems: "center" }}>
        <span aria-hidden="true">⚠</span>
        <span><strong>Some features are unavailable.</strong> We&apos;re aware and working on it.</span>
        <a href={STATUS_URL} target="_blank" rel="noreferrer" style={{ color: "inherit", fontWeight: 600 }}>
          Live status
        </a>
      </div>
    </div>
  );
}
