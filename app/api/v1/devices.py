from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.database import get_db
from app.models import Device, Outlet, User, DeviceShare
from app.schemas import (
    DeviceResponse,
    OutletResponse,
    DeviceRenameRequest,
    DeviceClaimRequest,
    ProtectionSettingsResponse,
    ProtectionSettingsUpdate
)
from app.services.device_service import DeviceService
from app.services.auth_service import AuthService, get_current_user
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
        icon = db_o.icon if db_o and db_o.icon else "outlet"
        auto_off = db_o.auto_off_minutes if db_o else 0
        standby_cutoff = db_o.standby_cutoff_w if db_o else 0.0
        surge_priority = db_o.is_surge_priority if db_o else False

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
            icon=icon,
            is_on=is_on,
            power_w=power_w,
            energy_kwh=energy_kwh,
            temp_c=temp_c,
            auto_off_minutes=auto_off,
            standby_cutoff_w=standby_cutoff,
            is_surge_priority=surge_priority
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
        min_voltage=dev.min_voltage or 190.0,
        max_voltage=dev.max_voltage or 245.0,
        max_power_w=dev.max_power_w or 3200.0,
        child_lock_enabled=bool(dev.child_lock_enabled),
        away_mode_enabled=bool(dev.away_mode_enabled),
        surge_router_channel=dev.surge_router_channel or 1,
        outlets=outlets_resp
    )


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    owner_telegram_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists devices accessible by the authenticated user only.

    Users cannot see other users' strips.
    """
    if current_user.is_admin:
        devices = await DeviceService.get_all_devices(db, owner_telegram_id)
    else:
        # Query devices owned by user or shared with user
        shares_stmt = select(DeviceShare.device_mac).where(DeviceShare.shared_telegram_id == current_user.telegram_id)
        shares_res = await db.execute(shares_stmt)
        shared_macs = set(shares_res.scalars().all())

        stmt = select(Device).where(
            or_(
                Device.owner_telegram_id == current_user.telegram_id,
                Device.mac.in_(shared_macs)
            )
        )
        res = await db.execute(stmt)
        devices = list(res.scalars().all())

    resp = []
    for d in devices:
        res = await db.execute(select(Outlet).where(Outlet.device_mac == d.mac))
        outlets = list(res.scalars().all())
        resp.append(_format_device_response(d, outlets))
    return resp


@router.get("/{mac}", response_model=DeviceResponse)
async def get_device(
    mac: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    dev = await AuthService.verify_device_access(db, current_user, mac)
    res = await db.execute(select(Outlet).where(Outlet.device_mac == dev.mac))
    outlets = list(res.scalars().all())
    return _format_device_response(dev, outlets)


@router.patch("/{mac}/rename")
async def rename_device(
    mac: str,
    payload: DeviceRenameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.verify_device_access(db, current_user, mac)
    ok = await DeviceService.rename_device(db, mac, payload.name)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"ok": True, "name": payload.name}


@router.get("/{mac}/protection", response_model=ProtectionSettingsResponse)
async def get_protection_settings(
    mac: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    dev = await AuthService.verify_device_access(db, current_user, mac)
    return ProtectionSettingsResponse(
        mac=dev.mac,
        min_voltage=dev.min_voltage or 190.0,
        max_voltage=dev.max_voltage or 245.0,
        max_power_w=dev.max_power_w or 3200.0,
        child_lock_enabled=bool(dev.child_lock_enabled),
        away_mode_enabled=bool(dev.away_mode_enabled),
        surge_router_channel=dev.surge_router_channel or 1,
    )


@router.put("/{mac}/protection", response_model=ProtectionSettingsResponse)
async def update_protection_settings(
    mac: str,
    payload: ProtectionSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    dev = await AuthService.verify_device_access(db, current_user, mac)
    if payload.min_voltage is not None:
        dev.min_voltage = payload.min_voltage
    if payload.max_voltage is not None:
        dev.max_voltage = payload.max_voltage
    if payload.max_power_w is not None:
        dev.max_power_w = payload.max_power_w
    if payload.child_lock_enabled is not None:
        dev.child_lock_enabled = payload.child_lock_enabled
    if payload.away_mode_enabled is not None:
        dev.away_mode_enabled = payload.away_mode_enabled
    if payload.surge_router_channel is not None:
        dev.surge_router_channel = payload.surge_router_channel

    await db.commit()
    await db.refresh(dev)

    return ProtectionSettingsResponse(
        mac=dev.mac,
        min_voltage=dev.min_voltage,
        max_voltage=dev.max_voltage,
        max_power_w=dev.max_power_w,
        child_lock_enabled=dev.child_lock_enabled,
        away_mode_enabled=dev.away_mode_enabled,
        surge_router_channel=dev.surge_router_channel,
    )


@router.post("/claim")
async def claim_device(
    payload: DeviceClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_user_id = payload.user_telegram_id or current_user.telegram_id
    if not current_user.is_admin and target_user_id != current_user.telegram_id:
        raise HTTPException(status_code=403, detail="Cannot claim device for another user")

    ok, message = await DeviceService.claim_device(db, payload.mac, target_user_id)
    if not ok:
        raise HTTPException(status_code=400, detail=message)
    return {"ok": True, "message": message}


@router.delete("/{mac}/claim")
async def unclaim_device(
    mac: str,
    user_telegram_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    target_user_id = user_telegram_id or current_user.telegram_id
    if not current_user.is_admin and target_user_id != current_user.telegram_id:
        raise HTTPException(status_code=403, detail="Cannot unclaim device of another user")

    ok = await DeviceService.unclaim_device(db, mac, target_user_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Cannot unclaim device")
    return {"ok": True}
