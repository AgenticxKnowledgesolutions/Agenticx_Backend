import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.candidates import require_admin
from app.deps import require_admin as require_admin_dep

# Mock user for admin authentication bypass
class MockUser:
    id = "admin_user_id"
    email = "admin@example.com"
    role = "admin"

@pytest.fixture
def client():
    # Override admin authentication dependencies
    app.dependency_overrides[require_admin_dep] = lambda: MockUser()
    app.dependency_overrides[require_admin] = lambda: MockUser()
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_bulk_permanent_delete(client):
    with patch("app.services.candidate_service.CandidateService.bulk_hard_delete_applications", new_callable=AsyncMock) as mock_delete:
        mock_delete.return_value = 3
        
        payload = {"candidate_ids": ["c1", "c2", "c3"]}
        response = client.request("DELETE", "/api/v1/candidates/permanent", json=payload)
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "Permanently deleted 3" in response.json()["detail"]
        mock_delete.assert_called_once()

def test_bulk_regenerate_certificates(client):
    with patch("app.services.candidate_service.CandidateService.bulk_regenerate_certificates", new_callable=AsyncMock) as mock_bulk_regen:
        mock_bulk_regen.return_value = {
            "processed": 2,
            "success_count": 2,
            "failed_count": 0,
            "results": [{"id": "c1", "success": True}, {"id": "c2", "success": True}]
        }
        
        payload = {"candidate_ids": ["c1", "c2"]}
        response = client.post("/api/v1/candidates/bulk-regenerate-certificates", json=payload)
        
        assert response.status_code == 200
        assert response.json()["processed"] == 2
        assert response.json()["success_count"] == 2
        mock_bulk_regen.assert_called_once()

def test_single_regenerate_certificate(client):
    class MockCandidate:
        id = "c1"
        application_status = "Completed"
        certificate_url = "http://example.com/cert.pdf"
        certificate_id = "cert_123"

    with patch("app.services.candidate_service.CandidateService.get_application_by_id", new_callable=AsyncMock) as mock_get, \
         patch("app.services.certificate_service.certificate_service.regenerate_certificate", new_callable=AsyncMock) as mock_regen, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.refresh", new_callable=AsyncMock) as mock_refresh, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock) as mock_commit:
        
        candidate = MockCandidate()
        mock_get.return_value = candidate
        mock_regen.return_value = candidate
        
        response = client.post("/api/v1/candidates/c1/regenerate-certificate")
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["certificate_url"] == "http://example.com/cert.pdf"
        mock_get.assert_called_once()
        mock_regen.assert_called_once()

def test_bulk_soft_delete(client):
    with patch("app.services.candidate_service.CandidateService.bulk_soft_delete_applications", new_callable=AsyncMock) as mock_trash:
        mock_trash.return_value = 3
        
        payload = {"candidate_ids": ["c1", "c2", "c3"]}
        response = client.post("/api/v1/candidates/bulk-trash", json=payload)
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["detail"] == "Successfully moved 3 candidates to trash."
        mock_trash.assert_called_once()
