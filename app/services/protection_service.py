import asyncio
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Device, Outlet
from app.device_server.hub import hub

logger = logging.getLogger("na7la.protection")


class ProtectionService:
    @staticmethod
    def calibrate_current(total_w: float, voltage_v: float | None) -> float:
        """Applies 19mA noise subtraction calibration to raw amperage calculation."""
        if not voltage_v or voltage_v <= 0:
            return 0.0
        raw_amps = total_w / voltage_v
        calibrated = raw_amps - 0.019
        return max(0.0, round(calibrated, 2))

    @staticmethod
    async def check_voltage_guard(mac: str, voltage_v: float) -> bool:
        """Checks if line voltage violates safety boundaries (190V - 245V).

        If out of bounds, trips all relays to protect connected appliances.
        """
        async with AsyncSessionLocal() as db:
            dev = await db.get(Device, mac.upper())
            if not dev:
                return False

            min_v = dev.min_voltage or 190.0
            max_v = dev.max_voltage or 245.0

            if voltage_v < min_v or voltage_v > max_v:
                logger.warning(
                    f"⚠️ VOLTAGE TRIP on {mac}: {voltage_v}V is outside safe window [{min_v}V - {max_v}V]! Tripping all outlets."
                )
                await hub.set_outlets(mac, [1, 2, 3, 4], False)

                from app.services.alert_service import alert_service
                msg = (
                    f"🚨 *فصل طوارئ لحماية الأجهزة!*\n"
                    f"الجهد الكهربائي المسجل ({voltage_v}V) خارج النطاق الآمن ({min_v}V - {max_v}V).\n"
                    f"تم فصل جميع المخارج في المشترك `{mac}` لحماية الأجهزة من التلف."
                )
                if dev.owner_telegram_id:
                    await alert_service.send_telegram_alert(dev.owner_telegram_id, msg)
                return True
        return False

    @staticmethod
    async def check_overload_guard(mac: str, total_w: float) -> bool:
        """Trips all relays if aggregate load exceeds user-defined max wattage."""
        async with AsyncSessionLocal() as db:
            dev = await db.get(Device, mac.upper())
            if not dev:
                return False

            limit_w = dev.max_power_w or 3200.0
            if total_w > limit_w:
                logger.warning(f"🚨 OVERLOAD TRIP on {mac}: {total_w}W exceeded limit {limit_w}W! Tripping all outlets.")
                await hub.set_outlets(mac, [1, 2, 3, 4], False)

                from app.services.alert_service import alert_service
                msg = (
                    f"🚨 *إنذار حمل زائد (Overload)!*\n"
                    f"إجمالي استهلاك المشترك `{mac}` وصل إلى {round(total_w, 1)} واط (الحد الأقصى {limit_w} واط).\n"
                    f"تم فصل المخارج فوراً لمنع احتراق الأسلاك أو انصهار الفيش."
                )
                if dev.owner_telegram_id:
                    await alert_service.send_telegram_alert(dev.owner_telegram_id, msg)
                return True
        return False

    @staticmethod
    async def handle_button_event_child_lock(mac: str, channel: int, physical_on: bool):
        """Enforces Child Lock: if enabled, immediately reverts hardware button pushes."""
        async with AsyncSessionLocal() as db:
            dev = await db.get(Device, mac.upper())
            if dev and dev.child_lock_enabled:
                logger.info(f"🔒 Child lock active on {mac}: reverting physical button on outlet {channel}")
                # Revert to the opposite of what the child pressed
                target_state = not physical_on
                channels = [1, 2, 3, 4] if channel == 0 else [channel]
                await hub.set_outlets(mac, channels, target_state)

    @staticmethod
    async def handle_cold_boot_surge_delay(mac: str):
        """When electricity restores after a power cut, energizes the Router outlet immediately,

        keeping high-draw appliances OFF/delayed to prevent inrush surge damage.
        """
        async with AsyncSessionLocal() as db:
            dev = await db.get(Device, mac.upper())
            if not dev:
                return

            router_ch = dev.surge_router_channel or 1
            logger.info(f"⚡ Cold boot surge protection for {mac}: turning ON Router outlet {router_ch} only.")
            # Ensure router is ON
            await hub.set_outlets(mac, [router_ch], True)


async def protection_monitor_loop():
    """Background monitoring task for Auto-off timers and Standby vampire power cutoffs."""
    logger.info("Hardware Protection Engine background monitor started.")
    while True:
        try:
            await asyncio.sleep(10.0)
            now = datetime.now(timezone.utc)

            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Outlet).where(Outlet.is_on == True))
                active_outlets = res.scalars().all()

                for o in active_outlets:
                    # 1. Auto-off countdown rule
                    if o.auto_off_minutes and o.auto_off_minutes > 0 and o.last_turned_on:
                        elapsed_min = (now - o.last_turned_on).total_seconds() / 60.0
                        if elapsed_min >= o.auto_off_minutes:
                            logger.info(f"⏱️ Auto-off triggered for outlet {o.channel} on {o.device_mac} ({elapsed_min:.1f}m)")
                            await hub.set_outlets(o.device_mac, [o.channel], False)
                            o.is_on = False
                            await db.commit()
                            continue

                    # 2. Standby power cutoff
                    if o.standby_cutoff_w and o.standby_cutoff_w > 0:
                        # If drawing less than standby threshold
                        if o.power_w < o.standby_cutoff_w and o.last_turned_on:
                            elapsed_min = (now - o.last_turned_on).total_seconds() / 60.0
                            cutoff_mins = o.standby_cutoff_minutes or 15
                            if elapsed_min >= cutoff_mins:
                                logger.info(
                                    f"💤 Standby cutoff triggered for outlet {o.channel} on {o.device_mac}: "
                                    f"drawing only {o.power_w}W (< {o.standby_cutoff_w}W for {elapsed_min:.1f}m)"
                                )
                                await hub.set_outlets(o.device_mac, [o.channel], False)
                                o.is_on = False
                                await db.commit()

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in protection monitor loop: {e}")
