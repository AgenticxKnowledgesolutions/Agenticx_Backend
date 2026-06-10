import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

def test_rate_limiting_lead_submission():
    """
    Test that the lead submission endpoint is rate limited:
    - First 5 requests should succeed (HTTP 201).
    - 6th request should fail with HTTP 429 and the custom details message.
    """
    client = TestClient(app)

    class DummyLead:
        id = "lead_123"
        name = "Test User"
        email = "test@example.com"
        phone = "1234567890"
        message = "Test message"
        interested_course = "AI"
        source_page = "contact"
        status = "Pending"
        admin_notes = None
        last_contacted_at = None
        next_followup_date = None
        followup_notes = None
        source = "Website"
        priority = "Cold"
        assigned_to = None
        created_at = datetime.now(timezone.utc)
        notes = []
        timeline_events = []

    dummy_lead = DummyLead()

    # Reset limiter memory storage for clean test run
    limiter = app.state.limiter
    limiter.reset()

    # Mock lead_service.create_lead to bypass actual database connection operations
    with patch("app.services.lead_service.create_lead", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = dummy_lead
        
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "1234567890",
            "message": "Hello"
        }
        
        # 1. First 5 submissions must succeed with HTTP 201
        for i in range(5):
            response = client.post("/api/v1/leads/", json=payload)
            assert response.status_code == 201, f"Failed on request {i+1}: {response.text}"
            
        # 2. 6th submission must be blocked with HTTP 429 and detail message
        response = client.post("/api/v1/leads/", json=payload)
        assert response.status_code == 429
        assert response.json() == {"detail": "Too many submissions. Please try again later."}
