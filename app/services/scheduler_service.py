import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Optional, List
from sqlalchemy import select, and_

from app.database import AsyncSessionLocal
from app.models import Schedule
from app.services.device_service import DeviceService

logger = logging.getLogger("powerk.scheduler")


def utcnow():
    return datetime.now(timezone.utc)


class SchedulerService:
    _last_recurring_minute: str = ""

    @staticmethod
    async def create_countdown(
        device_mac: str,
        channel: int,
        action: str,
        delay_seconds: int,
        user_id: Optional[int] = None
    ) -> Schedule:
        target = utcnow() + timedelta(seconds=delay_seconds)
        async with AsyncSessionLocal() as db:
            schedule = Schedule(
                device_mac=device_mac.upper(),
                outlet_channel=channel,
                action=action.lower(),
                schedule_type="countdown",
                target_time=target,
                is_active=True,
                created_by_telegram_id=user_id,
                created_at=utcnow(),
            )
            db.add(schedule)
            await db.commit()
            await db.refresh(schedule)
            logger.info(f"Countdown scheduled for {device_mac} ch={channel} to {action} at {target}")
            return schedule

    @staticmethod
    async def create_recurring(
        device_mac: str,
        channel: int,
        action: str,
        time_of_day: str,  # "HH:MM" in UTC or local
        days_of_week: str = "0,1,2,3,4,5,6",
        user_id: Optional[int] = None
    ) -> Schedule:
        async with AsyncSessionLocal() as db:
            schedule = Schedule(
                device_mac=device_mac.upper(),
                outlet_channel=channel,
                action=action.lower(),
                schedule_type="recurring",
                time_of_day=time_of_day,
                days_of_week=days_of_week,
                is_active=True,
                created_by_telegram_id=user_id,
                created_at=utcnow(),
            )
            db.add(schedule)
            await db.commit()
            await db.refresh(schedule)
            logger.info(f"Recurring schedule created for {device_mac} ch={channel} at {time_of_day}")
            return schedule

    @staticmethod
    async def list_active_schedules(device_mac: Optional[str] = None) -> List[Schedule]:
        async with AsyncSessionLocal() as db:
            stmt = select(Schedule).where(Schedule.is_active == True)
            if device_mac:
                stmt = stmt.where(Schedule.device_mac == device_mac.upper())
            res = await db.execute(stmt)
            return list(res.scalars().all())

    @staticmethod
    async def cancel_schedule(schedule_id: int) -> bool:
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = res.scalar_one_or_none()
            if not schedule:
                return False
            schedule.is_active = False
            await db.commit()
            return True

    @classmethod
    async def run_scheduler_tick(cls):
        """Single evaluation of active timers and recurring schedules."""
        now = utcnow()
        current_minute_str = now.strftime("%H:%M")
        current_weekday = str(now.weekday())

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Schedule).where(Schedule.is_active == True))
            schedules = res.scalars().all()

            for s in schedules:
                if s.schedule_type == "countdown" and s.target_time:
                    # Compare timezone-aware or normalize
                    t_target = s.target_time
                    if t_target.tzinfo is None:
                        t_target = t_target.replace(tzinfo=timezone.utc)

                    if t_target <= now:
                        logger.info(f"Executing countdown #{s.id} on {s.device_mac} ch={s.outlet_channel} -> {s.action}")
                        await DeviceService.toggle_outlet(s.device_mac, s.outlet_channel, s.action == "on")
                        s.is_active = False
                        await db.commit()

                elif s.schedule_type == "recurring" and s.time_of_day:
                    if cls._last_recurring_minute != current_minute_str:
                        if s.time_of_day == current_minute_str:
                            allowed_days = (s.days_of_week or "").split(",")
                            if current_weekday in allowed_days:
                                logger.info(f"Executing recurring schedule #{s.id} on {s.device_mac} ch={s.outlet_channel} -> {s.action}")
                                await DeviceService.toggle_outlet(s.device_mac, s.outlet_channel, s.action == "on")

            if cls._last_recurring_minute != current_minute_str:
                cls._last_recurring_minute = current_minute_str


async def scheduler_loop():
    """Background task running every 5 seconds to process scheduled events."""
    logger.info("Scheduler background loop started")
    while True:
        try:
            await asyncio.sleep(5.0)
            await SchedulerService.run_scheduler_tick()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in scheduler tick: {e}")
