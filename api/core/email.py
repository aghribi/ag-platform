"""Transactional email via Resend. All sends are fire-and-forget."""
import html as _html
import httpx

from core.config import settings


def _e(s: str) -> str:
    """HTML-escape a user-controlled string before embedding it in an email template."""
    return _html.escape(str(s), quote=True)

_RESEND_URL = "https://api.resend.com/emails"


async def _send(to: str, subject: str, html: str) -> None:
    if not settings.RESEND_API_KEY:
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": f"ag-tools <{settings.NOTIFY_FROM}>",
                    "to": [to],
                    "subject": subject,
                    "html": html,
                },
            )
    except Exception:
        pass  # never block the caller


async def send_verification(email: str, verify_url: str) -> None:
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#0ea5e9">Confirm your email address</h2>
  <p>Thanks for signing up for ag-tools. Click the button below to activate your account.</p>
  <p style="margin:24px 0">
    <a href="{verify_url}"
       style="background:#0ea5e9;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">
      Confirm email →</a>
  </p>
  <p style="color:#6b7280;font-size:13px">This link expires in 24 hours.
     If you didn't create an ag-tools account, you can safely ignore this email.</p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}" style="color:#6b7280">{settings.dashboard}</a>
  </p>
</div>"""
    await _send(email, "Confirm your ag-tools email address", html)


async def send_password_reset(email: str, reset_url: str) -> None:
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#0ea5e9">Reset your password</h2>
  <p>We received a request to reset the password for your ag-tools account.</p>
  <p style="margin:24px 0">
    <a href="{reset_url}"
       style="background:#0ea5e9;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">
      Reset password →</a>
  </p>
  <p style="color:#6b7280;font-size:13px">This link expires in 1 hour.
     If you didn't request a reset, you can safely ignore this email.</p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}" style="color:#6b7280">{settings.dashboard}</a>
  </p>
</div>"""
    await _send(email, "Reset your ag-tools password", html)


async def send_quota_warning(email: str, pct: int, used: int, quota: int) -> None:
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#4f46e5">Quota alert: {pct}% used</h2>
  <p>You've used <strong>{used:,}</strong> of your <strong>{quota:,}</strong> monthly units on ag-tools.</p>
  <p>If you reach 100%, API calls will be rejected until the start of next month.
     To request a higher limit, contact <a href="mailto:{settings.CONTACT_EMAIL}">{settings.CONTACT_EMAIL}</a>.</p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}/dashboard" style="color:#6b7280">Manage account</a>
  </p>
</div>"""
    await _send(email, f"ag-tools: you've used {pct}% of your monthly quota", html)


async def send_org_invite(to_email: str, org_name: str, invite_url: str, invited_by: str) -> None:
    safe_org = _e(org_name)
    safe_by = _e(invited_by)
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#4f46e5">You've been invited to join {safe_org} on ag-tools</h2>
  <p><strong>{safe_by}</strong> has invited you to join their team on ag-tools,
     the hosted API for PII protection, evals, guardrails and document extraction.</p>
  <p style="margin:24px 0">
    <a href="{invite_url}"
       style="background:#4f46e5;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;">
      Accept invitation →</a>
  </p>
  <p style="color:#6b7280;font-size:13px">This invitation expires in 7 days.
     If you didn't expect this email, you can safely ignore it.</p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}" style="color:#6b7280">{settings.dashboard}</a>
  </p>
</div>"""
    await _send(to_email, f"You've been invited to join {org_name} on ag-tools", html)


async def send_ticket_notification(admin_email: str, ticket_id: str, from_email: str,
                                   subject: str, message: str) -> None:
    safe_from    = _e(from_email)
    safe_subject = _e(subject)
    safe_message = _e(message).replace("\n", "<br>")
    html = f"""
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;color:#111827">
  <h2 style="color:#0ea5e9">New support ticket</h2>
  <table style="font-size:14px;border-collapse:collapse;width:100%;margin:16px 0">
    <tr><td style="padding:6px 12px 6px 0;color:#6b7280;white-space:nowrap">From</td>
        <td style="padding:6px 0">{safe_from}</td></tr>
    <tr><td style="padding:6px 12px 6px 0;color:#6b7280;white-space:nowrap">Subject</td>
        <td style="padding:6px 0">{safe_subject}</td></tr>
    <tr><td style="padding:6px 12px 6px 0;color:#6b7280;white-space:nowrap">Ticket ID</td>
        <td style="padding:6px 0;font-family:monospace;font-size:12px">{_e(ticket_id)}</td></tr>
  </table>
  <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:8px;padding:16px;font-size:14px;line-height:1.6">
    {safe_message}
  </div>
  <p style="margin-top:20px">
    <a href="{settings.dashboard}/admin/tickets"
       style="background:#0ea5e9;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">
      View in admin →</a>
  </p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}" style="color:#6b7280">{settings.dashboard}</a>
  </p>
</div>"""
    await _send(admin_email, f"[Ticket] {subject}", html)


async def send_ticket_confirmation(to_email: str, ticket_id: str, subject: str) -> None:
    safe_subject   = _e(subject)
    safe_ticket_id = _e(ticket_id)
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#0ea5e9">We received your request</h2>
  <p>Thanks for reaching out. We've received your message and will get back to you
     within <strong>one business day</strong>.</p>
  <table style="font-size:14px;border-collapse:collapse;width:100%;margin:16px 0">
    <tr><td style="padding:6px 12px 6px 0;color:#6b7280;white-space:nowrap">Subject</td>
        <td style="padding:6px 0">{safe_subject}</td></tr>
    <tr><td style="padding:6px 12px 6px 0;color:#6b7280;white-space:nowrap">Reference</td>
        <td style="padding:6px 0;font-family:monospace;font-size:12px">{safe_ticket_id}</td></tr>
  </table>
  <p style="color:#6b7280;font-size:13px">
    Keep this email: your reference number lets us find your request quickly
    if you need to follow up at <a href="mailto:{settings.CONTACT_EMAIL}" style="color:#0ea5e9">{settings.CONTACT_EMAIL}</a>.
  </p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}" style="color:#6b7280">{settings.dashboard}</a>
  </p>
</div>"""
    await _send(to_email, f"We received your request: {safe_subject}", html)


async def send_job_completed(email: str, job_id: str, schema_name: str, status: str) -> None:
    safe_status = _e(status)
    safe_job_id = _e(job_id)
    safe_schema = _e(schema_name)
    status_line = (
        '<p style="color:#16a34a">✓ Extraction completed successfully.</p>'
        if status == "completed"
        else '<p style="color:#dc2626">✗ Job failed. Check the dashboard for details.</p>'
    )
    html = f"""
<div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#111827">
  <h2 style="color:#4f46e5">DocParse job {safe_status}</h2>
  {status_line}
  <table style="font-size:14px;border-collapse:collapse;width:100%;margin:16px 0">
    <tr><td style="padding:6px 0;color:#6b7280">Job ID</td>
        <td style="padding:6px 0;font-family:monospace">{safe_job_id}</td></tr>
    <tr><td style="padding:6px 0;color:#6b7280">Schema</td>
        <td style="padding:6px 0">{safe_schema}</td></tr>
  </table>
  <p><a href="{settings.dashboard}/dashboard/docparse"
        style="background:#4f46e5;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;">
     View result →</a></p>
  <p style="color:#6b7280;font-size:12px;margin-top:32px">
    ag-tools · <a href="{settings.dashboard}/dashboard" style="color:#6b7280">Manage account</a>
  </p>
</div>"""
    await _send(email, f"ag-tools DocParse job {status}: {schema_name}", html)
