from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Outlet
from app.schemas import OutletToggleRequest, OutletRenameRequest, OutletSmartUpdateRequest
from app.services.device_service import DeviceService
from app.services.auth_service import AuthService, get_current_user
from app.device_server.hub import hub

router = APIRouter(prefix="/outlets", tags=["Outlets"])


@router.post("/toggle")
async def toggle_outlet(
    payload: OutletToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.verify_device_access(db, current_user, payload.mac)

    session = hub.get_session(payload.mac)
    if not session:
        raise HTTPException(status_code=503, detail="Device is offline or not connected")

    ok = await DeviceService.toggle_outlet(payload.mac, payload.outlet, payload.on)
    if not ok:
        raise HTTPException(status_code=502, detail="Failed to execute command on strip")
    return {"ok": True, "outlet": payload.outlet, "on": payload.on}


@router.patch("/{mac}/{channel}/rename")
async def rename_outlet(
    mac: str,
    channel: int,
    payload: OutletRenameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if channel not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 4")

    await AuthService.verify_device_access(db, current_user, mac)
    ok = await DeviceService.rename_outlet(db, mac, channel, payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Outlet or device not found")
    return {"ok": True, "channel": channel, "name": payload.name}


@router.patch("/{mac}/{channel}/smart")
async def update_outlet_smart(
    mac: str,
    channel: int,
    payload: OutletSmartUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if channel not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Channel must be between 1 and 4")

    dev = await AuthService.verify_device_access(db, current_user, mac)
    res = await db.execute(
        select(Outlet).where(Outlet.device_mac == dev.mac, Outlet.channel == channel)
    )
    outlet = res.scalar_one_or_none()
    if not outlet:
        outlet = Outlet(device_mac=dev.mac, channel=channel, name=f"مخرج {channel}")
        db.add(outlet)

    if payload.name is not None:
        outlet.name = payload.name
    if payload.icon is not None:
        outlet.icon = payload.icon
    if payload.auto_off_minutes is not None:
        outlet.auto_off_minutes = payload.auto_off_minutes
    if payload.standby_cutoff_w is not None:
        outlet.standby_cutoff_w = payload.standby_cutoff_w
    if payload.standby_cutoff_minutes is not None:
        outlet.standby_cutoff_minutes = payload.standby_cutoff_minutes
    if payload.is_surge_priority is not None:
        outlet.is_surge_priority = payload.is_surge_priority

    await db.commit()
    await db.refresh(outlet)
    return {
        "ok": True,
        "channel": channel,
        "name": outlet.name,
        "icon": outlet.icon,
        "auto_off_minutes": outlet.auto_off_minutes,
        "standby_cutoff_w": outlet.standby_cutoff_w,
        "standby_cutoff_minutes": outlet.standby_cutoff_minutes,
        "is_surge_priority": outlet.is_surge_priority,
    }
