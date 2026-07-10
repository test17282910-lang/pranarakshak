"""
alerts.py — Twilio SMS and SendGrid Email Dispatcher
Implements delivery mechanisms with transparent mock fallback options for local testing.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Config variables ─────────────────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "").strip()
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "").strip()


# ─── Twilio SMS Dispatch ──────────────────────────────────────────────────────

def send_sms(to: str, body: str) -> tuple[str, str]:
    """
    Sends an SMS using Twilio.
    If credentials are dummy or missing, falls back to mock delivery.
    Returns (status, provider_id/reason).
    """
    if not to:
        return "suppressed", "No phone number registered"

    # Detect placeholders or empty credentials
    is_mock = (
        not TWILIO_ACCOUNT_SID 
        or not TWILIO_AUTH_TOKEN 
        or "your_twilio" in TWILIO_ACCOUNT_SID.lower()
        or TWILIO_ACCOUNT_SID == ""
    )

    if is_mock:
        logger.info(f"📬 [MOCK SMS] to {to}: {body}")
        return "sent", f"mock_sms_{os.urandom(6).hex()}"

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=TWILIO_FROM_NUMBER,
            to=to
        )
        logger.info(f"✓ SMS alert successfully sent to {to} via Twilio. SID: {message.sid}")
        return "sent", message.sid
    except Exception as exc:
        logger.error(f"❌ Twilio SMS dispatch failed to {to}: {exc}")
        return "failed", str(exc)


# ─── SendGrid Email Dispatch ──────────────────────────────────────────────────

def send_email(to: str, subject: str, body_html: str) -> tuple[str, str]:
    """
    Sends an HTML email using SendGrid.
    If credentials are dummy or missing, falls back to mock delivery.
    Returns (status, provider_id/reason).
    """
    if not to:
        return "suppressed", "No email registered"

    # Detect placeholders or empty credentials
    is_mock = (
        not SENDGRID_API_KEY 
        or "your_sendgrid" in SENDGRID_API_KEY.lower()
        or SENDGRID_API_KEY == ""
    )

    if is_mock:
        logger.info(f"📬 [MOCK EMAIL] to {to} | Subject: {subject}\nContent: {body_html[:200]}...")
        return "sent", f"mock_email_{os.urandom(6).hex()}"

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
        
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=to,
            subject=subject,
            html_content=body_html
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        # Check success status
        if response.status_code in (200, 201, 202):
            msg_id = response.headers.get("X-Message-Id", f"sg_{os.urandom(6).hex()}")
            logger.info(f"✓ Email alert successfully sent to {to} via SendGrid. ID: {msg_id}")
            return "sent", msg_id
        else:
            logger.error(f"❌ SendGrid returned status code {response.status_code} for {to}")
            return "failed", f"HTTP_{response.status_code}"
    except Exception as exc:
        logger.error(f"❌ SendGrid Email dispatch failed to {to}: {exc}")
        return "failed", str(exc)
