import uuid
import urllib.parse
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.candidate_application import CandidateApplication
from app.services.upload_service import UploadService


class CertificateUploadService(UploadService):
    def __init__(self):
        super().__init__()
        self.bucket_name = "certificates"

    async def upload_certificate(self, file_content: bytes, candidate_id: str) -> str:
        """Uploads certificate PDF directly to certificates/{candidate_id}.pdf in certificates bucket."""
        # Ensure the bucket is created and public
        await self.ensure_bucket_exists()

        file_path = f"certificates/{candidate_id}.pdf"

        async with httpx.AsyncClient() as client:
            try:
                res = await client.put(
                    f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{file_path}",
                    headers={
                        **self.headers,
                        "Content-Type": "application/pdf"
                    },
                    content=file_content,
                    timeout=30.0
                )
                if res.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Supabase Storage Certificate Upload failed: {res.text}"
                    )

                # Return the public access URL
                return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{file_path}"
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage upload request failed: {str(e)}"
                )


# ReportLab-based Certificate Template & Generation Logic
import io
import os
import uuid
from datetime import datetime
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.core.security import create_certificate_token

# Brand colors from template
NAVY = HexColor("#16263F")
NAVY_SOFT = HexColor("#3C5478")
TEAL = HexColor("#1F9C9C")
TEAL_LIGHT = HexColor("#E7F6F6")
DARK_TEXT = HexColor("#262B33")
GREY_TEXT = HexColor("#6B7280")
HAIRLINE = HexColor("#D8DEE6")

PRONOUNS = {
    "male": {"subject": "He", "possessive": "His"},
    "female": {"subject": "She", "possessive": "Her"},
    "other": {"subject": "They", "possessive": "Their"},
}


def resolve_pronoun(gender: str) -> dict:
    return PRONOUNS.get((gender or "").strip().lower(), PRONOUNS["other"])


def get_ordinal_suffix(day: int) -> str:
    if 11 <= day <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")


def build_qr_image_from_url(verification_url: str):
    try:
        qr = qrcode.QRCode(
            version=2,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(verification_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#16263F", back_color="white")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return ImageReader(buf)
    except Exception as e:
        logger.error(f"Failed to generate QR code for URL {verification_url}: {e}", exc_info=True)
        return None


def draw_wrapped_text(c, text, x, y, max_width, font="Helvetica", size=11,
                       leading=16, color=DARK_TEXT, align="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    words = text.split(" ")
    lines = []
    line = ""
    for word in words:
        test_line = f"{line} {word}".strip()
        if c.stringWidth(test_line, font, size) <= max_width:
            line = test_line
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)

    for ln in lines:
        if align == "center":
            c.drawCentredString(x + max_width / 2, y, ln)
        else:
            c.drawString(x, y, ln)
        y -= leading
    return y


def get_course_details(course_name: str) -> dict:
    course_name_lower = (course_name or "").lower()
    if "data analytics" in course_name_lower:
        return {
            "topics": "Basics of Financial Accounting, MS Excel, Alteryx, Basics of SQL, Python, and Power BI",
            "domain": "Data Analytics"
        }
    elif "react native" in course_name_lower:
        return {
            "topics": "React Native components, Navigation, State Management, Push Notifications, Native Modules, App Store Deployment",
            "domain": "Mobile App Development"
        }
    elif "full stack" in course_name_lower or "web" in course_name_lower:
        return {
            "topics": "HTML5, CSS3, JavaScript, React, Node.js, Express, databases, REST APIs, and Cloud Deployment",
            "domain": "Full Stack Web Development"
        }
    elif "fastapi" in course_name_lower or "python" in course_name_lower:
        return {
            "topics": "Python programming, FastAPI framework, Pydantic, SQLAlchemy, PostgreSQL, async programming, and API Security",
            "domain": "Backend Web Development"
        }
    else:
        return {
            "topics": "Advanced core concepts, industry best practices, practical application, and final project evaluation",
            "domain": "Software Engineering"
        }


class CertificateService:
    @staticmethod
    async def generate_and_save_certificate(db: AsyncSession, candidate: CandidateApplication) -> CandidateApplication:
        """Generates the certificate using ReportLab, uploads to Supabase and updates candidate DB record."""
        # Determine/assign certificate_id if not present
        if not candidate.certificate_id:
            candidate.certificate_id = str(uuid.uuid4())

        # Determine completion date
        comp_date = candidate.completed_at or datetime.utcnow()
        candidate.completed_at = comp_date
        
        # Format completion date: e.g. "19th June 2026"
        day_suffix = get_ordinal_suffix(comp_date.day)
        completion_date_str = f"{comp_date.day}{day_suffix} {comp_date.strftime('%B %Y')}"
        issue_date_str = comp_date.strftime("%d %B %Y")

        # Generate signed JWT token (No expiry!)
        token = create_certificate_token(candidate.certificate_id)

        # Generate verification URL
        verification_url = f"{settings.CERTIFICATE_FRONTEND_URL.rstrip('/')}/verify?token={token}"

        # Fetch course details dynamically
        course_applied = candidate.course_applied or "Professional Certification Program"
        course_details = get_course_details(course_applied)

        # Fetch conduct remark
        conduct_remark = candidate.remarks.strip() if candidate.remarks else "Excellent"

        # Map candidate details to template data format
        data = {
            "certificateId": candidate.application_number or candidate.certificate_id,
            "issueDate": issue_date_str,
            "recipientName": candidate.full_name,
            "gender": candidate.gender or "other",
            "courseName": course_applied,
            "courseTopics": course_details["topics"],
            "organizationName": "AgenticX Knowledge Solutions LLP",
            "courseMode": candidate.mode_of_learning or "Online",
            "courseDuration": candidate.course_duration or "4 Weeks or 90+ Hours",
            "courseDomain": course_details["domain"],
            "startDate": candidate.course_start_date.strftime("%d/%m/%Y") if candidate.course_start_date else comp_date.strftime("%d/%m/%Y"),
            "endDate": comp_date.strftime("%d/%m/%Y"),
            "completionDate": completion_date_str,
            "conductRemark": conduct_remark,
            "performance": candidate.performance,
        }

        # Draw PDF using ReportLab in-memory
        pdf_buffer = io.BytesIO()
        pronoun = resolve_pronoun(data.get("gender"))

        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        width, height = A4
        margin = 22 * mm
        content_w = width - 2 * margin

        # ===================== Top accent bar =====================
        c.setFillColor(NAVY)
        c.rect(0, height - 4 * mm, width, 4 * mm, fill=1, stroke=0)
        c.setFillColor(TEAL)
        c.rect(0, height - 4 * mm, width * 0.32, 4 * mm, fill=1, stroke=0)

        # ===================== Header (centered) =====================
        top = height - 18 * mm
        logo_size = 20 * mm

        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "AgenticX-removebg-preview.png")
        try:
            logo_img = ImageReader(logo_path)
            c.drawImage(
                logo_img,
                width / 2 - logo_size / 2,
                top - logo_size,
                width=logo_size,
                height=logo_size,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception:
            # graceful fallback if logo file is unavailable
            c.setFillColor(NAVY)
            c.roundRect(width / 2 - logo_size / 2, top - logo_size, logo_size, logo_size, 3 * mm, fill=1, stroke=0)
            c.setFillColor(HexColor("#FFFFFF"))
            c.setFont("Helvetica-Bold", 8)
            c.drawCentredString(width / 2, top - logo_size / 2 - 2, "AgenticX")

        name_y = top - logo_size - 8 * mm
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 21)
        c.drawCentredString(width / 2, name_y, "AgenticX Knowledge Solutions")

        c.setFillColor(GREY_TEXT)
        c.setFont("Helvetica", 9.5)
        c.drawCentredString(width / 2, name_y - 6 * mm, "3rd Floor, Raj Plaza, Town Limit, Kollam, Kerala")
        c.drawCentredString(width / 2, name_y - 11 * mm, "www.agenticx.co.in  |  anju.muraleedharan@agenticx.co.in  |  +91 94965 52094")

        rule_y = name_y - 16 * mm
        c.setStrokeColor(TEAL)
        c.setLineWidth(1.2)
        c.line(margin, rule_y, width - margin, rule_y)

        # ===================== Cert ID / Date row =====================
        meta_y = rule_y - 7 * mm
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(margin, meta_y, f"Certificate No: {data['certificateId']}")
        c.drawRightString(width - margin, meta_y, f"Date of Issue: {data['issueDate']}")

        # ===================== Title =====================
        title_y = meta_y - 14 * mm
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 19)
        title = "CERTIFICATE OF COMPLETION"
        c.drawCentredString(width / 2, title_y, title)

        c.setFillColor(TEAL)
        tw = c.stringWidth(title, "Helvetica-Bold", 19)
        c.setLineWidth(1.6)
        c.line(width / 2 - tw / 2.6, title_y - 4 * mm, width / 2 + tw / 2.6, title_y - 4 * mm)

        # ===================== Body paragraph =====================
        body_y = title_y - 16 * mm
        body = (
            f"This is to certify that {data['recipientName']} has successfully completed the "
            f"{data['courseName']}, covering {data['courseTopics']} at {data['organizationName']} "
            f"on {data['completionDate']}. {pronoun['subject']} actively participated throughout the "
            f"program with full dedication and demonstrated a strong commitment to learning."
        )
        y = draw_wrapped_text(c, body, margin, body_y, content_w, size=11, leading=15.5)

        # ===================== Course Details panel =====================
        panel_top = y - 6 * mm
        detail_rows = [
            ("Organization", data["organizationName"]),
            ("Mode", data["courseMode"]),
            ("Duration & Hours", data["courseDuration"]),
            ("Domain(s)", data["courseDomain"]),
            ("Topics Covered", data["courseTopics"]),
            ("Start Date", data["startDate"]),
            ("End Date", data["endDate"]),
        ]

        label_w = 38 * mm
        row_leading = 6 * mm
        pad = 6 * mm

        # estimate panel height by laying out text first into a buffer
        temp_y = panel_top - pad
        c.setFont("Helvetica", 10)
        row_heights = []
        for label, value in detail_rows:
            lines_needed = 1
            words = value.split(" ")
            line = ""
            for word in words:
                test = f"{line} {word}".strip()
                if c.stringWidth(test, "Helvetica", 10) <= (content_w - label_w - pad * 2):
                    line = test
                else:
                    lines_needed += 1
                    line = word
            row_heights.append(lines_needed)
        panel_height = pad * 2 + sum(h * row_leading for h in row_heights) + 8 * mm

        c.setFillColor(TEAL_LIGHT)
        c.roundRect(margin, panel_top - panel_height, content_w, panel_height, 2.5 * mm, fill=1, stroke=0)
        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.6)
        c.roundRect(margin, panel_top - panel_height, content_w, panel_height, 2.5 * mm, fill=0, stroke=1)

        cy = panel_top - pad - 2 * mm
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin + pad, cy, "Course Details")
        cy -= 8 * mm

        for label, value in detail_rows:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(NAVY_SOFT)
            c.drawString(margin + pad, cy, f"{label}:")
            wrapped_end = draw_wrapped_text(
                c, value,
                margin + pad + label_w, cy + 0.1 * mm,
                content_w - label_w - pad * 2,
                font="Helvetica", size=10, leading=row_leading, color=DARK_TEXT,
            )
            # advance cy by however many lines were used
            lines_used = round((cy - wrapped_end) / row_leading)
            cy -= max(lines_used, 1) * row_leading

        y = panel_top - panel_height - 10 * mm

        # ===================== Conduct & Performance remark =====================
        c.setFont("Helvetica", 11)
        c.setFillColor(DARK_TEXT)
        conduct_line = f"{pronoun['possessive']} conduct and character during the period with us were "
        c.drawString(margin, y, conduct_line)
        cw = c.stringWidth(conduct_line, "Helvetica", 11)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(TEAL)
        c.drawString(margin + cw, y, f"{data['conductRemark']}.")

        if data.get("performance"):
            y -= 5.5 * mm
            c.setFont("Helvetica", 11)
            c.setFillColor(DARK_TEXT)
            perf_line = "Performance during the period was "
            c.drawString(margin, y, perf_line)
            pcw = c.stringWidth(perf_line, "Helvetica", 11)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(TEAL)
            perf_val = data["performance"].strip().capitalize()
            c.drawString(margin + pcw, y, f"{perf_val}.")

        y -= 9 * mm
        c.setFont("Helvetica", 11)
        c.setFillColor(DARK_TEXT)
        c.drawString(margin, y, "Wishing you all the best for your future endeavors.")

        # ===================== QR verification block (replaces seal) =====================
        qr_img = build_qr_image_from_url(verification_url)
        if qr_img is not None:
            qr_size = 26 * mm
            qr_x = margin
            qr_y = 34 * mm

            c.setStrokeColor(HAIRLINE)
            c.setLineWidth(0.6)
            c.roundRect(qr_x - 4 * mm, qr_y - 9 * mm, qr_size + 8 * mm, qr_size + 14 * mm, 2 * mm, fill=0, stroke=1)
            c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)

            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(NAVY)
            c.drawString(qr_x - 4 * mm + 2 * mm, qr_y - 5 * mm, "Scan to verify")
            c.setFont("Helvetica", 7)
            c.setFillColor(GREY_TEXT)
            c.drawString(qr_x - 4 * mm + 2 * mm, qr_y - 8.5 * mm, f"ID: {data['certificateId']}")
        else:
            logger.warning("Skipping QR code rendering due to generation failure.")

        # ===================== Signature block =====================
        sig_x = width - margin - 60 * mm
        c.setFont("Helvetica-Oblique", 11)
        c.setFillColor(DARK_TEXT)
        c.drawString(sig_x, 58 * mm, "Sincerely,")

        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.8)
        c.line(sig_x, 44 * mm, sig_x + 56 * mm, 44 * mm)

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(NAVY)
        c.drawString(sig_x, 39 * mm, "Anju Muraleedharan")
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(sig_x, 34.5 * mm, "Managing Partner")

        # ===================== Footer =====================
        c.setStrokeColor(TEAL)
        c.setLineWidth(1.2)
        c.line(margin, 18 * mm, width - margin, 18 * mm)
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(margin, 13 * mm, "AgenticX Knowledge Solutions")
        c.drawRightString(width - margin, 13 * mm, "Page 1")

        c.setFillColor(NAVY)
        c.rect(0, 0, width, 2.5 * mm, fill=1, stroke=0)

        c.showPage()
        c.save()

        # Get pdf bytes from buffer
        pdf_bytes = pdf_buffer.getvalue()

        try:
            # Upload to Supabase Storage
            uploader = CertificateUploadService()
            public_url = await uploader.upload_certificate(pdf_bytes, candidate.id)

            # Update candidate attributes
            candidate.certificate_url = public_url
            candidate.certificate_status = "valid"
            candidate.updated_at = datetime.utcnow()
            
            return candidate
        except Exception as e:
            # Re-raise as HTTP 500 error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Certificate generation or storage upload failed: {str(e)}"
            )


certificate_service = CertificateService()
