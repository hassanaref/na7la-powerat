import base64
import secrets
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import select, or_

from app.config import settings, BASE_DIR
from app.database import AsyncSessionLocal
from app.models import User, Device, DeviceShare
from app.device_server.hub import hub
from app.services.auth_service import AuthService

router = APIRouter(tags=["Legacy & Android App Compatibility"])


class LegacyOnOffRequest(BaseModel):
    mac: str
    outlet: int
    on: bool


def extract_token_from_request(request: Request) -> Optional[str]:
    # 1. X-User-Token or X-Token header
    token = request.headers.get("X-User-Token") or request.headers.get("X-Token")
    if token:
        return token.strip()

    # 2. Authorization Bearer
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    if auth.startswith("Basic "):
        try:
            user, _, password = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
            return password.strip() or user.strip()
        except Exception:
            pass

    # 3. Query params: ?user_token=, ?token=, ?t=
    token = (
        request.query_params.get("user_token")
        or request.query_params.get("token")
        or request.query_params.get("t")
    )
    if token:
        return token.strip()

    return None


async def get_request_user(request: Request) -> Optional[User]:
    token = extract_token_from_request(request)
    if not token:
        return None

    # Check server admin token
    if settings.API_TOKEN and secrets.compare_digest(token, settings.API_TOKEN):
        return User(telegram_id=0, first_name="Admin", is_admin=True)

    # Check user token in DB
    return await AuthService.get_user_by_token(token)


def is_authorized(request: Request) -> bool:
    if not settings.API_TOKEN:
        return True
    token = extract_token_from_request(request)
    return bool(token and secrets.compare_digest(token, settings.API_TOKEN))


def verify_auth(request: Request):
    if not is_authorized(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="na7la: token required",
            headers={"WWW-Authenticate": 'Basic realm="na7la"'}
        )


@router.get("/api/state")
async def legacy_get_state(request: Request):
    user = await get_request_user(request)
    if settings.API_TOKEN and not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="na7la: token required",
            headers={"WWW-Authenticate": 'Basic realm="na7la"'}
        )

    snap = hub.snapshot()
    snap["local_ip"] = settings.effective_local_ip
    snap["port"] = settings.DEVICE_PORT

    # Strict multi-tenancy: filter devices if not admin
    if user and not user.is_admin:
        async with AsyncSessionLocal() as db:
            shares_stmt = select(DeviceShare.device_mac).where(DeviceShare.shared_telegram_id == user.telegram_id)
            shares_res = await db.execute(shares_stmt)
            shared_macs = set(shares_res.scalars().all())

            stmt = select(Device.mac).where(
                or_(
                    Device.owner_telegram_id == user.telegram_id,
                    Device.mac.in_(shared_macs)
                )
            )
            res = await db.execute(stmt)
            allowed_macs = set(res.scalars().all())

        snap["devices"] = [d for d in snap["devices"] if d.get("mac", "").upper() in allowed_macs]

    return snap


@router.post("/api/onoff")
async def legacy_post_onoff(request: Request, payload: LegacyOnOffRequest):
    user = await get_request_user(request)
    if settings.API_TOKEN and not user:
        raise HTTPException(status_code=401, detail={"error": "token required"})

    mac = payload.mac.upper().replace(":", "").replace(".", "")

    if user and not user.is_admin:
        async with AsyncSessionLocal() as db:
            await AuthService.verify_device_access(db, user, mac)

    outlet = payload.outlet
    on = payload.on

    session = hub.get_session(mac)
    if not session:
        raise HTTPException(status_code=503, detail={"error": "device offline"})

    channels = [1, 2, 3, 4] if outlet == 0 else [outlet]
    if not set(channels) <= {1, 2, 3, 4}:
        raise HTTPException(status_code=400, detail={"error": "bad outlet"})

    try:
        ok = await hub.set_outlets(mac, channels, on)
    except Exception as err:
        raise HTTPException(status_code=502, detail={"error": f"command failed: {err}"})

    return {"ok": bool(ok), "confirmed": ok}


@router.get("/powerk.py")
@router.get("/na7la.py")
async def download_script():
    path = BASE_DIR / "na7la.py"
    if not path.is_file():
        path = BASE_DIR / "powerk.py"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Script not found")
    return FileResponse(
        path=path,
        media_type="text/x-python",
        filename="na7la.py"
    )


@router.get("/powerk.apk")
@router.get("/na7la_powerat.apk")
async def download_apk():
    path = BASE_DIR / "android/app/build/outputs/apk/debug/app-debug.apk"
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"error": "no APK built yet: cd android && gradlew assembleDebug"})
    return FileResponse(
        path=path,
        media_type="application/vnd.android.package-archive",
        filename="na7la_powerat.apk"
    )
