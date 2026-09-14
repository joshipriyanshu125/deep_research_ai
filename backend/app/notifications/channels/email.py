"""
Days 67–69 — Email Notification Channel

Delivers email notifications via SMTP or logs formatted emails when SMTP is unconfigured.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

from app.config.settings import settings
from app.database.models.notification import NotificationPayload
from app.utils.logger import logger


class EmailNotificationChannel:
    """Delivers email notifications for research lifecycle events."""

    def __init__(self) -> None:
        self.smtp_server = getattr(settings, "SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(getattr(settings, "SMTP_PORT", 587))
        self.smtp_user = getattr(settings, "SMTP_USERNAME", "")
        self.smtp_pass = getattr(settings, "SMTP_PASSWORD", "")
        self.email_from = getattr(settings, "EMAIL_FROM", "noreply@deepresearch.ai")

    async def send(self, payload: NotificationPayload, recipient_email: Optional[str] = None) -> bool:
        """Send email notification."""
        to_address = recipient_email or f"{payload.user_id}@deepresearch.ai"
        subject = f"[{settings.PROJECT_NAME}] {payload.title}"

        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e0e0e0; border-radius: 8px;">
              <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">{payload.title}</h2>
              <p><strong>Event:</strong> {payload.event_type.replace('_', ' ').title()}</p>
              <p><strong>Research ID:</strong> <code>{payload.research_id}</code></p>
              <p style="background: #f8f9fa; padding: 12px; border-left: 4px solid #3498db; border-radius: 4px;">
                {payload.message}
              </p>
              <footer style="margin-top: 20px; font-size: 12px; color: #7f8c8d; border-top: 1px solid #eee; padding-top: 10px;">
                Autonomous Deep Research AI Platform &bull; {payload.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
              </footer>
            </div>
          </body>
        </html>
        """

        # If SMTP username/password are provided, attempt live delivery
        if self.smtp_user and self.smtp_pass:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = self.email_from
                msg["To"] = to_address
                msg.attach(MIMEText(payload.message, "plain"))
                msg.attach(MIMEText(html_body, "html"))

                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(self.smtp_user, self.smtp_pass)
                    server.sendmail(self.email_from, [to_address], msg.as_string())

                logger.info(f"[EmailChannel] Email sent to {to_address}: '{subject}'")
                return True
            except Exception as exc:
                logger.error(f"[EmailChannel] Failed sending email to {to_address}: {exc}")
                return False
        else:
            # Fallback simulated email logging
            logger.info(f"[EmailChannel Simulated] To: {to_address} | Subject: '{subject}' | Message: {payload.message}")
            return True


email_channel = EmailNotificationChannel()
