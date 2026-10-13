import random
import time
from typing import Optional
from fastapi import Header, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Device, DeviceShare, User

security = HTTPBearer(auto_error=False)


class AuthService:
    @staticmethod
    async def create_user(email: Optional[str] = None, name: Optional[str] = None, pin: Optional[str] = None) -> User:
        """Creates a new user profile with a unique user_token for mobile app auth."""
        # Generate random 64-bit ID that doesn't collide with telegram IDs
        synth_id = random.randint(1000000000, 9999999999)
        async with AsyncSessionLocal() as db:
            user = User(
                telegram_id=synth_id,
                email=email,
                first_name=name or "User",
                pin_code=pin
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return user

    @staticmethod
    async def get_user_by_token(token: str) -> Optional[User]:
        if not token:
            return None
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(User).where(User.user_token == token))
            return res.scalar_one_or_none()

    @staticmethod
    async def verify_device_access(db, user: User, mac: str) -> Device:
        """Verifies that the user owns the device or has shared access.

        Raises 403 Forbidden if not authorized.
        """
        mac_clean = mac.replace(":", "").replace(".", "").upper()
        res = await db.execute(select(Device).where(Device.mac == mac_clean))
        dev = res.scalar_one_or_none()
        if not dev:
            raise HTTPException(status_code=404, detail="Device not found")

        # 1. Admin bypass
        if user.is_admin:
            return dev

        # 2. Direct owner check
        if dev.owner_telegram_id == user.telegram_id:
            return dev

        # 3. Check device shares
        res_share = await db.execute(
            select(DeviceShare).where(
                DeviceShare.device_mac == mac_clean,
                DeviceShare.shared_telegram_id == user.telegram_id,
                DeviceShare.can_control == True
            )
        )
        if res_share.scalar_one_or_none():
            return dev

        raise HTTPException(
            status_code=403,
            detail="Forbidden: You do not own this smart strip and have not been granted access."
        )


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_user_token: Optional[str] = Header(None, alias="X-User-Token"),
    token_query: Optional[str] = Query(None, alias="token"),
    user_token_query: Optional[str] = Query(None, alias="user_token")
) -> User:
    """FastAPI dependency to extract and authenticate the current user.

    Strictly isolates users so no user can see other users' strips.
    """
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials.strip()
    elif x_user_token:
        token = x_user_token.strip()
    elif user_token_query:
        token = user_token_query.strip()
    elif token_query:
        token = token_query.strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please provide a user token."
        )

    # Server Admin Token bypass
    if settings.API_TOKEN and token == settings.API_TOKEN:
        # Return a synthetic admin user
        admin = User(
            telegram_id=0,
            first_name="Admin",
            is_admin=True
        )
        return admin

    user = await AuthService.get_user_by_token(token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired user token."
        )

    return user
