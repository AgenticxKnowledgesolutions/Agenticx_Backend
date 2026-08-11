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
    if not course_name or not course_name.strip():
        raise ValueError("Course name cannot be empty or null for certificate generation.")

    course_name_clean = course_name.strip()
    course_name_lower = course_name_clean.lower()
    
    # 1. Check for Webinar
    if "webinar" in course_name_lower:
        topic = "General Technology"
        for splitter in [" on ", " in ", " - ", ":"]:
            if splitter in course_name_lower:
                parts = course_name_clean.split(splitter if splitter != ":" else ":", 1)
                if len(parts) > 1 and parts[1].strip():
                    topic = parts[1].strip()
                    break
        else:
            temp = course_name_clean
            if temp.lower().startswith("webinar"):
                temp = temp[len("webinar"):].strip().lstrip(" -:")
            if temp:
                topic = temp
            
        return {
            "topics": f"Technology Overview, Industry Trends, Emerging Concepts, Q&A with Experts, and Interactive Discussions on {topic}",
            "domain": f"Webinar: {topic}"
        }

    # 1.5 Check for Faculty Development Programme (FDP)
    if "fdp" in course_name_lower or "faculty development" in course_name_lower:
        topic = "Academic and Research Methodologies"
        for splitter in [" on ", " in ", " - ", ":"]:
            if splitter in course_name_lower:
                parts = course_name_clean.split(splitter if splitter != ":" else ":", 1)
                if len(parts) > 1 and parts[1].strip():
                    topic = parts[1].strip()
                    break
        else:
            temp = course_name_clean
            for prefix in ["faculty development programme", "faculty development program", "faculty development", "fdp"]:
                if temp.lower().startswith(prefix):
                    temp = temp[len(prefix):].strip()
                    break
            temp = temp.lstrip(" -:")
            if temp:
                topic = temp
                
        return {
            "topics": f"Advanced Pedagogy, Curriculum Design, Practical Training, Research Methodology, and Emerging Technologies in {topic}",
            "domain": f"Faculty Development Programme: {topic}"
        }

    # 2. Check for Workshop
    if "workshop" in course_name_lower or "bootcamp" in course_name_lower:
        topic = "Practical Technology Labs"
        keyword = "workshop" if "workshop" in course_name_lower else "bootcamp"
        for splitter in [" on ", " in ", " - ", ":"]:
            if splitter in course_name_lower:
                parts = course_name_clean.split(splitter if splitter != ":" else ":", 1)
                if len(parts) > 1 and parts[1].strip():
                    topic = parts[1].strip()
                    break
        else:
            temp = course_name_clean
            if temp.lower().startswith(keyword):
                temp = temp[len(keyword):].strip().lstrip(" -:")
            if temp:
                topic = temp
            
        return {
            "topics": f"Interactive Technical Training, Practical Labs, Guided Projects, Framework Deep-Dive, and Collaborative Problem Solving on {topic}",
            "domain": f"Workshop: {topic}"
        }

    # 3. Check for Internship
    if "internship" in course_name_lower or "intern" in course_name_lower:
        role = "Software Development"
        for splitter in [" in ", " on ", " - ", ":"]:
            if splitter in course_name_lower:
                parts = course_name_clean.split(splitter if splitter != ":" else ":", 1)
                if len(parts) > 1 and parts[1].strip():
                    role = parts[1].strip()
                    break
        else:
            temp = course_name_clean
            for prefix in ["internship", "intern"]:
                if temp.lower().startswith(prefix):
                    temp = temp[len(prefix):].strip()
                    break
            temp = temp.lstrip(" -:")
            if temp:
                role = temp
            
        return {
            "topics": f"Hands-on Project Work, Collaborative Development, Version Control, Code Reviews, Software Engineering Lifecycle, and Professional Best Practices in {role}",
            "domain": f"Internship: {role}"
        }

    # 4. Standard config alias matching (longest matching alias first)
    from app.core.course_config import COURSE_CONFIG
    
    best_match = None
    best_match_length = -1
    
    for config in COURSE_CONFIG:
        for alias in config["aliases"]:
            if alias in course_name_lower:
                if len(alias) > best_match_length:
                    best_match_length = len(alias)
                    best_match = config
                    
    if best_match:
        return {
            "topics": best_match["topics"],
            "domain": best_match["domain"]
        }

    # 5. Robust fallback for unlisted courses
    return {
        "topics": f"Professional Development, Advanced Concepts, Hands-on Training, and Practical Applications in {course_name_clean}",
        "domain": course_name_clean
    }


class CertificateMetadataResolver:
    """Resolves certificate metadata using strict 5-tier priority hierarchy:
    1. Candidate Overrides (candidate.certificate_*)
    2. Program Certificate Metadata (program.certificate_*)
    3. Existing Candidate Values (candidate.programme_domain, candidate.training_location, candidate.course_applied, etc.)
    4. Legacy Fallback (get_course_details() / keyword matching)
    5. System Default
    """

    @classmethod
    def resolve_all(cls, candidate: CandidateApplication, program: Optional[Any] = None) -> Dict[str, Any]:
        course_applied = candidate.course_applied or "Professional Certification Program"
        course_details = get_course_details(course_applied)

        # 1. Program Type
        program_type = (
            candidate.certificate_program_type or
            candidate.program_type or
            (program.certificate_default_program_type if program else None) or
            (program.program_type if program else None) or
            "Course"
        )

        # 2. Course Name
        course_name = (
            candidate.certificate_course_name or
            candidate.course_applied or
            (program.name if program else None) or
            "Professional Certification Program"
        )

        # 3. Certificate Template
        cert_template = (
            (program.certificate_template if program else None) or
            "completion"
        )
        prog_type_lower = program_type.lower()
        course_lower = course_name.lower()
        if cert_template not in ["appreciation", "achievement"] and (
            prog_type_lower in ["fdp", "faculty development programme"] or
            "fdp" in course_lower or
            "faculty development" in course_lower
        ):
            cert_template = "fdp"
            program_type = "Faculty Development Programme"
        elif not candidate.program_id and cert_template not in ["appreciation", "achievement"]:
            if (
                "webinar" in course_lower or
                "workshop" in course_lower or
                prog_type_lower in ["workshop", "webinar"]
            ):
                cert_template = "participation"

        # 4. Certificate Title
        cert_title = (
            candidate.certificate_title_override or
            (program.certificate_title if program else None) or
            cls._default_title_for_template(cert_template)
        )

        # 5. Certificate Subtitle
        cert_subtitle = (
            (program.certificate_subtitle if program else None) or ""
        )

        # 6. Partner ("In Association With")
        partner = (
            candidate.certificate_partner or
            (program.certificate_partner if program else None) or
            candidate.training_location or
            candidate.college_name or
            ""
        ).strip()

        # 7. Topics Covered
        topics = (
            candidate.certificate_topics or
            (program.certificate_topics if program else None) or
            candidate.programme_domain or
            course_details.get("topics") or
            "Professional Development, Advanced Concepts, and Practical Applications"
        ).strip()

        # 8. Domain
        domain = (
            candidate.certificate_domain or
            (program.certificate_domain if program else None) or
            candidate.programme_domain or
            course_details.get("domain") or
            "Technology & Professional Studies"
        ).strip()

        # 9. Mode & Duration
        mode = (
            candidate.certificate_mode or
            candidate.mode_of_learning or
            (program.certificate_default_mode if program else None) or
            (program.mode if program else None) or
            "Online"
        )

        duration = (
            candidate.certificate_duration or
            candidate.course_duration or
            (program.certificate_duration if program else None) or
            (program.duration if program else None) or
            "4 Weeks"
        )

        # 10. Dates
        comp_date = candidate.certificate_completion_date or candidate.completed_at or datetime.utcnow()
        issue_date = candidate.certificate_issue_date or comp_date
        
        day_suffix = get_ordinal_suffix(comp_date.day)
        completion_date_str = f"{comp_date.day}{day_suffix} {comp_date.strftime('%B %Y')}"
        issue_date_str = issue_date.strftime("%d %B %Y")
        start_date_str = candidate.course_start_date.strftime("%d/%m/%Y") if candidate.course_start_date else comp_date.strftime("%d/%m/%Y")

        # 11. Signatory Info
        signatory_name = (
            (program.certificate_signatory_name if program else None) or
            "Anju Muraleedharan"
        )
        signatory_title = (
            (program.certificate_signatory_title if program else None) or
            "Managing Partner"
        )

        # 12. Organization
        organization_name = "AgenticX Knowledge Solutions LLP"

        # 13. Pronouns
        pronoun = resolve_pronoun(candidate.gender or "other")

        # 14. Body Paragraph
        body_template = candidate.certificate_body_override or (program.certificate_body_template if program else None)
        if body_template:
            body_text = cls.render_placeholders(body_template, {
                "candidate_name": candidate.full_name,
                "course_name": course_name,
                "program_type": program_type,
                "topics": topics,
                "partner": partner,
                "organization": organization_name,
                "completion_date": completion_date_str,
                "issue_date": issue_date_str,
                "pronoun": pronoun["subject"],
                "duration": duration,
                "mode": mode,
            })
        else:
            body_text = cls._default_body_text(
                cert_template=cert_template,
                recipient_name=candidate.full_name,
                program_type=program_type,
                course_name=course_name,
                organization_name=organization_name,
                partner=partner,
                start_date_str=candidate.course_start_date.strftime("%d %B %Y") if candidate.course_start_date else comp_date.strftime("%d %B %Y"),
                end_date_str=comp_date.strftime("%d %B %Y"),
                completion_date_str=completion_date_str,
                topics=topics,
                pronoun=pronoun
            )

        return {
            "certificateId": candidate.application_number or candidate.certificate_id,
            "issueDate": issue_date_str,
            "recipientName": candidate.full_name,
            "gender": candidate.gender or "other",
            "courseName": course_name,
            "courseTopics": topics,
            "organizationName": organization_name,
            "associationWith": partner,
            "courseMode": mode,
            "courseDuration": duration,
            "courseDomain": domain,
            "startDate": start_date_str,
            "endDate": comp_date.strftime("%d/%m/%Y"),
            "completionDate": completion_date_str,
            "performance": candidate.performance,
            "programType": program_type,
            "certTemplate": cert_template,
            "certTitle": cert_title,
            "certSubtitle": cert_subtitle,
            "bodyText": body_text,
            "signatoryName": signatory_name,
            "signatoryTitle": signatory_title,
            "footerText": (program.certificate_footer if program else None) or "AgenticX Knowledge Solutions",
            "qrEnabled": program.certificate_qr_enabled if program else True,
            "verificationEnabled": program.certificate_verification_enabled if program else True,
        }

    @staticmethod
    def render_placeholders(template_str: str, data_dict: Dict[str, Any]) -> str:
        res = template_str
        for k, v in data_dict.items():
            res = res.replace(f"{{{k}}}", str(v or ""))
        return res

    @staticmethod
    def _default_title_for_template(cert_template: str) -> str:
        if cert_template == "participation":
            return "CERTIFICATE OF PARTICIPATION"
        elif cert_template == "achievement":
            return "CERTIFICATE OF ACHIEVEMENT"
        elif cert_template == "appreciation":
            return "CERTIFICATE OF APPRECIATION"
        return "CERTIFICATE OF COMPLETION"

    @staticmethod
    def _default_body_text(cert_template: str, recipient_name: str, program_type: str, course_name: str,
                           organization_name: str, partner: str, start_date_str: str, end_date_str: str,
                           completion_date_str: str, topics: str, pronoun: dict) -> str:
        assoc_str = f" in association with <b>{partner}</b>" if partner else ""
        if cert_template == "participation":
            prog_name_str = f"<b>{program_type}</b> on " if program_type and program_type.lower() != "course" else ""
            return (
                f"This is to certify that <b>{recipient_name}</b> has successfully participated in the "
                f"{prog_name_str}<b>{course_name}</b> organized by <b>{organization_name}</b>{assoc_str} held from "
                f"<b>{start_date_str}</b> to <b>{end_date_str}</b>. We appreciate your active participation and "
                f"wish you continued success in your academic and professional journey."
            )
        elif cert_template == "fdp":
            fdp_topic = (topics or course_name or "Faculty Development Programme").strip()
            fdp_text = f"Faculty Development Programme on {fdp_topic}" if not fdp_topic.lower().startswith("faculty development") else fdp_topic
            return (
                f"This is to certify that <b>{recipient_name}</b> has successfully completed the "
                f"<b>{fdp_text}</b> organized by <b>{organization_name}</b>{assoc_str} on <b>{completion_date_str}</b>. "
                f"{pronoun['subject']} actively participated throughout the "
                f"program with full dedication and demonstrated a strong commitment to learning."
            )
        elif cert_template == "appreciation":
            pos_pronoun = pronoun['possessive'].lower()
            return (
                f"This certificate is proudly presented to<br/>"
                f"<font size=\"14.5\"><b>{recipient_name}</b></font><br/><br/>"
                f"in recognition and appreciation of {pos_pronoun} valuable contribution as a "
                f"<b>Faculty / Resource Person / Mentor</b> for the <b>{course_name}</b>, conducted by "
                f"<b>{organization_name}</b>.<br/><br/>"
                f"The programme was conducted from <b>{start_date_str} to {end_date_str}</b>, during which the faculty member "
                f"shared {pos_pronoun} knowledge, expertise, and practical insights in the areas of <b>{topics}</b>.<br/><br/>"
                f"We sincerely appreciate {pos_pronoun} dedication, expertise, and valuable contribution towards making the programme "
                f"meaningful and enriching for all participants."
            )
        else:
            prog_title = f"<b>{program_type}</b> on <b>{course_name}</b>" if program_type and program_type.lower() != "course" else f"<b>{course_name}</b>"
            return (
                f"This is to certify that <b>{recipient_name}</b> has successfully completed the "
                f"{prog_title}, covering {topics} at <b>{organization_name}</b>{assoc_str} "
                f"on <b>{completion_date_str}</b>. {pronoun['subject']} actively participated throughout the "
                f"program with full dedication and demonstrated a strong commitment to learning."
            )


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

        # Fetch linked program model if present
        from sqlalchemy import select
        from app.models.program import Program
        db_program = None
        if candidate.program_id:
            res_p = await db.execute(select(Program).where(Program.id == candidate.program_id))
            db_program = res_p.scalar_one_or_none()

        # Resolve all certificate metadata via CertificateMetadataResolver
        data = CertificateMetadataResolver.resolve_all(candidate, db_program)

        # Generate signed JWT token (No expiry!)
        token = create_certificate_token(candidate.certificate_id)

        # Generate verification URL
        verification_url = f"{settings.CERTIFICATE_FRONTEND_URL.rstrip('/')}/verify?token={token}"

        # Draw PDF using ReportLab in-memory
        pdf_buffer = io.BytesIO()

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
        title = data["certTitle"]
        c.drawCentredString(width / 2, title_y, title)

        c.setFillColor(TEAL)
        tw = c.stringWidth(title, "Helvetica-Bold", 19)
        c.setLineWidth(1.6)
        c.line(width / 2 - tw / 2.6, title_y - 4 * mm, width / 2 + tw / 2.6, title_y - 4 * mm)

        # ===================== Body paragraph =====================
        body_y = title_y - 16 * mm
        body = data["bodyText"]

        from reportlab.platypus import Paragraph
        from reportlab.lib.styles import ParagraphStyle

        body_align = 1 if data.get("certTemplate") == "appreciation" else 0
        body_style = ParagraphStyle(
            'CertBody',
            fontName='Helvetica',
            fontSize=11,
            leading=15.5,
            textColor=DARK_TEXT,
            alignment=body_align
        )
        p = Paragraph(body, body_style)
        pw, ph = p.wrap(content_w, 100 * mm)
        p.drawOn(c, margin, body_y - ph)
        y = body_y - ph

        # ===================== Course/Program Details panel =====================
        panel_top = y - 6 * mm
        if data.get("certTemplate") == "appreciation":
            detail_rows = [
                ("Programme Duration", f"{data['startDate']} – {data['endDate']}"),
                ("Faculty / Resource Person", data["recipientName"]),
            ]
        else:
            detail_rows = [
                ("Program", data["programType"]),
                ("Organization", data["organizationName"]),
            ]
            if data.get("associationWith"):
                detail_rows.append(("In Association With", data["associationWith"]))
            detail_rows.extend([
                ("Mode", data["courseMode"]),
                ("Duration & Hours", data["courseDuration"]),
                ("Topics Covered", data["courseTopics"]),
                ("Start Date", data["startDate"]),
                ("End Date", data["endDate"]),
            ])

        label_w = 38 * mm
        row_leading = 6 * mm
        pad = 6 * mm

        # estimate panel height by laying out text first into a buffer
        temp_y = panel_top - pad
        row_heights = []
        for label, value in detail_rows:
            font_to_use = "Helvetica-Bold" if label == "In Association With" else "Helvetica"
            c.setFont(font_to_use, 10)
            lines_needed = 1
            words = value.split(" ")
            line = ""
            for word in words:
                test = f"{line} {word}".strip()
                if c.stringWidth(test, font_to_use, 10) <= (content_w - label_w - pad * 2):
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
        details_title = "Programme Details" if data.get("certTemplate") == "appreciation" else (f"{data['programType']} Details" if data.get("programType") else "Course Details")
        c.drawString(margin + pad, cy, details_title)
        cy -= 8 * mm

        for label, value in detail_rows:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(NAVY_SOFT)
            c.drawString(margin + pad, cy, f"{label}:")
            value_font = "Helvetica-Bold" if label == "In Association With" else "Helvetica"
            wrapped_end = draw_wrapped_text(
                c, value,
                margin + pad + label_w, cy + 0.1 * mm,
                content_w - label_w - pad * 2,
                font=value_font, size=10, leading=row_leading, color=DARK_TEXT,
            )
            # advance cy by however many lines were used
            lines_used = round((cy - wrapped_end) / row_leading)
            cy -= max(lines_used, 1) * row_leading

        y = panel_top - panel_height - 10 * mm

        # ===================== Performance remark =====================
        if data.get("certTemplate") not in ("participation", "fdp", "appreciation") and data.get("performance"):
            c.setFont("Helvetica", 11)
            c.setFillColor(DARK_TEXT)
            perf_line = "Performance during the period was "
            c.drawString(margin, y, perf_line)
            pcw = c.stringWidth(perf_line, "Helvetica", 11)
            c.setFont("Helvetica-Bold", 11)
            c.setFillColor(TEAL)
            perf_val = data["performance"].strip().capitalize()
            c.drawString(margin + pcw, y, f"{perf_val}.")
            y -= 8 * mm

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

        # Draw digital signature
        sig_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "signature.png")
        try:
            sig_img = ImageReader(sig_path)
            c.drawImage(
                sig_img,
                sig_x + 10 * mm,
                45 * mm,
                width=35 * mm,
                height=12 * mm,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception as e:
            logger.error(f"Failed to render digital signature: {e}")

        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.8)
        c.line(sig_x, 44 * mm, sig_x + 56 * mm, 44 * mm)

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(NAVY)
        c.drawString(sig_x, 39 * mm, data.get("signatoryName", "Anju Muraleedharan"))
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(sig_x, 34.5 * mm, data.get("signatoryTitle", "Managing Partner"))

        # ===================== Footer =====================
        c.setStrokeColor(TEAL)
        c.setLineWidth(1.2)
        c.line(margin, 18 * mm, width - margin, 18 * mm)
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(margin, 13 * mm, data.get("footerText", "AgenticX Knowledge Solutions"))
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

    @staticmethod
    async def regenerate_certificate(db: AsyncSession, candidate: CandidateApplication) -> CandidateApplication:
        """Regenerates the certificate. If a certificate exists, it hard deletes it from storage first."""
        uploader = CertificateUploadService()
        if candidate.certificate_url:
            try:
                await uploader.delete_file(candidate.certificate_url)
                logger.info(f"Deleted existing certificate file {candidate.certificate_url} for candidate {candidate.id}")
            except Exception as e:
                logger.warning(f"Failed to delete existing certificate file for candidate {candidate.id}: {e}")

        # Reset certificate status
        candidate.certificate_url = None
        candidate.certificate_status = "pending"
        
        # Generate new one
        return await CertificateService.generate_and_save_certificate(db, candidate)


certificate_service = CertificateService()
