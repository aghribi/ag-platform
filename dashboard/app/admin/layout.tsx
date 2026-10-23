"use client";
import React, { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { useTheme } from "@/app/components/ThemeProvider";
import { API_URL } from "@/lib/config";

const NAV = [
  { href: "/admin",          label: "Overview" },
  { href: "/admin/users",    label: "Users" },
  { href: "/admin/metrics",  label: "Metrics" },
  { href: "/admin/tickets",  label: "Tickets",  badgeKey: "tickets" },
  { href: "/admin/compose",  label: "Compose" },
];

function SunIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06L5.404 4.343a.75.75 0 00-1.06 1.06l1.06 1.061z" /></svg>;
}
function MoonIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M7.455 2.004a.75.75 0 01.26.77 7 7 0 009.958 7.967.75.75 0 011.067.853A8.5 8.5 0 116.647 1.921a.75.75 0 01.808.083z" clipRule="evenodd" /></svg>;
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [openTickets, setOpenTickets] = useState<number | null>(null);
  const { theme, toggle } = useTheme();

  useEffect(() => {
    const token = Cookies.get("ag_admin_token");
    if (!token && pathname !== "/admin/login") {
      router.replace("/admin/login");
      return;
    }
    if (token && pathname !== "/admin/login") {
      const API = API_URL;
      fetch(`${API}/admin/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => {
        if (r.status === 401 || r.status === 403) {
          Cookies.remove("ag_admin_token");
          router.replace("/admin/login");
        } else {
          setReady(true);
        }
      }).catch(() => setReady(true));
      fetch(`${API}/admin/tickets?status=open`, {
        headers: { Authorization: `Bearer ${token}` },
      }).then(r => r.ok ? r.json() : null).then(d => {
        if (d) setOpenTickets(d.open ?? d.total ?? 0);
      }).catch(() => {});
    } else {
      setReady(true);
    }
  }, [router, pathname]);

  if (!ready) return null;

  if (pathname === "/admin/login") return <>{children}</>;

  function handleLogout() {
    Cookies.remove("ag_admin_token");
    router.push("/admin/login");
  }

  return (
    <div className="md:h-screen flex flex-col md:flex-row md:overflow-hidden">
      <aside className="hidden md:flex flex-col w-48 shrink-0 bg-card border-r border-edge overflow-y-auto">
        <nav className="flex flex-col h-full p-4 gap-1">
          <div className="px-3 py-2 mb-3">
            <p className="text-xs font-bold text-ink-4 uppercase tracking-widest">Admin</p>
            <p className="text-base font-bold text-ink">ag-tools</p>
          </div>

          {NAV.map(({ href, label, badgeKey }) => {
            const active = pathname === href;
            const badge = badgeKey === "tickets" && openTickets ? openTickets : 0;
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  active ? "bg-brand-lo text-brand-hi" : "text-ink-2 hover:text-ink hover:bg-inset"
                }`}
              >
                {label}
                {badge > 0 && (
                  <span className="ml-auto text-xs font-semibold bg-red-500 text-white rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1">
                    {badge}
                  </span>
                )}
              </Link>
            );
          })}

          <div className="mt-auto pt-4 border-t border-edge space-y-1">
            <button
              onClick={toggle}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-ink-2 hover:text-ink hover:bg-inset transition-colors"
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
              {theme === "dark" ? "Light mode" : "Dark mode"}
            </button>
            <button
              onClick={handleLogout}
              className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm text-ink-2 hover:text-ink hover:bg-inset transition-colors"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0">
                <path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z" clipRule="evenodd" />
                <path fillRule="evenodd" d="M19 10a.75.75 0 00-.75-.75H8.704l1.048-1.068a.75.75 0 10-1.064-1.058l-2.5 2.5a.75.75 0 000 1.058l2.5 2.5a.75.75 0 101.064-1.058L8.704 10.75H18.25A.75.75 0 0019 10z" clipRule="evenodd" />
              </svg>
              Sign out
            </button>
          </div>
        </nav>
      </aside>

      <div className="flex-1 flex flex-col min-w-0 md:overflow-y-auto">
        <main className="flex-1 px-4 py-6 md:px-8 md:py-8 max-w-6xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
