"""
Email Notification Sender.
Uses smtplib to send emails using standard SMTP/App Passwords.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging

logger = logging.getLogger(__name__)

def send_notification(subject: str, body: str):
    """
    Sends an email notification using configured SMTP credentials.
    """
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    recipient = os.environ.get("NOTIFICATION_EMAIL")

    if not all([smtp_user, smtp_pass, recipient]):
        logger.warning("SMTP credentials or NOTIFICATION_EMAIL not fully configured. Skipping email.")
        return

    # Using Gmail SMTP settings as default given the standard app password usage
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))

    msg = MIMEMultipart()
    msg['From'] = smtp_user
    msg['To'] = recipient
    msg['Subject'] = f"[HITL Agent] {subject}"

    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(smtp_host, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        logger.info(f"📧 Notification email sent to {recipient}")
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")

if __name__ == "__main__":
    # Simple self-test
    from dotenv import load_dotenv
    load_dotenv()
    send_notification("Test Email", "This is a test from the HITL agent.")
