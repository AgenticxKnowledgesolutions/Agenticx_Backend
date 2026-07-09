from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Query, status
from app.deps import require_admin
from app.models.user import User
from app.services.upload_service import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_IMAGE_FOLDERS = {"courses/thumbnails", "activities/banners", "reviews", "team", "blogs", "collaborators"}

ALLOWED_PDF_EXTENSIONS = {"pdf"}
ALLOWED_PDF_MIMES = {"application/pdf"}
ALLOWED_PDF_FOLDERS = {"courses/brochures", "company-settings/brochures"}

# Size limits
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_PDF_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/image", status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    folder: str = Query(..., description="Target upload folder"),
    _: User = Depends(require_admin)
):
    # Validate folder
    if folder not in ALLOWED_IMAGE_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target folder. Must be one of: {', '.join(ALLOWED_IMAGE_FOLDERS)}"
        )

    # Validate file extension and MIME type
    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_IMAGE_EXTENSIONS or file.content_type not in ALLOWED_IMAGE_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported image format. Allowed formats: JPG, JPEG, PNG, WEBP."
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file size exceeds the 5MB maximum limit."
        )

    # Perform upload
    public_url = await upload_service.upload_file(
        file_content=content,
        folder=folder,
        original_filename=filename,
        mime_type=file.content_type
    )

    return {"success": True, "url": public_url}


@router.post("/pdf", status_code=status.HTTP_201_CREATED)
async def upload_pdf(
    file: UploadFile = File(...),
    folder: str = Query(..., description="Target upload folder"),
    _: User = Depends(require_admin)
):
    # Validate folder
    if folder not in ALLOWED_PDF_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid target folder. Must be one of: {', '.join(ALLOWED_PDF_FOLDERS)}"
        )

    # Validate file extension and MIME type
    filename = file.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_PDF_EXTENSIONS or file.content_type not in ALLOWED_PDF_MIMES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported document format. Allowed format: PDF."
        )

    # Read and validate size
    content = await file.read()
    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF file size exceeds the 20MB maximum limit."
        )

    # Perform upload
    public_url = await upload_service.upload_file(
        file_content=content,
        folder=folder,
        original_filename=filename,
        mime_type=file.content_type
    )

    return {"success": True, "url": public_url}
