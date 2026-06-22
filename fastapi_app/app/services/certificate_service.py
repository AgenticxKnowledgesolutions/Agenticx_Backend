import uuid
import urllib.parse
from datetime import datetime
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


# Clean, premium certificate template
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800&family=Playfair+Display:ital,wght@0,600;1,400&display=swap');
  
  @page {
    size: A4 landscape;
    margin: 0;
  }
  
  body {
    margin: 0;
    padding: 0;
    font-family: 'Outfit', sans-serif;
    background-color: #ffffff;
    -webkit-print-color-adjust: exact;
  }
  
  .certificate-container {
    width: 297mm;
    height: 210mm;
    box-sizing: border-box;
    padding: 20mm;
    position: relative;
    background: #ffffff;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
  
  /* Decorative borders */
  .border-outer {
    position: absolute;
    top: 5mm;
    left: 5mm;
    right: 5mm;
    bottom: 5mm;
    border: 1px solid #e2e8f0;
    pointer-events: none;
  }
  
  .border-inner {
    position: absolute;
    top: 8mm;
    left: 8mm;
    right: 8mm;
    bottom: 8mm;
    border: 2px solid #b89047; /* Warm Gold */
    pointer-events: none;
  }
  
  .corner-decor {
    position: absolute;
    width: 15mm;
    height: 15mm;
    border: 4px solid #1e293b; /* Deep Indigo/Slate */
    pointer-events: none;
  }
  .corner-tl { top: 12mm; left: 12mm; border-right: none; border-bottom: none; }
  .corner-tr { top: 12mm; right: 12mm; border-left: none; border-bottom: none; }
  .corner-bl { bottom: 12mm; left: 12mm; border-right: none; border-top: none; }
  .corner-br { bottom: 12mm; right: 12mm; border-left: none; border-top: none; }

  /* Content */
  .header {
    text-align: center;
    margin-top: 5mm;
  }
  
  .logo-text {
    font-size: 24px;
    font-weight: 800;
    color: #1e293b;
    letter-spacing: 2px;
    margin: 0 0 2mm 0;
  }
  
  .subtitle-top {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: #b89047;
    font-weight: 600;
    margin: 0;
  }
  
  .main-content {
    text-align: center;
    margin-top: 10mm;
  }
  
  .cert-title {
    font-family: 'Playfair Display', serif;
    font-size: 40px;
    font-weight: 600;
    color: #1e293b;
    margin: 0 0 5mm 0;
    letter-spacing: 1px;
  }
  
  .cert-to {
    font-size: 14px;
    color: #64748b;
    margin: 0 0 4mm 0;
    font-style: italic;
  }
  
  .candidate-name {
    font-size: 32px;
    font-weight: 800;
    color: #1e293b;
    margin: 0 0 5mm 0;
    border-bottom: 2px solid #f1f5f9;
    display: inline-block;
    padding-bottom: 2mm;
    min-width: 150mm;
  }
  
  .cert-description {
    font-size: 14px;
    color: #475569;
    line-height: 1.6;
    margin: 0 auto;
    max-width: 180mm;
  }
  
  .course-name {
    color: #b89047;
    font-weight: 600;
  }

  .footer {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 5mm;
    padding: 0 10mm;
  }
  
  .signature-block {
    text-align: left;
  }
  
  .signature-line {
    width: 45mm;
    border-top: 1px solid #cbd5e1;
    margin-bottom: 2mm;
  }
  
  .signature-title {
    font-size: 11px;
    font-weight: 600;
    color: #475569;
  }
  
  .signature-org {
    font-size: 10px;
    color: #94a3b8;
  }
  
  .qr-block {
    display: flex;
    align-items: center;
    gap: 4mm;
    text-align: right;
  }
  
  .qr-info {
    display: flex;
    flex-direction: column;
    justify-content: center;
  }
  
  .qr-title {
    font-size: 10px;
    font-weight: 600;
    color: #475569;
    margin: 0;
  }
  
  .qr-id {
    font-size: 8px;
    color: #94a3b8;
    font-family: monospace;
    margin: 1mm 0 0 0;
  }
  
  .qr-code {
    width: 22mm;
    height: 22mm;
    border: 1px solid #e2e8f0;
    padding: 1mm;
    background: #ffffff;
  }
</style>
</head>
<body>
  <div class="certificate-container">
    <div class="border-outer"></div>
    <div class="border-inner"></div>
    <div class="corner-decor corner-tl"></div>
    <div class="corner-decor corner-tr"></div>
    <div class="corner-decor corner-bl"></div>
    <div class="corner-decor corner-br"></div>
    
    <div class="header">
      <h2 class="logo-text">AGENTICX</h2>
      <p class="subtitle-top">Credential Verification Services</p>
    </div>
    
    <div class="main-content">
      <h1 class="cert-title">Certificate of Completion</h1>
      <p class="cert-to">This is proudly presented to</p>
      <div class="candidate-name">{{candidate_name}}</div>
      <p class="cert-description">
        for successfully completing the {{duration_str}}coursework and certification requirements for<br>
        <span class="course-name">{{course_name}}</span><br>
        {{period_str}}.
      </p>
    </div>
    
    <div class="footer">
      <div class="signature-block">
        <div class="signature-line"></div>
        <div class="signature-title">Authorized Signatory</div>
        <div class="signature-org">AgenticX Solutions</div>
      </div>
      
      <div class="qr-block">
        <div class="qr-info">
          <p class="qr-title">Scan to Verify Authenticity</p>
          <p class="qr-id">ID: {{certificate_id}}</p>
        </div>
        <img class="qr-code" src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={{verification_url}}" alt="QR Code" />
      </div>
    </div>
  </div>
</body>
</html>
"""


class CertificateService:
    @staticmethod
    async def generate_and_save_certificate(db: AsyncSession, candidate: CandidateApplication) -> CandidateApplication:
        """Generates the certificate using WeasyPrint, uploads to Supabase and updates candidate DB record."""
        # Lazy import WeasyPrint to keep FastAPI load time light
        from weasyprint import HTML

        # Determine/assign certificate_id if not present
        if not candidate.certificate_id:
            candidate.certificate_id = str(uuid.uuid4())

        # Determine completion date
        comp_date = candidate.completed_at or datetime.utcnow()
        candidate.completed_at = comp_date
        date_str = comp_date.strftime("%B %d, %Y")

        # Format verification URL
        verification_raw_url = f"{settings.FRONTEND_URL.rstrip('/')}/verify/{candidate.certificate_id}"
        verification_encoded_url = urllib.parse.quote_plus(verification_raw_url)

        # Format duration string (e.g. "3-Month " or "intensive ")
        if candidate.course_duration:
            duration_str = f"{candidate.course_duration.strip()} "
        else:
            duration_str = ""

        # Format period string (from X to Y or completed on Z)
        if candidate.course_start_date:
            start_str = candidate.course_start_date.strftime("%B %d, %Y")
            end_str = comp_date.strftime("%B %d, %Y")
            period_str = f"conducted from <span style=\"font-weight: 600; color: #1e293b;\">{start_str}</span> to <span style=\"font-weight: 600; color: #1e293b;\">{end_str}</span>"
        else:
            period_str = f"on this date <span style=\"font-weight: 600; color: #1e293b;\">{date_str}</span>"

        # Inject details into template
        course = candidate.course_applied or "Professional Certification Program"
        html_content = (
            HTML_TEMPLATE.replace("{{candidate_name}}", candidate.full_name)
            .replace("{{course_name}}", course)
            .replace("{{duration_str}}", duration_str)
            .replace("{{period_str}}", period_str)
            .replace("{{certificate_id}}", candidate.certificate_id)
            .replace("{{verification_url}}", verification_encoded_url)
        )

        try:
            # Generate PDF bytes in-memory using WeasyPrint
            pdf_bytes = HTML(string=html_content).write_pdf()

            # Upload to Supabase Storage
            uploader = CertificateUploadService()
            public_url = await uploader.upload_certificate(pdf_bytes, candidate.id)

            # Update candidate attributes
            candidate.certificate_url = public_url
            candidate.certificate_status = "generated"
            candidate.updated_at = datetime.utcnow()
            
            return candidate
        except Exception as e:
            # Re-raise as HTTP 500 error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Certificate generation or storage upload failed: {str(e)}"
            )


certificate_service = CertificateService()
