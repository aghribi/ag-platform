"use client";
import React, { useEffect, useState } from "react";
import Cookies from "js-cookie";
import {
  getMe,
  downloadUsageCsv,
  changePassword,
  deleteVaultData,
  deleteAccount,
} from "@/lib/api";
import { CONTACT_EMAIL } from "@/lib/config";
import { useRouter } from "next/navigation";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-edge rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-edge">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
      </div>
      <div className="px-6 py-5 space-y-4">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-ink-3 shrink-0">{label}</span>
      <div className="text-sm text-ink text-right">{children}</div>
    </div>
  );
}

export default function AccountPage() {
  const router = useRouter();
  const token = Cookies.get("ag_token") ?? "";

  const [user, setUser] = useState<{ id: string; email: string; monthly_period: string | null } | null>(null);

  // Password change state
  const [currentPw, setCurrentPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [pwSaving, setPwSaving] = useState(false);
  const [pwMsg, setPwMsg] = useState<{ ok: boolean; text: string } | null>(null);

  // Clear vault modal
  const [vaultModal, setVaultModal] = useState(false);
  const [vaultEmail, setVaultEmail] = useState("");
  const [vaultLoading, setVaultLoading] = useState(false);
  const [vaultError, setVaultError] = useState("");

  // Data export state
  const [exportLoading, setExportLoading] = useState(false);
  const [exportError, setExportError] = useState("");

  // Delete account modal
  const [deleteModal, setDeleteModal] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  useEffect(() => {
    if (!token) { router.replace("/login"); return; }
    getMe(token).then(setUser).catch(() => {
      Cookies.remove("ag_token");
      router.replace("/login");
    });
  }, [token, router]);

  async function handlePasswordChange() {
    if (!newPw || newPw.length < 8) {
      setPwMsg({ ok: false, text: "New password must be at least 8 characters." });
      return;
    }
    setPwSaving(true);
    setPwMsg(null);
    try {
      await changePassword(token, currentPw, newPw);
      setPwMsg({ ok: true, text: "Password updated successfully." });
      setCurrentPw("");
      setNewPw("");
    } catch (e: unknown) {
      setPwMsg({ ok: false, text: e instanceof Error ? e.message : "Failed to change password." });
    } finally {
      setPwSaving(false);
    }
  }

  async function handleClearVault() {
    if (!user || vaultEmail !== user.email) {
      setVaultError("Email does not match.");
      return;
    }
    setVaultLoading(true);
    setVaultError("");
    try {
      await deleteVaultData(token);
      setVaultModal(false);
      setVaultEmail("");
    } catch (e: unknown) {
      setVaultError(e instanceof Error ? e.message : "Failed to clear vault.");
    } finally {
      setVaultLoading(false);
    }
  }

  async function handleDeleteAccount() {
    if (deleteConfirm !== "DELETE") {
      setDeleteError('Type "DELETE" to confirm.');
      return;
    }
    setDeleteLoading(true);
    setDeleteError("");
    try {
      await deleteAccount(token);
      Cookies.remove("ag_token");
      router.replace("/login");
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : "Failed to delete account.");
      setDeleteLoading(false);
    }
  }

  if (!user) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="w-5 h-5 border-2 border-brand border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-ink">Account</h1>
        <p className="text-sm text-ink-3 mt-0.5">Manage your profile and data.</p>
      </div>

      {/* Account info */}
      <Section title="Account information">
        <Row label="Email">
          <span className="font-medium">{user.email}</span>
        </Row>
        {user.monthly_period && (
          <Row label="Usage period">
            <span className="text-ink-3">{user.monthly_period}</span>
          </Row>
        )}
      </Section>

      {/* Limits */}
      <Section title="Usage limits">
        <p className="text-sm text-ink-3">
          Each account has monthly limits per product, shown on each product page.
          To request a higher limit, write to{" "}
          <a href={`mailto:${CONTACT_EMAIL}`} className="text-brand hover:underline">{CONTACT_EMAIL}</a>.
        </p>
      </Section>

      {/* Password change */}
      <Section title="Change password">
        <div className="space-y-3">
          <div>
            <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">Current password</label>
            <input
              type="password"
              value={currentPw}
              onChange={e => setCurrentPw(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand"
              placeholder="••••••••"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">New password</label>
            <input
              type="password"
              value={newPw}
              onChange={e => setNewPw(e.target.value)}
              className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-2 focus:ring-brand"
              placeholder="Min. 8 characters"
            />
          </div>
          {pwMsg && (
            <p className={`text-xs ${pwMsg.ok ? "text-green-500" : "text-red-500"}`}>{pwMsg.text}</p>
          )}
          <button
            onClick={handlePasswordChange}
            disabled={pwSaving || !currentPw || !newPw}
            className="px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-40"
          >
            {pwSaving ? "Saving…" : "Update password"}
          </button>
        </div>
      </Section>

      {/* Data export */}
      <Section title="Export your data">
        <p className="text-sm text-ink-3">Download your full usage history as a CSV file (up to 10,000 recent events).</p>
        {exportError && <p className="text-xs text-red-500">{exportError}</p>}
        <button
          onClick={async () => {
            setExportLoading(true);
            setExportError("");
            try { await downloadUsageCsv(token); }
            catch (e: unknown) { setExportError(e instanceof Error ? e.message : "Export failed."); }
            finally { setExportLoading(false); }
          }}
          disabled={exportLoading}
          className="inline-block px-4 py-2 rounded-lg border border-edge text-sm text-ink-2 hover:border-brand hover:text-brand transition-colors disabled:opacity-40"
        >
          {exportLoading ? "Preparing…" : "Download usage CSV"}
        </button>
      </Section>

      {/* Danger zone */}
      <div className="bg-card border border-red-500/30 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-red-500/20">
          <h2 className="text-sm font-semibold text-red-500">Danger zone</h2>
        </div>
        <div className="px-6 py-5 space-y-5">
          {/* Clear vault */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink">Clear vault data</p>
              <p className="text-xs text-ink-3 mt-0.5">Permanently delete all PII entries stored in your vault. This resets your vault quota. Irreversible.</p>
            </div>
            <button
              onClick={() => { setVaultModal(true); setVaultEmail(""); setVaultError(""); }}
              className="shrink-0 px-3 py-1.5 rounded-lg border border-red-500/40 text-red-500 text-xs font-semibold hover:bg-red-500/10 transition-colors"
            >
              Clear vault
            </button>
          </div>

          <div className="border-t border-edge" />

          {/* Delete account */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-medium text-ink">Delete account</p>
              <p className="text-xs text-ink-3 mt-0.5">
                Permanently delete your account and all associated data including vault entries, API keys, and usage logs.
                {" "}This action cannot be undone.
              </p>
            </div>
            <button
              onClick={() => { setDeleteModal(true); setDeleteConfirm(""); setDeleteError(""); }}
              className="shrink-0 px-3 py-1.5 rounded-lg bg-red-500/10 border border-red-500/40 text-red-500 text-xs font-semibold hover:bg-red-500/20 transition-colors"
            >
              Delete account
            </button>
          </div>
        </div>
      </div>

      {/* Clear vault modal */}
      {vaultModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="bg-card border border-edge rounded-2xl w-full max-w-md p-6 space-y-4">
            <div>
              <h3 className="text-base font-bold text-ink">Clear vault data?</h3>
              <p className="text-sm text-ink-3 mt-1">
                All PII entries stored in your vault will be permanently deleted. Your vault usage counter will reset.
                This cannot be undone.
              </p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">
                Type your email to confirm
              </label>
              <input
                type="email"
                value={vaultEmail}
                onChange={e => setVaultEmail(e.target.value)}
                placeholder={user.email}
                className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>
            {vaultError && <p className="text-xs text-red-500">{vaultError}</p>}
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setVaultModal(false)}
                className="px-4 py-2 rounded-lg border border-edge text-sm text-ink-2 hover:text-ink"
              >
                Cancel
              </button>
              <button
                onClick={handleClearVault}
                disabled={vaultLoading || vaultEmail !== user.email}
                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-semibold disabled:opacity-40"
              >
                {vaultLoading ? "Clearing…" : "Clear vault"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete account modal */}
      {deleteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="bg-card border border-edge rounded-2xl w-full max-w-md p-6 space-y-4">
            <div>
              <h3 className="text-base font-bold text-red-500">Delete account permanently?</h3>
              <p className="text-sm text-ink-3 mt-1">
                This will permanently delete:
              </p>
              <ul className="text-sm text-ink-3 mt-2 space-y-1 list-disc list-inside">
                <li>All vault entries and PII data</li>
                <li>All API keys</li>
                <li>All usage history</li>
                <li>Your account and profile</li>
              </ul>
              <p className="text-sm text-red-500 mt-3 font-medium">This action is irreversible.</p>
            </div>
            <div>
              <label className="block text-xs font-semibold text-ink-4 uppercase tracking-wider mb-1">
                Type DELETE to confirm
              </label>
              <input
                type="text"
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
                placeholder="DELETE"
                className="w-full px-3 py-2 rounded-lg bg-inset border border-edge text-sm text-ink focus:outline-none focus:ring-2 focus:ring-red-500"
              />
            </div>
            {deleteError && <p className="text-xs text-red-500">{deleteError}</p>}
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteModal(false)}
                className="px-4 py-2 rounded-lg border border-edge text-sm text-ink-2 hover:text-ink"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deleteLoading || deleteConfirm !== "DELETE"}
                className="px-4 py-2 rounded-lg bg-red-500 text-white text-sm font-semibold disabled:opacity-40"
              >
                {deleteLoading ? "Deleting…" : "Delete my account"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
