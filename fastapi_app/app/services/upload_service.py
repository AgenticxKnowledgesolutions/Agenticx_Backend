import uuid
import httpx
from fastapi import HTTPException, status
from app.core.config import settings

class UploadService:
    def __init__(self):
        self.supabase_url = settings.SUPABASE_URL.rstrip("/")
        self.service_key = settings.SUPABASE_SERVICE_KEY
        self.bucket_name = "uploads"
        
        self.headers = {
            "Authorization": f"Bearer {self.service_key}"
        }

    async def ensure_bucket_exists(self) -> None:
        """Checks if the uploads storage bucket exists, and creates it if not."""
        async with httpx.AsyncClient() as client:
            try:
                # Check if bucket exists
                res = await client.get(
                    f"{self.supabase_url}/storage/v1/bucket/{self.bucket_name}",
                    headers=self.headers
                )
                if res.status_code == 200:
                    return
                
                # If not, create it
                create_res = await client.post(
                    f"{self.supabase_url}/storage/v1/bucket",
                    headers=self.headers,
                    json={
                        "id": self.bucket_name,
                        "name": self.bucket_name,
                        "public": True
                    }
                )
                if create_res.status_code not in (200, 409):
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to initialize Supabase storage bucket: {create_res.text}"
                    )
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage service connection error: {str(e)}"
                )

    async def upload_file(self, file_content: bytes, folder: str, original_filename: str, mime_type: str) -> str:
        """
        Uploads raw file bytes to Supabase Storage in the specified folder,
        returning the public access URL.
        """
        # Ensure bucket is initialized
        await self.ensure_bucket_exists()

        # Sanitize filename and make it unique
        ext = original_filename.split(".")[-1] if "." in original_filename else ""
        unique_name = f"{uuid.uuid4().hex}"
        if ext:
            unique_name = f"{unique_name}.{ext}"

        file_path = f"{folder.strip('/')}/{unique_name}"

        # Upload request
        async with httpx.AsyncClient() as client:
            try:
                res = await client.put(
                    f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{file_path}",
                    headers={
                        **self.headers,
                        "Content-Type": mime_type
                    },
                    content=file_content,
                    timeout=30.0
                )
                if res.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Supabase Storage Upload failed: {res.text}"
                    )
                
                # Return the public access URL
                return f"{self.supabase_url}/storage/v1/object/public/{self.bucket_name}/{file_path}"
            except httpx.HTTPError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage upload request failed: {str(e)}"
                )

    async def delete_file(self, file_path_or_url: str) -> bool:
        """
        Deletes a file from Supabase Storage.
        Accepts either the full public URL or the relative file path.
        """
        if not file_path_or_url:
            return False

        bucket_name = self.bucket_name
        file_path = file_path_or_url
        
        # Extract bucket and path from public URL if present
        if "/storage/v1/object/public/" in file_path_or_url:
            try:
                parts = file_path_or_url.split("/storage/v1/object/public/", 1)
                if len(parts) > 1:
                    path_parts = parts[1].split("/", 1)
                    if len(path_parts) > 1:
                        bucket_name = path_parts[0]
                        file_path = path_parts[1]
            except Exception as e:
                print(f"Failed to parse Supabase URL {file_path_or_url}: {e}")

        file_path = file_path.strip("/")

        async with httpx.AsyncClient() as client:
            try:
                res = await client.delete(
                    f"{self.supabase_url}/storage/v1/object/{bucket_name}/{file_path}",
                    headers=self.headers
                )
                return res.status_code == 200
            except Exception as e:
                print(f"Failed to delete file {file_path} from bucket {bucket_name}: {e}")
                return False

upload_service = UploadService()
