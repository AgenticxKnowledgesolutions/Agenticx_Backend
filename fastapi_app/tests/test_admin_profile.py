import pytest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.models.user import User, UserRole
from app.models.admin_email_verification import AdminEmailVerification
from app.services.admin_profile_service import AdminProfileService
from app.core.security import hash_password, verify_password


@pytest.mark.asyncio
async def test_get_profile():
    user = User(
        id="admin-123",
        username="admin_user",
        email="admin@example.com",
        hashed_password=hash_password("secret123"),
        role=UserRole.admin
    )
    profile = AdminProfileService.get_profile(user)
    assert profile["id"] == "admin-123"
    assert profile["name"] == "admin_user"
    assert profile["username"] == "admin_user"
    assert profile["email"] == "admin@example.com"
    assert profile["role"] == "admin"


@pytest.mark.asyncio
async def test_request_email_change_validation():
    mock_db = AsyncMock()
    user = User(
        id="admin-123",
        username="admin_user",
        email="admin@example.com",
        hashed_password=hash_password("secret123"),
        role=UserRole.admin
    )

    # 1. Invalid format
    with pytest.raises(HTTPException) as exc1:
        await AdminProfileService.request_email_change(mock_db, user, "invalid-email")
    assert exc1.value.status_code == 400

    # 2. Same email
    with pytest.raises(HTTPException) as exc2:
        await AdminProfileService.request_email_change(mock_db, user, "admin@example.com")
    assert exc2.value.status_code == 400

    # 3. Already taken email
    mock_res_taken = MagicMock()
    mock_res_taken.scalar_one_or_none.return_value = User(id="user-2", email="taken@example.com")
    mock_db.execute.return_value = mock_res_taken

    with pytest.raises(HTTPException) as exc3:
        await AdminProfileService.request_email_change(mock_db, user, "taken@example.com")
    assert exc3.value.status_code == 400
    assert "already registered" in exc3.value.detail


@pytest.mark.asyncio
async def test_request_email_change_success():
    mock_db = AsyncMock()
    user = User(
        id="admin-123",
        username="admin_user",
        email="admin@example.com",
        hashed_password=hash_password("secret123"),
        role=UserRole.admin
    )

    # Mock no conflicting user and no recent unverified OTP
    mock_res_empty = MagicMock()
    mock_res_empty.scalar_one_or_none.return_value = None
    mock_res_empty.scalars.return_value.first.return_value = None
    mock_db.execute.return_value = mock_res_empty

    with patch("app.services.admin_profile_service.EmailService.send_otp_email", return_value=True):
        res = await AdminProfileService.request_email_change(mock_db, user, "newadmin@example.com")
        assert res["success"] is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_verify_email_change_otp_success():
    mock_db = AsyncMock()
    user = User(
        id="admin-123",
        username="admin_user",
        email="oldadmin@example.com",
        hashed_password=hash_password("secret123"),
        role=UserRole.admin
    )

    otp = "123456"
    verification = AdminEmailVerification(
        id="ver-1",
        user_id="admin-123",
        new_email="newadmin@example.com",
        hashed_otp=hash_password(otp),
        attempts=0,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [verification]
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    result = await AdminProfileService.verify_email_change_otp(mock_db, user, otp)
    assert result["success"] is True
    assert user.email == "newadmin@example.com"
    assert verification.verified is True
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_verify_email_change_otp_wrong_code():
    mock_db = AsyncMock()
    user = User(
        id="admin-123",
        username="admin_user",
        email="oldadmin@example.com",
        hashed_password=hash_password("secret123"),
        role=UserRole.admin
    )

    verification = AdminEmailVerification(
        id="ver-1",
        user_id="admin-123",
        new_email="newadmin@example.com",
        hashed_otp=hash_password("123456"),
        attempts=0,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        verified=False
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [verification]
    mock_db.execute.return_value = mock_res

    with pytest.raises(HTTPException) as exc:
        await AdminProfileService.verify_email_change_otp(mock_db, user, "999999")

    assert exc.value.status_code == 400
    assert verification.attempts == 1
    assert "Invalid verification code" in exc.value.detail


@pytest.mark.asyncio
async def test_change_password_success_and_failures():
    mock_db = AsyncMock()
    old_pass = "oldsecret123"
    user = User(
        id="admin-123",
        username="admin_user",
        email="admin@example.com",
        hashed_password=hash_password(old_pass),
        role=UserRole.admin
    )

    # 1. Wrong current password
    with pytest.raises(HTTPException) as exc1:
        await AdminProfileService.change_password(mock_db, user, "wrongpassword", "newsecret123")
    assert exc1.value.status_code == 400
    assert "Incorrect current password" in exc1.value.detail

    # 2. Too short new password
    with pytest.raises(HTTPException) as exc2:
        await AdminProfileService.change_password(mock_db, user, old_pass, "short")
    assert exc2.value.status_code == 400
    assert "at least 8 characters" in exc2.value.detail

    # 3. Valid password change
    new_pass = "newsecret123"
    res = await AdminProfileService.change_password(mock_db, user, old_pass, new_pass)
    assert res["success"] is True
    assert verify_password(new_pass, user.hashed_password) is True
    mock_db.commit.assert_called_once()
