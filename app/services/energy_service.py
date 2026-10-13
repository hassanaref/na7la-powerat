import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Dict, Any
from sqlalchemy import select, func

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Telemetry, Device
from app.device_server.hub import hub

logger = logging.getLogger("powerk.energy")


def utcnow():
    return datetime.now(timezone.utc)


class EnergyService:
    @staticmethod
    async def log_telemetry_snapshot():
        """Take a snapshot of all online devices and log telemetry to DB."""
        async with AsyncSessionLocal() as db:
            for mac, dev in hub.devices.items():
                if not dev.online:
                    continue
                # Aggregate telemetry
                snap = dev.snapshot()
                rec = Telemetry(
                    device_mac=mac,
                    outlet_channel=0,
                    power_w=snap["power_w"],
                    energy_kwh=snap["energy_kwh"],
                    voltage_v=snap["voltage"],
                    current_a=snap["current_a"],
                    temp_c=max((o["temp_c"] for o in snap["outlets"]), default=0),
                    recorded_at=utcnow(),
                )
                db.add(rec)

                # Outlets telemetry
                for o in snap["outlets"]:
                    rec_out = Telemetry(
                        device_mac=mac,
                        outlet_channel=o["channel"],
                        power_w=o["power_w"],
                        energy_kwh=o["energy_kwh"],
                        temp_c=o["temp_c"],
                        recorded_at=utcnow(),
                    )
                    db.add(rec_out)

            await db.commit()

    @staticmethod
    async def get_device_summary(device_mac: str) -> Dict[str, Any]:
        """Calculates total energy, daily energy, and cost estimation."""
        mac = device_mac.upper()
        dev = hub.get_device(mac)
        total_kwh = dev.snapshot()["energy_kwh"] if dev else 0.0

        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        async with AsyncSessionLocal() as db:
            # Query earliest energy reading today
            res_earliest = await db.execute(
                select(Telemetry.energy_kwh)
                .where(
                    Telemetry.device_mac == mac,
                    Telemetry.outlet_channel == 0,
                    Telemetry.recorded_at >= today_start
                )
                .order_by(Telemetry.recorded_at.asc())
                .limit(1)
            )
            earliest_today = res_earliest.scalar_one_or_none()

            today_kwh = 0.0
            if earliest_today is not None and total_kwh >= earliest_today:
                today_kwh = round(total_kwh - earliest_today, 3)

        cost_egp = round(today_kwh * settings.ELECTRICITY_COST_PER_KWH, 2)
        total_cost_egp = round(total_kwh * settings.ELECTRICITY_COST_PER_KWH, 2)

        return {
            "mac": mac,
            "total_kwh": total_kwh,
            "today_kwh": today_kwh,
            "today_cost_egp": cost_egp,
            "total_cost_egp": total_cost_egp,
            "rate_per_kwh": settings.ELECTRICITY_COST_PER_KWH,
        }


async def energy_logger_loop():
    """Background task logging energy usage every minute."""
    logger.info("Energy logging background task started")
    while True:
        try:
            await asyncio.sleep(settings.TELEMETRY_LOG_INTERVAL)
            await EnergyService.log_telemetry_snapshot()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in energy logger: {e}")
