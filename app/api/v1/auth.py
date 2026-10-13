from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Device
from app.services.auth_service import AuthService, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication & User Management"])


class SignUpRequest(BaseModel):
    name: Optional[str] = "User"
    email: Optional[str] = None
    pin_code: Optional[str] = None


class LoginRequest(BaseModel):
    user_token: Optional[str] = None
    email: Optional[str] = None


class ClaimDeviceRequest(BaseModel):
    mac: str


@router.post("/signup")
async def signup(payload: SignUpRequest, db: AsyncSession = Depends(get_db)):
    """Registers a new mobile app user and generates a persistent user_token."""
    user = await AuthService.create_user(email=payload.email, name=payload.name, pin=payload.pin_code)
    return {
        "ok": True,
        "user_id": user.telegram_id,
        "user_token": user.user_token,
        "name": user.first_name,
        "email": user.email
    }


@router.post("/login")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Logs in using an existing user_token or email."""
    if payload.user_token:
        user = await AuthService.get_user_by_token(payload.user_token)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid user token")
        return {
            "ok": True,
            "user_id": user.telegram_id,
            "user_token": user.user_token,
            "name": user.first_name,
            "email": user.email
        }
    elif payload.email:
        res = await db.execute(select(User).where(User.email == payload.email))
        user = res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found with this email")
        return {
            "ok": True,
            "user_id": user.telegram_id,
            "user_token": user.user_token,
            "name": user.first_name,
            "email": user.email
        }
    raise HTTPException(status_code=400, detail="Provide user_token or email to login")


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Returns current authenticated user details and their claimed devices."""
    res = await db.execute(select(Device).where(Device.owner_telegram_id == current_user.telegram_id))
    devices = res.scalars().all()
    return {
        "user_id": current_user.telegram_id,
        "name": current_user.first_name,
        "email": current_user.email,
        "devices": [{"mac": d.mac, "name": d.name, "online": d.online} for d in devices]
    }


@router.post("/claim")
async def claim_strip(
    payload: ClaimDeviceRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Claims a strip for the authenticated user.

    Prevents hijacking if already claimed by someone else.
    """
    mac_clean = payload.mac.replace(":", "").replace(".", "").upper()
    dev = await db.get(Device, mac_clean)
    if not dev:
        # Pre-register device if offline
        dev = Device(
            mac=mac_clean,
            name=f"مشترك {mac_clean[-4:]}",
            owner_telegram_id=current_user.telegram_id
        )
        db.add(dev)
        await db.commit()
        return {"ok": True, "message": f"Device {mac_clean} linked to your account."}

    if dev.owner_telegram_id and dev.owner_telegram_id != current_user.telegram_id:
        raise HTTPException(status_code=403, detail="Device is already linked to another user account.")

    dev.owner_telegram_id = current_user.telegram_id
    await db.commit()
    return {"ok": True, "message": f"Device {mac_clean} linked to your account."}
