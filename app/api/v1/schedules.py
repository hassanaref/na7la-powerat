from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from app.schemas import CountdownCreateRequest, ScheduleResponse
from app.services.scheduler_service import SchedulerService

router = APIRouter(prefix="/schedules", tags=["Schedules"])


@router.post("/countdown", response_model=ScheduleResponse)
async def create_countdown(payload: CountdownCreateRequest):
    s = await SchedulerService.create_countdown(
        device_mac=payload.device_mac,
        channel=payload.outlet_channel,
        action=payload.action,
        delay_seconds=payload.delay_seconds
    )
    return s


@router.get("", response_model=List[ScheduleResponse])
async def list_schedules(device_mac: Optional[str] = Query(None)):
    return await SchedulerService.list_active_schedules(device_mac)


@router.delete("/{schedule_id}")
async def cancel_schedule(schedule_id: int):
    ok = await SchedulerService.cancel_schedule(schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"ok": True}
