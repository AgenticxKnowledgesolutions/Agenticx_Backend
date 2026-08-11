import base64
from fastapi import APIRouter, Depends, status, Response, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.schemas.faculty_certificate import (
    FacultyCertificateCreate,
    FacultyCertificateUpdate,
    FacultyCertificateResponse
)
from app.services.faculty_certificate_service import FacultyCertificateService

router = APIRouter(prefix="/admin/certificates/fdp", tags=["faculty-certificates"])


@router.get("", response_model=List[FacultyCertificateResponse])
async def list_faculty_certificates(
    search: Optional[str] = Query(None, description="Search by faculty name or program title"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: List all faculty certificates with search filter."""
    return await FacultyCertificateService.list_certificates(db, search=search)


@router.post("", response_model=FacultyCertificateResponse, status_code=status.HTTP_201_CREATED)
async def create_faculty_certificate(
    payload: FacultyCertificateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Create a new draft faculty certificate."""
    return await FacultyCertificateService.create_certificate(db, payload)


@router.get("/{id}", response_model=FacultyCertificateResponse)
async def get_faculty_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Get details of a single faculty certificate."""
    return await FacultyCertificateService.get_certificate(db, id)


@router.put("/{id}", response_model=FacultyCertificateResponse)
async def update_faculty_certificate(
    id: str,
    payload: FacultyCertificateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Update an existing faculty certificate (resets status to Draft)."""
    return await FacultyCertificateService.update_certificate(db, id, payload)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faculty_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Delete a faculty certificate and its associated storage file."""
    await FacultyCertificateService.delete_certificate(db, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{id}/preview")
async def preview_faculty_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Generate and return a live PDF preview stream of the certificate."""
    cert = await FacultyCertificateService.get_certificate(db, id)
    pdf_bytes = FacultyCertificateService.generate_pdf_bytes(cert)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="preview_{cert.certificate_number}.pdf"'}
    )


@router.post("/{id}/generate", response_model=FacultyCertificateResponse)
async def generate_faculty_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Generate the PDF, upload it to storage, and mark the status as Generated."""
    return await FacultyCertificateService.generate_and_save_certificate(db, id)


@router.get("/{id}/download")
async def download_faculty_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Download the generated certificate PDF file."""
    cert = await FacultyCertificateService.get_certificate(db, id)
    if not cert.certificate_url or cert.status != "Generated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate PDF has not been generated yet. Please generate it first."
        )

    # Re-generate pdf bytes locally to return as attachment download directly
    pdf_bytes = FacultyCertificateService.generate_pdf_bytes(cert)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{cert.certificate_number}.pdf"'}
    )
