import secrets
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel

from app.config import settings, BASE_DIR
from app.device_server.hub import hub

router = APIRouter(tags=["Legacy & Android App Compatibility"])


class LegacyOnOffRequest(BaseModel):
    mac: str
    outlet: int
    on: bool


def is_authorized(request: Request) -> bool:
    token = settings.API_TOKEN
    if not token:
        return True

    # 1. X-Token header
    if secrets.compare_digest(request.headers.get("X-Token", ""), token):
        return True

    # 2. Query param ?t=
    if secrets.compare_digest(request.query_params.get("t", ""), token):
        return True

    # 3. HTTP Basic Auth
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Basic "):
        import base64
        try:
            user, _, password = base64.b64decode(auth[6:]).decode("utf-8").partition(":")
            if secrets.compare_digest(password, token) or secrets.compare_digest(user, token):
                return True
        except Exception:
            return False

    return False


def verify_auth(request: Request):
    if not is_authorized(request):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="powerk: token required",
            headers={"WWW-Authenticate": 'Basic realm="powerk"'}
        )


@router.get("/api/state")
async def legacy_get_state(request: Request):
    verify_auth(request)
    snap = hub.snapshot()
    snap["local_ip"] = settings.effective_local_ip
    snap["port"] = settings.DEVICE_PORT
    return snap


@router.post("/api/onoff")
async def legacy_post_onoff(request: Request, payload: LegacyOnOffRequest):
    verify_auth(request)
    mac = payload.mac.upper()
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
async def download_powerk_py():
    path = BASE_DIR / "powerk.py"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="powerk.py not found")
    return FileResponse(
        path=path,
        media_type="text/x-python",
        filename="powerk.py"
    )


@router.get("/powerk.apk")
async def download_powerk_apk():
    path = BASE_DIR / "android/app/build/outputs/apk/debug/app-debug.apk"
    if not path.is_file():
        raise HTTPException(status_code=404, detail={"error": "no APK built yet: cd android && gradlew assembleDebug"})
    return FileResponse(
        path=path,
        media_type="application/vnd.android.package-archive",
        filename="powerk.apk"
    )
