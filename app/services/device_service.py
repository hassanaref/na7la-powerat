from datetime import datetime, timezone
import logging
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models import Device, Outlet, User
from app.device_server.hub import hub

logger = logging.getLogger("powerk.device_service")


def utcnow():
    return datetime.now(timezone.utc)


class DeviceService:
    @staticmethod
    async def on_device_connected(mac: str, ip: str, model: str, fw: str):
        """Sync incoming TCP device to DB."""
        mac = mac.upper()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Device).where(Device.mac == mac))
            device = result.scalar_one_or_none()

            if not device:
                device = Device(
                    mac=mac,
                    name=f"مشترك {mac[-4:]}",
                    model=model,
                    fw=fw,
                    ip=ip,
                    online=True,
                    last_seen=utcnow()
                )
                db.add(device)
                await db.flush()

                # Add the 4 outlets
                for ch in range(1, 5):
                    outlet = Outlet(
                        device_mac=mac,
                        channel=ch,
                        name=f"مخرج {ch}",
                        is_on=False
                    )
                    db.add(outlet)
            else:
                device.ip = ip
                device.model = model
                device.fw = fw
                device.online = True
                device.last_seen = utcnow()

            await db.commit()
            logger.info(f"Database synced for device {mac} (online)")

    @staticmethod
    async def on_device_disconnected(mac: str):
        mac = mac.upper()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Device).where(Device.mac == mac))
            device = result.scalar_one_or_none()
            if device:
                device.online = False
                device.last_seen = utcnow()
                await db.commit()
                logger.info(f"Database synced for device {mac} (offline)")

    @staticmethod
    async def on_state_updated(mac: str, snapshot: dict):
        mac = mac.upper()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Device).where(Device.mac == mac))
            device = result.scalar_one_or_none()
            if not device:
                return

            device.online = True
            device.last_seen = utcnow()
            device.voltage_v = snapshot.get("voltage")
            device.rssi = snapshot.get("rssi")

            # Update outlets
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            db_outlets = {o.channel: o for o in outlets_res.scalars().all()}

            for o_snap in snapshot.get("outlets", []):
                ch = o_snap["channel"]
                if ch in db_outlets:
                    db_outlets[ch].is_on = o_snap["on"]
                    db_outlets[ch].power_w = o_snap["power_w"]
                    db_outlets[ch].energy_kwh = o_snap["energy_kwh"]
                    db_outlets[ch].temp_c = o_snap["temp_c"]

            await db.commit()

    @staticmethod
    async def get_device(db: AsyncSession, mac: str) -> Optional[Device]:
        res = await db.execute(select(Device).where(Device.mac == mac.upper()))
        return res.scalar_one_or_none()

    @staticmethod
    async def get_all_devices(db: AsyncSession, user_telegram_id: Optional[int] = None) -> List[Device]:
        stmt = select(Device)
        if user_telegram_id is not None:
            stmt = stmt.where(Device.owner_telegram_id == user_telegram_id)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def rename_device(db: AsyncSession, mac: str, name: str) -> bool:
        device = await DeviceService.get_device(db, mac)
        if not device:
            return False
        device.name = name.strip()
        await db.commit()
        return True

    @staticmethod
    async def rename_outlet(db: AsyncSession, mac: str, channel: int, name: str) -> bool:
        res = await db.execute(
            select(Outlet).where(Outlet.device_mac == mac.upper(), Outlet.channel == channel)
        )
        outlet = res.scalar_one_or_none()
        if not outlet:
            return False
        outlet.name = name.strip()
        await db.commit()
        return True

    @staticmethod
    async def claim_device(db: AsyncSession, mac: str, user_telegram_id: int) -> tuple[bool, str]:
        device = await DeviceService.get_device(db, mac)
        if not device:
            return False, "الجهاز غير موجود. تأكد من عنوان الماك أو قم بتوصيله بالكهرباء أولاً."

        if device.owner_telegram_id and device.owner_telegram_id != user_telegram_id:
            return False, "هذا المشترك مربوط بالفعل بحساب مستخدم آخر."

        device.owner_telegram_id = user_telegram_id
        await db.commit()
        return True, f"تم ربط المشترك [{device.name}] بنجاح!"

    @staticmethod
    async def unclaim_device(db: AsyncSession, mac: str, user_telegram_id: int) -> bool:
        device = await DeviceService.get_device(db, mac)
        if not device or device.owner_telegram_id != user_telegram_id:
            return False
        device.owner_telegram_id = None
        await db.commit()
        return True

    @staticmethod
    async def toggle_outlet(mac: str, channel: int, on: bool) -> bool:
        channels = [1, 2, 3, 4] if channel == 0 else [channel]
        return await hub.set_outlets(mac.upper(), channels, on)


# Register listeners to hub
hub.register_listener("device_connected", DeviceService.on_device_connected)
hub.register_listener("device_disconnected", DeviceService.on_device_disconnected)
hub.register_listener("state_updated", DeviceService.on_state_updated)
