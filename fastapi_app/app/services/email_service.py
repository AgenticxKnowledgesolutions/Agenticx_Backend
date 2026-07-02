import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger("email_service")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(ch)


class EmailService:
    @classmethod
    def send_via_resend(cls, to_email: str, subject: str, body_text: str) -> bool:
        import httpx
        try:
            headers = {
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            }
            # Resend requires a from field. Default to onboarding@resend.dev if not configured.
            from_email = settings.SMTP_FROM or "onboarding@resend.dev"
            payload = {
                "from": from_email,
                "to": [to_email],
                "subject": subject,
                "text": body_text
            }
            response = httpx.post("https://api.resend.com/emails", json=payload, headers=headers, timeout=10.0)
            if response.status_code in (200, 201, 202):
                logger.info(f"Email successfully sent via Resend API to {to_email}")
                return True
            else:
                logger.error(f"Resend API failed: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Exception sending via Resend API to {to_email}: {str(e)}")
            return False

    @classmethod
    def send_admission_link(cls, to_email: str, name: str, apply_url: str) -> bool:
        logger.warning(f"send_admission_link called for {to_email} but it is disabled. Frontend EmailJS is used instead.")
        return False

    @classmethod
    def send_otp_email(cls, to_email: str, otp: str) -> bool:
        subject = f"{otp} is your AgenticX Login Verification Code"
        body = f"""Hi,

Your one-time login verification code (OTP) for the AgenticX Candidate Portal is:

{otp}

This code is valid for 5 minutes. Please do not share this code with anyone.

Best regards,
AgenticX Team
"""
        if settings.RESEND_API_KEY:
            return cls.send_via_resend(to_email, subject, body)

        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                f"[SMTP NOT CONFIG] Would send OTP code email to {to_email}.\n"
                f"OTP Code: {otp}"
            )
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_FROM or settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            # Use SSL/TLS or STARTTLS depending on port
            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.send_message(msg)
                
            logger.info(f"OTP email successfully sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send OTP email to {to_email}: {str(e)}")
            return False
