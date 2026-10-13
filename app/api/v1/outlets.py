from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import OutletToggleRequest, OutletRenameRequest
from app.services.device_service import DeviceService
from app.device_server.hub import hub

router = APIRouter(prefix="/outlets", tags=["Outlets"])


@router.post("/toggle")
async def toggle_outlet(payload: OutletToggleRequest):
    session = hub.get_session(payload.mac)
    if not session:
        raise HTTPException(status_code=503, detail="Device is offline or not connected")

    ok = await DeviceService.toggle_outlet(payload.mac, payload.outlet, payload.on)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to execute command on strip")
    return {"ok": True, "outlet": payload.outlet, "on": payload.on}


@router.patch("/{mac}/{channel}/rename")
async def rename_outlet(mac: str, channel: int, payload: OutletRenameRequest, db: AsyncSession = Depends(get_db)):
    if channel not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 4")
    ok = await DeviceService.rename_outlet(db, mac, channel, payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Outlet or device not found")
    return {"ok": True, "channel": channel, "name": payload.name}
