from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Device, Outlet
from app.schemas import DeviceResponse, OutletResponse, DeviceRenameRequest, DeviceClaimRequest
from app.services.device_service import DeviceService
from app.device_server.hub import hub

router = APIRouter(prefix="/devices", tags=["Devices"])


def _format_device_response(dev: Device, outlets: List[Outlet]) -> DeviceResponse:
    snap = hub.devices[dev.mac].snapshot() if dev.mac in hub.devices else None
    online = dev.mac in hub.sessions
    outlets_resp = []

    outlets_by_ch = {o.channel: o for o in outlets}
    for ch in range(1, 5):
        db_o = outlets_by_ch.get(ch)
        name = db_o.name if db_o else f"مخرج {ch}"
        if snap:
            snap_o = next((so for so in snap["outlets"] if so["channel"] == ch), None)
            is_on = snap_o["on"] if snap_o else (db_o.is_on if db_o else False)
            power_w = snap_o["power_w"] if snap_o else (db_o.power_w if db_o else 0.0)
            energy_kwh = snap_o["energy_kwh"] if snap_o else (db_o.energy_kwh if db_o else 0.0)
            temp_c = snap_o["temp_c"] if snap_o else (db_o.temp_c if db_o else 0)
        else:
            is_on = db_o.is_on if db_o else False
            power_w = db_o.power_w if db_o else 0.0
            energy_kwh = db_o.energy_kwh if db_o else 0.0
            temp_c = db_o.temp_c if db_o else 0

        outlets_resp.append(OutletResponse(
            channel=ch,
            name=name,
            is_on=is_on,
            power_w=power_w,
            energy_kwh=energy_kwh,
            temp_c=temp_c
        ))

    return DeviceResponse(
        mac=dev.mac,
        name=dev.name,
        model=dev.model,
        fw=dev.fw,
        ip=dev.ip,
        online=online,
        voltage_v=snap["voltage"] if snap else dev.voltage_v,
        current_a=snap["current_a"] if snap else None,
        rssi=snap["rssi"] if snap else dev.rssi,
        last_seen=dev.last_seen,
        owner_telegram_id=dev.owner_telegram_id,
        outlets=outlets_resp
    )


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    owner_telegram_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    devices = await DeviceService.get_all_devices(db, owner_telegram_id)
    resp = []
    for d in devices:
        res = await db.execute(select(Outlet).where(Outlet.device_mac == d.mac))
        outlets = list(res.scalars().all())
        resp.append(_format_device_response(d, outlets))
    return resp


@router.get("/{mac}", response_model=DeviceResponse)
async def get_device(mac: str, db: AsyncSession = Depends(get_db)):
    dev = await DeviceService.get_device(db, mac)
    if not dev:
        raise HTTPException(status_code=404, detail="Device not found")
    res = await db.execute(select(Outlet).where(Outlet.device_mac == dev.mac))
    outlets = list(res.scalars().all())
    return _format_device_response(dev, outlets)


@router.patch("/{mac}/rename")
async def rename_device(mac: str, payload: DeviceRenameRequest, db: AsyncSession = Depends(get_db)):
    ok = await DeviceService.rename_device(db, mac, payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True, "name": payload.name}


@router.post("/claim")
async def claim_device(payload: DeviceClaimRequest, db: AsyncSession = Depends(get_db)):
    ok, message = await DeviceService.claim_device(db, payload.mac, payload.user_telegram_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@router.delete("/{mac}/claim")
async def unclaim_device(mac: str, user_telegram_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    ok = await DeviceService.unclaim_device(db, mac, user_telegram_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot unclaim device")
    return {"ok": True}
