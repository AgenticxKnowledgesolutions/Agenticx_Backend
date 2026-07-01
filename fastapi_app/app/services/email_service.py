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
    def send_admission_link(cls, to_email: str, name: str, apply_url: str) -> bool:
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                f"[SMTP NOT CONFIG] Would send admission form email to {to_email}.\n"
                f"URL: {apply_url}"
            )
            return False
            
        try:
            msg = MIMEMultipart()
            msg['From'] = settings.SMTP_FROM or settings.SMTP_USER
            msg['To'] = to_email
            msg['Subject'] = "Complete Your Candidate Admission Form - Agenticx"
            
            body = f"""Hi {name},

Thank you for your interest. You have been qualified for next steps.

Please complete your candidate admission form by clicking the link below:
{apply_url}

Best regards,
Agenticx Team
"""
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
                
            logger.info(f"Admission form email successfully sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False

    @classmethod
    def send_otp_email(cls, to_email: str, otp: str) -> bool:
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
            msg['Subject'] = f"{otp} is your AgenticX Login Verification Code"
            
            body = f"""Hi,

Your one-time login verification code (OTP) for the AgenticX Candidate Portal is:

{otp}

This code is valid for 5 minutes. Please do not share this code with anyone.

Best regards,
AgenticX Team
"""
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
