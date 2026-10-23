"use client";
import React, { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { getMe } from "@/lib/api";
import { useTheme } from "@/app/components/ThemeProvider";
import { DOCS_URL } from "@/lib/config";

const NAV_TOP = [
  { href: "/dashboard",           label: "Overview",  icon: GridIcon },
  { href: "/dashboard/keys",      label: "API Keys",  icon: KeyIcon },
  { href: "/dashboard/webhooks",  label: "Webhooks",  icon: WebhookIcon },
  { href: "/dashboard/team",      label: "Team",      icon: TeamIcon },
];

const NAV_PRODUCTS = [
  { href: "/dashboard/pii-vault", label: "PII Vault",  icon: ShieldIcon },
  { href: "/dashboard/eval",      label: "EvalForge",  icon: ChartIcon },
  { href: "/dashboard/guardrail", label: "Guardrail",  icon: LockIcon },
  { href: "/dashboard/docparse",  label: "DocParse",   icon: DocIcon },
];

function GridIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M4.25 2A2.25 2.25 0 002 4.25v2.5A2.25 2.25 0 004.25 9h2.5A2.25 2.25 0 009 6.75v-2.5A2.25 2.25 0 006.75 2h-2.5zm0 9A2.25 2.25 0 002 13.25v2.5A2.25 2.25 0 004.25 18h2.5A2.25 2.25 0 009 15.75v-2.5A2.25 2.25 0 006.75 11h-2.5zm6.5-9A2.25 2.25 0 008.5 4.25v2.5A2.25 2.25 0 0010.75 9h2.5A2.25 2.25 0 0015.5 6.75v-2.5A2.25 2.25 0 0013.25 2h-2.5zm0 9A2.25 2.25 0 008.5 13.25v2.5A2.25 2.25 0 0010.75 18h2.5a2.25 2.25 0 002.25-2.25v-2.5A2.25 2.25 0 0013.25 11h-2.5z" clipRule="evenodd" /></svg>;
}
function KeyIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M8 7a5 5 0 114.546 4.978L11 13.5H9.5V15h-1.5v1.5H6.5V15H5v-1.5l.022-.022A5 5 0 018 7zm1 1a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd" /></svg>;
}
function ShieldIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M9.661 2.237a.531.531 0 01.678 0 11.947 11.947 0 007.078 2.749.5.5 0 01.479.425c.069.52.104 1.05.104 1.589 0 5.162-3.26 9.563-7.834 11.256a.48.48 0 01-.332 0C5.26 16.563 2 12.162 2 7c0-.538.035-1.069.104-1.589a.5.5 0 01.48-.425 11.947 11.947 0 007.077-2.749z" clipRule="evenodd" /></svg>;
}
function ChartIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M15.5 2A1.5 1.5 0 0014 3.5v13a1.5 1.5 0 003 0v-13A1.5 1.5 0 0015.5 2zM9.5 6A1.5 1.5 0 008 7.5v9a1.5 1.5 0 003 0v-9A1.5 1.5 0 009.5 6zM3.5 10A1.5 1.5 0 002 11.5v5a1.5 1.5 0 003 0v-5A1.5 1.5 0 003.5 10z" /></svg>;
}
function LockIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M10 1a4.5 4.5 0 00-4.5 4.5V9H5a2 2 0 00-2 2v6a2 2 0 002 2h10a2 2 0 002-2v-6a2 2 0 00-2-2h-.5V5.5A4.5 4.5 0 0010 1zm3 8V5.5a3 3 0 10-6 0V9h6z" clipRule="evenodd" /></svg>;
}
function DocIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z" clipRule="evenodd" /></svg>;
}
function SupportIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-5a.75.75 0 01.75.75v4.5a.75.75 0 01-1.5 0v-4.5A.75.75 0 0110 5zm0 10a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" /></svg>;
}
function AccountIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-5.5-2.5a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0zM10 12a5.99 5.99 0 00-4.793 2.39A6.483 6.483 0 0010 16.5a6.483 6.483 0 004.793-2.11A5.99 5.99 0 0010 12z" clipRule="evenodd" /></svg>;
}
function WebhookIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M13.887 3.182c.396.037.79.08 1.183.128C16.194 3.45 17 4.414 17 5.517V16.75A2.25 2.25 0 0114.75 19h-9.5A2.25 2.25 0 013 16.75V5.517c0-1.103.806-2.068 1.93-2.207.393-.048.787-.09 1.183-.128A3.001 3.001 0 019 1h2c1.373 0 2.531.923 2.887 2.182zM7.5 4A1.5 1.5 0 019 2.5h2A1.5 1.5 0 0112.5 4v.5h-5V4z" clipRule="evenodd" /></svg>;
}
function TeamIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path d="M7 8a3 3 0 100-6 3 3 0 000 6zM14.5 9a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM1.615 16.428a1.224 1.224 0 01-.569-1.175 6.002 6.002 0 0111.908 0c.058.467-.172.92-.57 1.174A9.953 9.953 0 017 17a9.953 9.953 0 01-5.385-1.572zM14.5 16h-.106c.07-.297.088-.611.048-.933a7.47 7.47 0 00-1.588-3.755 4.502 4.502 0 015.874 2.636.818.818 0 01-.36.98A7.465 7.465 0 0114.5 16z" /></svg>;
}
function SunIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06L5.404 4.343a.75.75 0 00-1.06 1.06l1.06 1.061z" /></svg>;
}
function MoonIcon() {
  return <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M7.455 2.004a.75.75 0 01.26.77 7 7 0 009.958 7.967.75.75 0 011.067.853A8.5 8.5 0 116.647 1.921a.75.75 0 01.808.083z" clipRule="evenodd" /></svg>;
}

function NavLink({ href, label, Icon, pathname }: { href: string; label: string; Icon: () => React.ReactElement; pathname: string }) {
  const active = pathname === href;
  return (
    <Link
      href={href}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
        active
          ? "bg-brand-lo text-brand-hi"
          : "text-ink-2 hover:text-ink hover:bg-inset"
      }`}
    >
      <Icon />
      {label}
    </Link>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [email, setEmail] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { theme, toggle } = useTheme();

  useEffect(() => {
    const token = Cookies.get("ag_token");
    if (!token) { router.replace("/login"); return; }
    getMe(token).then(u => setEmail(u.email)).catch(() => {
      Cookies.remove("ag_token");
      router.replace("/login");
    });
  }, [router]);

  // Close sidebar on route change (mobile)
  useEffect(() => { setSidebarOpen(false); }, [pathname]);

  function handleLogout() {
    Cookies.remove("ag_token");
    router.push("/login");
  }

  const sidebar = (
    <nav className="flex flex-col h-full p-4 gap-1">
      <div className="px-3 py-2 mb-2 flex items-center gap-2.5">
        <svg width="28" height="28" viewBox="0 0 44 44" fill="none" aria-hidden="true">
          <rect width="44" height="44" rx="11" fill="#0c1a2e"/>
          <circle cx="22" cy="22" r="13" stroke="#0ea5e9" strokeWidth="2.5" strokeDasharray="68 14" strokeLinecap="round" transform="rotate(-30 22 22)"/>
          <circle cx="22" cy="22" r="5" fill="#0ea5e9"/>
          <circle cx="32" cy="13" r="3" fill="#d946ef"/>
        </svg>
        <span className="font-bold text-ink text-base tracking-tight">ag-tools</span>
      </div>

      {NAV_TOP.map(({ href, label, icon: Icon }) => (
        <NavLink key={href} href={href} label={label} Icon={Icon} pathname={pathname} />
      ))}

      <div className="mt-4 mb-1 px-3">
        <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider">Products</p>
      </div>

      {NAV_PRODUCTS.map(({ href, label, icon: Icon }) => (
        <NavLink key={href} href={href} label={label} Icon={Icon} pathname={pathname} />
      ))}

      <div className="mt-auto pt-4 border-t border-edge space-y-1">
        <div className="px-3 py-1.5 text-xs text-ink-4 truncate">{email}</div>
        <NavLink href="/dashboard/account" label="Account" Icon={AccountIcon} pathname={pathname} />
        <NavLink href="/dashboard/support" label="Support" Icon={SupportIcon} pathname={pathname} />
        <button
          onClick={toggle}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-ink-2 hover:text-ink hover:bg-inset transition-colors"
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-sm text-ink-2 hover:text-ink hover:bg-inset transition-colors"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 shrink-0"><path fillRule="evenodd" d="M3 4.25A2.25 2.25 0 015.25 2h5.5A2.25 2.25 0 0113 4.25v2a.75.75 0 01-1.5 0v-2a.75.75 0 00-.75-.75h-5.5a.75.75 0 00-.75.75v11.5c0 .414.336.75.75.75h5.5a.75.75 0 00.75-.75v-2a.75.75 0 011.5 0v2A2.25 2.25 0 0110.75 18h-5.5A2.25 2.25 0 013 15.75V4.25z" clipRule="evenodd" /><path fillRule="evenodd" d="M19 10a.75.75 0 00-.75-.75H8.704l1.048-1.068a.75.75 0 10-1.064-1.058l-2.5 2.5a.75.75 0 000 1.058l2.5 2.5a.75.75 0 101.064-1.058L8.704 10.75H18.25A.75.75 0 0019 10z" clipRule="evenodd" /></svg>
          Sign out
        </button>
        <div className="px-3 pt-3">
          <a href={DOCS_URL} target="_blank" rel="noopener noreferrer"
            className="text-xs text-ink-4 hover:text-ink-3 transition-colors" style={{ opacity: 0.6 }}>
            source code
          </a>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="md:h-screen flex flex-col md:flex-row md:overflow-hidden">
      {/* Desktop sidebar */}
      <aside className="hidden md:flex flex-col w-56 shrink-0 bg-card border-r border-edge overflow-y-auto">
        {sidebar}
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div className="fixed inset-0 bg-black/40" onClick={() => setSidebarOpen(false)} />
          <aside className="relative z-50 flex flex-col w-56 bg-card border-r border-edge overflow-y-auto">
            {sidebar}
          </aside>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 md:overflow-y-auto">
        {/* Mobile header — sticky */}
        <header className="md:hidden sticky top-0 z-30 bg-card border-b border-edge px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 rounded-lg text-ink-3 hover:text-ink hover:bg-inset"
          >
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5"><path fillRule="evenodd" d="M2 4.75A.75.75 0 012.75 4h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 4.75zM2 10a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75A.75.75 0 012 10zm0 5.25a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H2.75a.75.75 0 01-.75-.75z" clipRule="evenodd" /></svg>
          </button>
          <svg width="24" height="24" viewBox="0 0 44 44" fill="none" aria-hidden="true">
              <rect width="44" height="44" rx="11" fill="#0c1a2e"/>
              <circle cx="22" cy="22" r="13" stroke="#0ea5e9" strokeWidth="2.5" strokeDasharray="68 14" strokeLinecap="round" transform="rotate(-30 22 22)"/>
              <circle cx="22" cy="22" r="5" fill="#0ea5e9"/>
              <circle cx="32" cy="13" r="3" fill="#d946ef"/>
            </svg>
          <span className="font-bold text-ink">ag-tools</span>
        </header>

        <main className="flex-1 px-4 py-6 md:px-6 md:py-8 max-w-5xl w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
