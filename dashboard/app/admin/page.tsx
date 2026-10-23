"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import Cookies from "js-cookie";
import { fetchAdminStats, fetchAdminOrgs, type AdminStats, type AdminOrg } from "@/lib/admin-api";
import LimitsEditor from "@/app/components/LimitsEditor";

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-card border border-edge rounded-xl p-5">
      <p className="text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">{label}</p>
      <p className="text-2xl font-bold text-ink">{value}</p>
      {sub && <p className="text-xs text-ink-3 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [orgs, setOrgs] = useState<AdminOrg[]>([]);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const token = Cookies.get("ag_admin_token") ?? "";

  function load() {
    Promise.all([
      fetchAdminStats(token),
      fetchAdminOrgs(token),
    ])
      .then(([s, o]) => {
        setStats(s);
        setOrgs(o.orgs.slice(0, 10));
      })
      .catch(e => setError(e.message));
  }

  useEffect(load, []);

  if (error) return <p className="text-red-500 text-sm">{error}</p>;
  if (!stats) return <p className="text-ink-4 text-sm">Loading…</p>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold text-ink">Overview</h1>
        <p className="text-sm text-ink-3 mt-0.5">Platform metrics</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <StatCard label="Total users" value={stats.users.total} />
        <StatCard label="Organizations" value={stats.orgs} />
      </div>

      {/* Organizations */}
      {orgs.length > 0 && (
        <div className="bg-card border border-edge rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-edge flex items-center justify-between">
            <p className="text-sm font-semibold text-ink">Organizations ({stats.orgs})</p>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-inset text-xs text-ink-4 uppercase tracking-wider">
              <tr>
                <th className="px-5 py-2.5 text-left">Name</th>
                <th className="px-5 py-2.5 text-left">Seats</th>
                <th className="px-5 py-2.5 text-left">Created</th>
                <th className="px-5 py-2.5 text-left"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-edge">
              {orgs.map(org => (
                <React.Fragment key={org.id}>
                  <tr className="hover:bg-inset/50">
                    <td className="px-5 py-3 text-ink font-medium">{org.name}</td>
                    <td className="px-5 py-3 text-ink-3">{org.seats_used} / {org.seat_limit}</td>
                    <td className="px-5 py-3 text-ink-4">{org.created_at ? new Date(org.created_at).toLocaleDateString() : "—"}</td>
                    <td className="px-5 py-3 text-right">
                      <button onClick={() => setEditing(editing === org.id ? null : org.id)} className="text-xs text-brand hover:underline">
                        {editing === org.id ? "Close" : "Limits"}
                      </button>
                    </td>
                  </tr>
                  {editing === org.id && (
                    <tr>
                      <td colSpan={4} className="px-5 py-4 bg-inset/40">
                        <LimitsEditor token={token} kind="orgs" id={org.id} limits={org.limits} seatLimit={org.seat_limit} onSaved={load} />
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex gap-3">
        <Link
          href="/admin/users"
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold"
        >
          Manage users →
        </Link>
      </div>
    </div>
  );
}
