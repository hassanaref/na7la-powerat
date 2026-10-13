from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import User, Schedule, Device
from app.schemas import CountdownCreateRequest, ScheduleResponse
from app.services.scheduler_service import SchedulerService
from app.services.auth_service import AuthService, get_current_user

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post("/countdown", response_model=ScheduleResponse)
async def create_countdown(
    payload: CountdownCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.verify_device_access(db, current_user, payload.device_mac)
    s = await SchedulerService.create_countdown(
        device_mac=payload.device_mac,
        channel=payload.outlet_channel,
        action=payload.action,
        delay_seconds=payload.delay_seconds
    )
    return s


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(
    device_mac: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if device_mac:
        await AuthService.verify_device_access(db, current_user, device_mac)
        return await SchedulerService.list_active_schedules(device_mac)

    all_schedules = await SchedulerService.list_active_schedules(None)
    if current_user.is_admin:
        return all_schedules

    # Filter to only schedules for devices owned by user
    user_macs_stmt = select(Device.mac).where(Device.owner_telegram_id == current_user.telegram_id)
    res = await db.execute(user_macs_stmt)
    owned_macs = set(res.scalars().all())

    return [s for s in all_schedules if s.device_mac in owned_macs]


@router.delete("/{schedule_id}")
async def cancel_schedule(
    schedule_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    sched = await db.get(Schedule, schedule_id)
    if not sched:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await AuthService.verify_device_access(db, current_user, sched.device_mac)
    ok = await SchedulerService.cancel_schedule(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"ok": True}
