import io
import os
import logging
from datetime import datetime
from typing import Optional, List, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func

from app.models.faculty_certificate import FacultyCertificate
from app.schemas.faculty_certificate import FacultyCertificateCreate, FacultyCertificateUpdate
from app.services.upload_service import UploadService

# ReportLab imports for certificate generation
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

logger = logging.getLogger(__name__)

# Design System Colors
NAVY = HexColor("#16263F")
NAVY_SOFT = HexColor("#3C5478")
TEAL = HexColor("#1F9C9C")
TEAL_LIGHT = HexColor("#E7F6F6")
DARK_TEXT = HexColor("#262B33")
GREY_TEXT = HexColor("#6B7280")
HAIRLINE = HexColor("#D8DEE6")


class FacultyCertificateUploadService(UploadService):
    def __init__(self):
        super().__init__()
        self.bucket_name = "certificates"

    async def upload_faculty_certificate(self, file_content: bytes, cert_id: str) -> str:
        """Uploads faculty certificate PDF directly to faculty_certificates/{cert_id}.pdf in certificates bucket."""
        await self.ensure_bucket_exists()
        file_path = f"faculty_certificates/{cert_id}.pdf"

        import httpx
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
                        detail=f"Supabase Storage Faculty Upload failed: {res.text}"
                    )
                return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{file_path}"
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage upload request failed: {str(e)}"
                )


class FacultyCertificateService:
    @classmethod
    async def create_certificate(cls, db: AsyncSession, payload: FacultyCertificateCreate) -> FacultyCertificate:
        """Creates a new Faculty FDP Certificate in Draft state."""
        current_year = datetime.now().year
        prefix = f"FDP-{current_year}-"
        
        stmt = select(func.count(FacultyCertificate.id)).where(FacultyCertificate.certificate_number.like(f"{prefix}%"))
        res = await db.execute(stmt)
        count = res.scalar() or 0
        cert_number = f"{prefix}{count + 1:05d}"

        cert = FacultyCertificate(
            certificate_number=cert_number,
            faculty_name=payload.faculty_name,
            faculty_email=payload.faculty_email,
            designation=payload.designation,
            organization=payload.organization,
            programme_title=payload.programme_title,
            topic=payload.topic,
            start_date=payload.start_date,
            end_date=payload.end_date,
            duration=payload.duration,
            mode=payload.mode,
            description=payload.description,
            organization_name=payload.organization_name,
            signatory_name=payload.signatory_name,
            signatory_designation=payload.signatory_designation,
            status="Draft"
        )
        db.add(cert)
        await db.commit()
        await db.refresh(cert)
        return cert

    @classmethod
    async def get_certificate(cls, db: AsyncSession, cert_id: str) -> FacultyCertificate:
        """Retrieves a single certificate or raises 404."""
        stmt = select(FacultyCertificate).where(FacultyCertificate.id == cert_id)
        res = await db.execute(stmt)
        cert = res.scalar_one_or_none()
        if not cert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Faculty Certificate with ID {cert_id} not found."
            )
        return cert

    @classmethod
    async def update_certificate(cls, db: AsyncSession, cert_id: str, payload: FacultyCertificateUpdate) -> FacultyCertificate:
        """Updates a certificate. Resets status back to Draft so it must be regenerated to sync the PDF."""
        cert = await cls.get_certificate(db, cert_id)
        
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(cert, k, v)
        
        cert.status = "Draft"  # Invalidate previous PDF URL to enforce regeneration
        await db.commit()
        await db.refresh(cert)
        return cert

    @classmethod
    async def list_certificates(cls, db: AsyncSession, search: Optional[str] = None) -> List[FacultyCertificate]:
        """Lists all faculty certificates, with optional search filter."""
        stmt = select(FacultyCertificate)
        if search:
            q = f"%{search}%"
            stmt = stmt.where(
                or_(
                    FacultyCertificate.faculty_name.ilike(q),
                    FacultyCertificate.programme_title.ilike(q),
                    FacultyCertificate.certificate_number.ilike(q)
                )
            )
        res = await db.execute(stmt.order_by(FacultyCertificate.created_at.desc()))
        return list(res.scalars().all())

    @classmethod
    async def delete_certificate(cls, db: AsyncSession, cert_id: str) -> None:
        """Deletes a certificate and removes its PDF from Supabase storage if it exists."""
        cert = await cls.get_certificate(db, cert_id)
        
        if cert.certificate_url:
            uploader = FacultyCertificateUploadService()
            try:
                await uploader.delete_file(cert.certificate_url)
            except Exception as e:
                logger.warning(f"Failed to delete storage file {cert.certificate_url}: {e}")

        await db.delete(cert)
        await db.commit()

    @classmethod
    def generate_pdf_bytes(cls, cert: FacultyCertificate) -> bytes:
        """Draws the Faculty FDP appreciation certificate PDF using ReportLab."""
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        width, height = A4
        margin = 22 * mm
        content_w = width - 2 * margin

        # ===================== Top Accent Bar =====================
        c.setFillColor(NAVY)
        c.rect(0, height - 4 * mm, width, 4 * mm, fill=1, stroke=0)
        c.setFillColor(TEAL)
        c.rect(0, height - 4 * mm, width * 0.32, 4 * mm, fill=1, stroke=0)

        # ===================== Header =====================
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

        # ===================== Metadata Row =====================
        meta_y = rule_y - 7 * mm
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(margin, meta_y, f"Certificate No: {cert.certificate_number}")
        
        issue_date_str = datetime.now().strftime("%d %B %Y")
        c.drawRightString(width - margin, meta_y, f"Date of Issue: {issue_date_str}")

        # ===================== Title =====================
        title_y = meta_y - 14 * mm
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 19)
        title = "CERTIFICATE OF APPRECIATION"
        c.drawCentredString(width / 2, title_y, title)

        c.setFillColor(TEAL)
        tw = c.stringWidth(title, "Helvetica-Bold", 19)
        c.setLineWidth(1.6)
        c.line(width / 2 - tw / 2.6, title_y - 4 * mm, width / 2 + tw / 2.6, title_y - 4 * mm)

        # ===================== Body Paragraph =====================
        body_y = title_y - 16 * mm
        
        start_date_str = cert.start_date.strftime("%d %B %Y")
        end_date_str = cert.end_date.strftime("%d %B %Y")
        
        body_text = (
            f"This certificate is proudly presented to<br/>"
            f"<font size=\"14.5\"><b>{cert.faculty_name}</b></font><br/><br/>"
            f"in recognition and appreciation of their valuable contribution as a "
            f"<b>Faculty / Trainer / Mentor</b> for the <b>{cert.programme_title}</b>, conducted by "
            f"<b>{cert.organization_name}</b>.<br/><br/>"
            f"The programme was conducted from <b>{start_date_str} to {end_date_str}</b>, during which the faculty member "
            f"shared their knowledge, expertise, and practical insights in the areas of <b>{cert.topic}</b>.<br/><br/>"
            f"We sincerely appreciate their dedication, expertise, and valuable contribution towards making the programme "
            f"meaningful and enriching for all participants."
        )

        body_style = ParagraphStyle(
            'FacultyCertBody',
            fontName='Helvetica',
            fontSize=11,
            leading=15.5,
            textColor=DARK_TEXT,
            alignment=1  # Centered
        )
        p = Paragraph(body_text, body_style)
        pw, ph = p.wrap(content_w, 100 * mm)
        p.drawOn(c, margin, body_y - ph)
        y = body_y - ph

        # ===================== Program Details Box =====================
        panel_top = y - 8 * mm
        detail_rows = [
            ("Programme Duration", f"{start_date_str} – {end_date_str}"),
            ("Faculty / Resource Person", cert.faculty_name),
            ("Topic Focus Area", cert.topic),
            ("Program Duration", cert.duration),
        ]
        if cert.mode:
            detail_rows.append(("Training Mode", cert.mode))

        label_w = 48 * mm
        row_leading = 6 * mm
        pad = 6 * mm

        # Estimate panel height
        row_heights = []
        for label, val in detail_rows:
            c.setFont("Helvetica", 10)
            lines_needed = 1
            words = val.split(" ")
            line = ""
            for w in words:
                test = f"{line} {w}".strip()
                if c.stringWidth(test, "Helvetica", 10) <= (content_w - label_w - pad * 2):
                    line = test
                else:
                    lines_needed += 1
                    line = w
            row_heights.append(lines_needed)
        panel_height = pad * 2 + sum(h * row_leading for h in row_heights) + 8 * mm

        # Round Rect Background
        c.setFillColor(TEAL_LIGHT)
        c.roundRect(margin, panel_top - panel_height, content_w, panel_height, 2.5 * mm, fill=1, stroke=0)
        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.6)
        c.roundRect(margin, panel_top - panel_height, content_w, panel_height, 2.5 * mm, fill=0, stroke=1)

        # Title of details block
        cy = panel_top - pad - 2 * mm
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin + pad, cy, "Programme & Contribution Details")
        cy -= 8 * mm

        # Draw details content rows
        for label, val in detail_rows:
            c.setFont("Helvetica-Bold", 9.5)
            c.setFillColor(NAVY_SOFT)
            c.drawString(margin + pad, cy, f"{label}:")
            
            c.setFont("Helvetica", 10)
            c.setFillColor(DARK_TEXT)
            
            # Draw wrapped text
            words = val.split(" ")
            lines = []
            line = ""
            for w in words:
                test_line = f"{line} {w}".strip()
                if c.stringWidth(test_line, "Helvetica", 10) <= (content_w - label_w - pad * 2):
                    line = test_line
                else:
                    lines.append(line)
                    line = w
            if line:
                lines.append(line)

            sub_cy = cy
            for ln in lines:
                c.drawString(margin + pad + label_w, sub_cy, ln)
                sub_cy -= row_leading
            
            lines_used = len(lines)
            cy -= max(lines_used, 1) * row_leading

        # ===================== Signature Block =====================
        sig_x = width - margin - 60 * mm
        c.setFont("Helvetica-Oblique", 11)
        c.setFillColor(DARK_TEXT)
        c.drawString(sig_x, 56 * mm, "Sincerely,")

        # Draw digital signature image
        sig_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "signature.png")
        try:
            sig_img = ImageReader(sig_path)
            c.drawImage(
                sig_img,
                sig_x + 10 * mm,
                43 * mm,
                width=35 * mm,
                height=12 * mm,
                mask="auto",
                preserveAspectRatio=True,
            )
        except Exception as e:
            logger.error(f"Failed to render signature: {e}")

        c.setStrokeColor(HAIRLINE)
        c.setLineWidth(0.8)
        c.line(sig_x, 42 * mm, sig_x + 56 * mm, 42 * mm)

        signatory_n = cert.signatory_name or "Anju Muraleedharan"
        signatory_d = cert.signatory_designation or "Managing Partner"

        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(NAVY)
        c.drawString(sig_x, 37 * mm, signatory_n)
        
        c.setFont("Helvetica", 9.5)
        c.setFillColor(GREY_TEXT)
        c.drawString(sig_x, 32.5 * mm, signatory_d)

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

        return pdf_buffer.getvalue()

    @classmethod
    async def generate_and_save_certificate(cls, db: AsyncSession, cert_id: str) -> FacultyCertificate:
        """Generates the certificate PDF, uploads it, and sets status to 'Generated'."""
        cert = await cls.get_certificate(db, cert_id)

        pdf_bytes = cls.generate_pdf_bytes(cert)

        uploader = FacultyCertificateUploadService()
        public_url = await uploader.upload_faculty_certificate(pdf_bytes, cert.id)

        cert.certificate_url = public_url
        cert.status = "Generated"
        cert.generated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(cert)
        return cert
