import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)

MAIL_SERVER = settings.MAIL_SERVER
MAIL_PORT = settings.MAIL_PORT
MAIL_USERNAME = settings.MAIL_USERNAME
MAIL_PASSWORD = settings.MAIL_PASSWORD
MAIL_FROM = settings.MAIL_FROM or settings.MAIL_USERNAME


def send_email(to_email: str, subject: str, html_body: str, from_name: str = "Genomic Intelligence System"):
    """
    Send email via SMTP with error handling and logging.
    Exceptions are logged and re-raised for caller handling.
    """
    if not MAIL_USERNAME or not MAIL_PASSWORD:
        raise RuntimeError("MAIL_USERNAME and MAIL_PASSWORD must be configured in .env")
    
    mail_from = MAIL_FROM or MAIL_USERNAME
    msg = MIMEMultipart()
    msg["From"] = formataddr((from_name, mail_from))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(MAIL_SERVER, MAIL_PORT, timeout=10) as server:
            server.set_debuglevel(1)  # Minimal SMTP protocol logging
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(mail_from, to_email, msg.as_string())
            
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"[SMTP_ERROR] Authentication failed: {e}")
        raise RuntimeError(f"SMTP Authentication failed: {e}")
    except smtplib.SMTPException as e:
        logger.error(f"[SMTP_ERROR] SMTP error: {e}")
        raise RuntimeError(f"SMTP error during email send: {e}")
    except OSError as e:
        logger.error(f"[SMTP_ERROR] Network error: {e}")
        raise RuntimeError(f"Network error connecting to SMTP server: {e}")
    except Exception as e:
        logger.error(f"[SMTP_ERROR] Unexpected error: {type(e).__name__}: {e}")
        raise RuntimeError(f"Unexpected error in email send: {e}")


def send_password_reset_email(to_email: str, reset_link: str):
    """Send password reset email with reset link."""
    subject = "Password Reset Request"
    frontend_url = settings.FRONTEND_URL.rstrip('/')
    
    html_body = f"""
        <div style="padding: 40px 16px; background-color: #f6f5f3; background-image: url('{frontend_url}/bg_main.png'); background-size: cover; background-position: center; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
          <table width="100%" border="0" cellspacing="0" cellpadding="0">
            <tr>
              <td align="center">
                <div style="max-width: 460px; margin: 0 auto; background-color: #ffffff; border-radius: 40px; padding: 40px; text-align: center; box-shadow: 0 10px 40px rgba(0,0,0,0.08);">
                  <h2 style="margin: 0 0 24px; font-size: 26px; font-weight: 800; color: #a48e7e; padding-bottom: 24px; border-bottom: 2px solid #f9f9f9; letter-spacing: -0.5px;">
                    Sedimentra
                  </h2>
                  <h1 style="margin: 0 0 16px; font-size: 28px; font-weight: 700; color: #4c4c4c; letter-spacing: -0.5px;">
                    Password Reset
                  </h1>
                  <p style="margin: 0 0 32px; color: #6d5b51; font-size: 15px; font-weight: 500; line-height: 1.5;">
                    Click the link below to reset your password.<br />This link expires in 15 minutes.
                  </p>
                  <table width="100%" border="0" cellspacing="0" cellpadding="0">
                    <tr>
                      <td align="center">
                        <a href="{reset_link}" style="display: inline-block; width: 100%; max-width: 380px; padding: 16px 0; border-radius: 30px; background-color: #938575; color: #ffffff; font-weight: 700; font-size: 14px; text-decoration: none; letter-spacing: 0.5px; text-align: center;">
                          RESET PASSWORD
                        </a>
                      </td>
                    </tr>
                  </table>
                </div>
              </td>
            </tr>
          </table>
        </div>
    """
    
    try:
        send_email(to_email, subject, html_body)
        logger.info(f"[EMAIL] Password reset email sent to {to_email}")
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send password reset email to {to_email}: {e}")
        raise
