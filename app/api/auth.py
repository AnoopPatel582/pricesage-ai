import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.notifications.email_service import EmailService
from app.utils.config import settings

router = APIRouter(prefix="/auth", tags=["Authentication"])

# In-memory store for OTPs: { "email@example.com": {"otp": "123456", "expires_at": datetime} }
OTP_STORE: Dict[str, dict] = {}


# --- Schemas for Password Reset via OTP ---
class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp: str
    new_password: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with a hashed password."""
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists."
        )

    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate email and password to return an access JWT."""
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    """Fetch the authenticated user's profile."""
    return current_user


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generate a 6-digit OTP valid for 10 minutes."""
    user = db.query(User).filter(User.email == payload.email).first()

    # Generic message prevents email enumeration
    if not user:
        return {"detail": "If this email is registered, a 6-digit verification code has been sent."}

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise HTTPException(status_code=503, detail="Password reset email is not configured.")

    otp = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    OTP_STORE[payload.email] = {
        "otp": otp,
        "expires_at": expires_at
    }

    if not EmailService.send_password_reset_code(payload.email, otp):
        OTP_STORE.pop(payload.email, None)
        raise HTTPException(status_code=502, detail="Password reset email could not be sent.")

    return {"detail": "A 6-digit verification code has been sent."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Verify OTP and update user password."""
    record = OTP_STORE.get(payload.email)

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP requested for this email. Please request a new code."
        )

    # Check expiration
    if datetime.now(timezone.utc) > record["expires_at"]:
        del OTP_STORE[payload.email]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The verification code has expired. Please request a new one."
        )

    # Check match
    if record["otp"] != payload.otp.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid 6-digit verification code."
        )

    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    # Update password and clear used OTP
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    del OTP_STORE[payload.email]

    return {"detail": "Password has been successfully reset! You can now sign in."}
