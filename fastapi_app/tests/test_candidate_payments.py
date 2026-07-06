import pytest
import hmac
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.deps import get_current_candidate as get_current_candidate_dep
from app.models.candidate_application import CandidateApplication
from app.models.candidate_payment import CandidatePayment

class MockCandidate:
    id = "mock_candidate_id"
    email = "candidate@example.com"
    full_name = "Mock Candidate"
    phone = "9876543210"
    application_status = "Qualified"
    is_deleted = False
    standard_course_fee = 10000.0
    scholarship_amount = 2000.0
    special_discount = 0.0
    corporate_discount = 0.0
    promo_discount = 0.0
    booking_amount = 0.0
    final_payable_amount = 8000.0
    admission_fee_amount = 250.0
    admission_fee_paid = False
    auto_enroll_enabled = True
    offer_expiry_date = None
    payments = []

@pytest.fixture
def client():
    app.dependency_overrides[get_current_candidate_dep] = lambda: MockCandidate()
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_create_order_rejected_candidate(client):
    candidate = MockCandidate()
    candidate.application_status = "Rejected"
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = candidate
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_res
        
        payload = {"amount": 1000, "payment_type": "Installment"}
        response = client.post("/api/v1/candidates/portal/payments/create-order", json=payload)
        
        assert response.status_code == 400
        assert "rejected" in response.json()["detail"].lower()

def test_create_order_expired_offer(client):
    candidate = MockCandidate()
    candidate.offer_expiry_date = datetime.now() - timedelta(days=1)
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = candidate
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_res
        
        payload = {"amount": 1000, "payment_type": "Installment"}
        response = client.post("/api/v1/candidates/portal/payments/create-order", json=payload)
        
        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()

def test_create_order_exceed_balance(client):
    candidate = MockCandidate()
    candidate.final_payable_amount = 5000.0
    
    mock_payment = CandidatePayment(
        id="p1",
        amount=4500.0,
        payment_type="Installment",
        status="Paid"
    )
    candidate.payments = [mock_payment]
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = candidate
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_res
        
        payload = {"amount": 1000, "payment_type": "Installment"}
        response = client.post("/api/v1/candidates/portal/payments/create-order", json=payload)
        
        assert response.status_code == 400
        assert "exceeds remaining balance" in response.json()["detail"].lower()

def test_create_order_success_mock(client):
    candidate = MockCandidate()
    candidate.payments = []
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = candidate
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock) as mock_commit, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.flush", new_callable=AsyncMock) as mock_flush:
        
        mock_execute.return_value = mock_res
        
        payload = {"amount": 1000, "payment_type": "Installment"}
        response = client.post("/api/v1/candidates/portal/payments/create-order", json=payload)
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert "order_mock_" in response.json()["order_id"]
        assert response.json()["sandbox"] is True

def test_payment_status(client):
    payment = CandidatePayment(
        id="pay_1",
        amount=1000,
        payment_type="Installment",
        status="Paid",
        razorpay_order_id="order_1",
        receipt_url="http://receipt.pdf"
    )
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = payment
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute:
        mock_execute.return_value = mock_res
        
        response = client.get("/api/v1/candidates/portal/payments/status/order_1")
        assert response.status_code == 200
        assert response.json()["status"] == "Paid"
        assert response.json()["receipt_url"] == "http://receipt.pdf"

def test_verify_mock_payment(client):
    payment = CandidatePayment(
        id="pay_1",
        amount=1000,
        payment_type="Admission Fee",
        status="Created",
        razorpay_order_id="order_mock_1",
    )
    
    payment.candidate = CandidateApplication(
        id="mock_candidate_id",
        email="candidate@example.com",
        full_name="Mock Candidate",
        phone="9876543210",
        application_status="Qualified",
        is_deleted=False,
        admission_fee_paid=False,
        auto_enroll_enabled=True,
    )
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = payment
    
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock) as mock_commit, \
         patch("app.services.candidate_service.CandidateService.generate_and_upload_receipt", new_callable=AsyncMock) as mock_receipt:
        
        mock_execute.return_value = mock_res
        
        payload = {
            "razorpay_order_id": "order_mock_1",
            "razorpay_payment_id": "pay_mock_123",
            "razorpay_signature": "sig_mock",
            "payment_type": "Admission Fee",
            "amount": 1000
        }
        
        response = client.post("/api/v1/candidates/portal/payments/verify", json=payload)
        assert response.status_code == 200
        assert response.json()["sandbox"] is True
        mock_receipt.assert_called_once()

def test_webhook_signature_verification_failure(client):
    payload = b'{"event": "payment.captured"}'
    
    with patch("app.core.config.settings.RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret"):
        response = client.post(
            "/api/v1/candidates/portal/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": "invalid_sig"}
        )
        
        assert response.status_code == 400
        assert "signature verification failed" in response.json()["detail"].lower()

def test_webhook_payment_captured_success(client):
    payload = b'{"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_123", "order_id": "order_123"}}}}'
    
    # Calculate valid signature
    webhook_secret = "test_webhook_secret"
    generated_sig = hmac.new(
        webhook_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    payment = CandidatePayment(
        id="pay_1",
        amount=1000,
        payment_type="Admission Fee",
        status="Created",
        razorpay_order_id="order_123",
    )
    payment.candidate = CandidateApplication(
        id="mock_candidate_id",
        email="candidate@example.com",
        full_name="Mock Candidate",
        phone="9876543210",
        application_status="Qualified",
        is_deleted=False,
        admission_fee_paid=False,
        auto_enroll_enabled=True,
    )
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = payment
    
    with patch("app.core.config.settings.RAZORPAY_WEBHOOK_SECRET", webhook_secret), \
         patch("sqlalchemy.ext.asyncio.AsyncSession.execute", new_callable=AsyncMock) as mock_execute, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.commit", new_callable=AsyncMock) as mock_commit, \
         patch("app.services.candidate_service.CandidateService.generate_and_upload_receipt", new_callable=AsyncMock) as mock_receipt:
         
        mock_execute.return_value = mock_res
        
        response = client.post(
            "/api/v1/candidates/portal/payments/webhook",
            content=payload,
            headers={"X-Razorpay-Signature": generated_sig}
        )
        
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert payment.status == "Paid"
        assert payment.transaction_id == "pay_123"
        mock_receipt.assert_called_once()
