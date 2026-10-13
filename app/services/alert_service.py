import asyncio
from datetime import datetime, timezone
import logging
from typing import Callable, Coroutine, Any, Optional
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import Device, User
from app.device_server.hub import hub

logger = logging.getLogger("powerk.alert")

# Callback to send telegram message: func(chat_id: int, text: str)
_telegram_sender: Optional[Callable[[int, str], Coroutine[Any, Any, None]]] = None


def set_telegram_sender(sender: Callable[[int, str], Coroutine[Any, Any, None]]):
    global _telegram_sender
    _telegram_sender = sender


class AlertService:
    @staticmethod
    async def notify_owner(mac: str, message: str):
        if not _telegram_sender:
            return
        async with AsyncSessionLocal() as db:
            res = await db.execute(select(Device).where(Device.mac == mac.upper()))
            dev = res.scalar_one_or_none()
            if not dev or not dev.owner_telegram_id:
                return

            # Check user notification preference
            res_user = await db.execute(select(User).where(User.telegram_id == dev.owner_telegram_id))
            user = res_user.scalar_one_or_none()
            if user and not user.notifications_enabled:
                return

            try:
                await _telegram_sender(dev.owner_telegram_id, message)
            except Exception as e:
                logger.error(f"Failed to send alert to telegram user {dev.owner_telegram_id}: {e}")

    @staticmethod
    async def on_device_connected(mac: str, ip: str, model: str, fw: str):
        dev = hub.get_device(mac)
        dev_name = dev.name if dev else mac
        msg = (
            f"⚡ *عودة الاتصال / التيار الكهربائي*\n"
            f"المشترك: `{dev_name}`\n"
            f"عنوان IP: `{ip}`\n"
            f"الحالة: متصل وجاهز للتحكم."
        )
        await AlertService.notify_owner(mac, msg)

    @staticmethod
    async def on_device_disconnected(mac: str):
        dev = hub.get_device(mac)
        dev_name = dev.name if dev else mac
        msg = (
            f"⚠️ *انقطاع الكهرباء أو الاتصال*\n"
            f"المشترك: `{dev_name}`\n"
            f"الحالة: غير متصل (Offline).\n"
            f"قد يكون حدث انقطاع في التيار الكهربائي بالمنزل أو في شبكة الواي فاي."
        )
        await AlertService.notify_owner(mac, msg)

    @staticmethod
    async def on_state_updated(mac: str, snapshot: dict):
        # 1. Check overload
        power_w = snapshot.get("power_w", 0)
        current_a = snapshot.get("current_a", 0)
        if power_w > 3500 or current_a > 15.5:
            msg = (
                f"🚨 *تحذير حمل زائد (Overload Alert)!*\n"
                f"المشترك: `{snapshot.get('name')}`\n"
                f"القدرة الحالية: *{power_w} W* | التيار: *{current_a} A*\n"
                f"يرجى فصل بعض الأجهزة لتجنب تلف المشترك أو حدوث ماس كهربائي!"
            )
            await AlertService.notify_owner(mac, msg)

        # 2. Check overheat
        max_temp = max((o.get("temp_c", 0) for o in snapshot.get("outlets", [])), default=0)
        if max_temp >= 65:
            msg = (
                f"🔥 *تحذير حرارة مرتفعة (Overheat Alert)!*\n"
                f"المشترك: `{snapshot.get('name')}`\n"
                f"درجة الحرارة: *{max_temp} °C*\n"
                f"الحرارة مرتفعة جداً، يرجى فحص المشترك فوراً!"
            )
            await AlertService.notify_owner(mac, msg)


# Register listeners to hub
hub.register_listener("device_connected", AlertService.on_device_connected)
hub.register_listener("device_disconnected", AlertService.on_device_disconnected)
hub.register_listener("state_updated", AlertService.on_state_updated)
