"""Transactional email via Resend."""
import logging
import resend

from config import settings

logger = logging.getLogger(__name__)

resend.api_key = settings.RESEND_API_KEY

_FROM = settings.EMAIL_FROM
_DEVELOPER = settings.DEVELOPER_EMAIL
_PORTAL = settings.PORTAL_FRONTEND_URL.rstrip("/")


def _send(to: str, subject: str, html: str) -> dict:
    """Send one email. Returns Resend response or raises."""
    return resend.Emails.send({
        "from": _FROM,
        "to": [to],
        "subject": subject,
        "html": html,
    })


# ── Templates ────────────────────────────────────────────────────────────────

def send_signup_notification(user_email: str) -> dict:
    """Email the portal developer when a new user signs up."""
    approval_url = f"{_PORTAL}/admin/approvals.html?email={user_email}"
    html = f"""
    <!DOCTYPE html>
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;padding:20px">
      <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 4px 16px rgba(0,0,0,.08)">
        <div style="text-align:center;margin-bottom:24px">
          <div style="display:inline-block;background:#D40511;color:#fff;font-weight:900;
                      padding:8px 24px;border-radius:10px;font-size:18px;letter-spacing:1px">
            SMART EXPORT
          </div>
          <h2 style="margin-top:16px;color:#1a1a1a">มีผู้สมัครใหม่</h2>
        </div>
        <p style="font-size:15px;color:#444;line-height:1.6">
          มีผู้ใช้สมัครเข้าสู่ระบบ DSC Portal:
        </p>
        <div style="background:#fef3c7;border-left:4px solid #FFCC00;padding:12px 16px;
                    border-radius:6px;margin:16px 0">
          <strong style="color:#92400E">{user_email}</strong>
        </div>
        <p style="color:#666;font-size:14px">
          คลิกปุ่มด้านล่างเพื่อพิจารณาอนุมัติและกำหนดสิทธิ์การใช้งาน:
        </p>
        <div style="text-align:center;margin:24px 0">
          <a href="{approval_url}"
             style="display:inline-block;background:#D40511;color:#fff;
                    padding:12px 32px;border-radius:8px;text-decoration:none;
                    font-weight:700;font-size:15px">
            เปิดหน้าอนุมัติ →
          </a>
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:32px">
          DSC · CTC FG Export Portal
        </p>
      </div>
    </body></html>
    """
    return _send(_DEVELOPER, f"DSC Portal: ผู้สมัครใหม่ — {user_email}", html)


def send_approval_notification(user_email: str, apps: list[dict]) -> dict:
    """Email user when their account is approved."""
    apps_html = "".join(
        f"<li><strong>{a['app'].title()}</strong> — {a['role']}</li>"
        for a in apps
    )
    html = f"""
    <!DOCTYPE html>
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;padding:20px">
      <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 4px 16px rgba(0,0,0,.08)">
        <div style="text-align:center;margin-bottom:24px">
          <div style="display:inline-block;background:#16a34a;color:#fff;font-weight:900;
                      padding:8px 24px;border-radius:10px;font-size:18px;letter-spacing:1px">
            ✓ APPROVED
          </div>
          <h2 style="margin-top:16px;color:#1a1a1a">บัญชีของคุณได้รับการอนุมัติ</h2>
        </div>
        <p style="font-size:15px;color:#444;line-height:1.6">
          ขณะนี้คุณสามารถเข้าใช้งานระบบต่อไปนี้ได้:
        </p>
        <ul style="background:#f0fdf4;border-left:4px solid #16a34a;padding:12px 16px 12px 32px;border-radius:6px;margin:16px 0;color:#15803d">
          {apps_html}
        </ul>
        <div style="text-align:center;margin:24px 0">
          <a href="{_PORTAL}/login.html"
             style="display:inline-block;background:#D40511;color:#fff;
                    padding:12px 32px;border-radius:8px;text-decoration:none;
                    font-weight:700;font-size:15px">
            เข้าสู่ระบบ →
          </a>
        </div>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:32px">
          DSC · CTC FG Export Portal
        </p>
      </div>
    </body></html>
    """
    return _send(user_email, "DSC Portal: บัญชีของคุณได้รับการอนุมัติ", html)


def send_password_reset(user_email: str, reset_token: str) -> dict:
    """Email user a one-time password-reset link."""
    reset_url = f"{_PORTAL}/reset-password.html?token={reset_token}"
    html = f"""
    <!DOCTYPE html>
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;padding:20px">
      <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 4px 16px rgba(0,0,0,.08)">
        <div style="text-align:center;margin-bottom:24px">
          <div style="display:inline-block;background:#D40511;color:#fff;font-weight:900;
                      padding:8px 24px;border-radius:10px;font-size:18px;letter-spacing:1px">
            SMART EXPORT
          </div>
          <h2 style="margin-top:16px;color:#1a1a1a">รีเซ็ต Password</h2>
        </div>
        <p style="font-size:15px;color:#444;line-height:1.6">
          เราได้รับคำขอรีเซ็ต password สำหรับ <strong>{user_email}</strong>
        </p>
        <p style="color:#666;font-size:14px;margin-top:12px">
          คลิกปุ่มด้านล่างเพื่อตั้ง password ใหม่ — ลิงก์มีอายุ <strong>1 ชั่วโมง</strong>:
        </p>
        <div style="text-align:center;margin:28px 0">
          <a href="{reset_url}"
             style="display:inline-block;background:#D40511;color:#fff;
                    padding:14px 36px;border-radius:8px;text-decoration:none;
                    font-weight:700;font-size:15px;box-shadow:0 4px 16px rgba(212,5,17,.3)">
            ตั้ง Password ใหม่ →
          </a>
        </div>
        <p style="color:#888;font-size:12px;text-align:center;line-height:1.5;margin-top:24px">
          หากปุ่มไม่ทำงาน copy ลิงก์นี้ไปวางใน browser:<br>
          <span style="color:#444;word-break:break-all">{reset_url}</span>
        </p>
        <div style="border-top:1px solid #eee;margin-top:24px;padding-top:16px">
          <p style="color:#999;font-size:12px;text-align:center;line-height:1.5">
            หากคุณไม่ได้ขอรีเซ็ต password — ไม่ต้องทำอะไร ลิงก์นี้จะหมดอายุไปเอง<br>
            DSC · CTC FG Export Portal
          </p>
        </div>
      </div>
    </body></html>
    """
    return _send(user_email, "DSC Portal: ลิงก์รีเซ็ต Password", html)


def send_rejection_notification(user_email: str, note: str | None = None) -> dict:
    """Email user when their signup is rejected."""
    note_html = (
        f'<p style="background:#fef2f2;border-left:4px solid #ef4444;padding:12px 16px;'
        f'border-radius:6px;color:#7f1d1d">หมายเหตุ: {note}</p>'
        if note else ""
    )
    html = f"""
    <!DOCTYPE html>
    <html><body style="font-family:'Segoe UI',Arial,sans-serif;background:#f5f5f5;padding:20px">
      <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;box-shadow:0 4px 16px rgba(0,0,0,.08)">
        <div style="text-align:center;margin-bottom:24px">
          <h2 style="color:#1a1a1a">คำขอสมัครไม่ได้รับการอนุมัติ</h2>
        </div>
        <p style="font-size:15px;color:#444;line-height:1.6">
          เสียใจด้วย คำขอสมัครของคุณ ({user_email}) ไม่ได้รับการอนุมัติ
        </p>
        {note_html}
        <p style="color:#666;font-size:14px;margin-top:16px">
          กรุณาติดต่อผู้ดูแลระบบหากมีคำถามเพิ่มเติม
        </p>
        <p style="color:#999;font-size:12px;text-align:center;margin-top:32px">
          DSC · CTC FG Export Portal
        </p>
      </div>
    </body></html>
    """
    return _send(user_email, "DSC Portal: คำขอสมัครไม่ได้รับการอนุมัติ", html)
