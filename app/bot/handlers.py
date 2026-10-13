import re
import logging
from typing import Dict, Any, Tuple
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models import User, Device, Outlet
from app.device_server.hub import hub
from app.services.device_service import DeviceService
from app.services.scheduler_service import SchedulerService
from app.services.energy_service import EnergyService
from app.bot.keyboards import (
    devices_menu_keyboard,
    device_dashboard_keyboard,
    select_outlet_for_timer_keyboard,
    timer_durations_keyboard,
    rename_menu_keyboard,
)

logger = logging.getLogger("powerk.bot.handlers")

# State for users currently renaming an outlet or device: user_id -> (mac, target_type, channel)
_pending_renames: Dict[int, Tuple[str, str, int]] = {}


async def _get_or_create_user(update: Update) -> User:
    tg_user = update.effective_user
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.telegram_id == tg_user.id))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                is_admin=False,
                notifications_enabled=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            if user.username != tg_user.username or user.first_name != tg_user.first_name:
                user.username = tg_user.username
                user.first_name = tg_user.first_name
                await db.commit()
        return user


async def _render_dashboard_text(mac: str, db_device: Device, snapshot: Dict[str, Any]) -> str:
    online = snapshot.get("online", False)
    status_str = "🟢 متصل" if online else "🔴 غير متصل"
    total_w = snapshot.get("power_w", 0.0)
    total_kwh = snapshot.get("energy_kwh", 0.0)
    voltage = snapshot.get("voltage")
    voltage_str = f"{voltage} V" if voltage else "-- V"
    current_a = snapshot.get("current_a", 0.0)
    rssi = snapshot.get("rssi")
    rssi_str = f"{rssi} dBm" if rssi else "--"

    text = (
        f"🔌 *{db_device.name}* (`{mac}`)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📶 الحالة: *{status_str}* | الإشارة: `{rssi_str}`\n"
        f"⚡ القدرة اللحظية: *{total_w} W*\n"
        f"🔋 الطاقة التراكمية: *{total_kwh} kWh*\n"
        f"⚡ الجهد: *{voltage_str}* | التيار: *{current_a} A*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"اضغط على أي مخرج لتشغيله أو إيقافه:"
    )
    return text


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_or_create_user(update)
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Device).where(Device.owner_telegram_id == user.telegram_id))
        devices = list(res.scalars().all())

    if not devices:
        # Check if there are any devices connected that have no owner
        unclaimed_list = []
        for mac, dev in hub.devices.items():
            async with AsyncSessionLocal() as db:
                db_d = await DeviceService.get_device(db, mac)
                if db_d and not db_d.owner_telegram_id:
                    unclaimed_list.append(db_d)

        welcome_text = (
            f"👋 أهلاً بك يا *{update.effective_user.first_name}* في بوت المشترك الذكي ⚡\n"
            f"(البديل الكامل لتطبيق Voltra — تحكم بكل المخارج والمؤقتات وسجل الكهرباء)\n\n"
            f"لم تقم بربط أي مشترك بحسابك بعد.\n"
        )
        if unclaimed_list:
            welcome_text += "\nتم اكتشاف المشتركات التالية المتصلة بالخادم، اضغط لربطها:\n"
            for d in unclaimed_list:
                welcome_text += f"• `{d.mac}` ({d.name})\n"
            welcome_text += "\nأو أرسل عنوان الماك (MAC Address) مباشرة في رسالة."
        else:
            welcome_text += (
                "\nلربط مشتركك، قم بتوصيله بالكهرباء ثم أرسل عنوان الماك (MAC Address) الخاص به "
                "(المكتوب على ظهر المشترك أو في إعدادات الواي فاي)."
            )

        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
        return

    if len(devices) == 1:
        dev = devices[0]
        snap = hub.devices[dev.mac].snapshot() if dev.mac in hub.devices else dev.__dict__
        snap["online"] = dev.mac in hub.sessions
        async with AsyncSessionLocal() as db:
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == dev.mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}

        text = await _render_dashboard_text(dev.mac, dev, snap)
        kb = device_dashboard_keyboard(dev.mac, snap, outlets_db, multi_device=False)
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        text = "⚡ *المشتركات المسجلة بحسابك:*\nاختر المشترك الذي تريد التحكم به:"
        kb = devices_menu_keyboard(devices)
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user = await _get_or_create_user(update)

    # 1. View Device
    if data.startswith("cb:view:"):
        mac = data.split(":")[2]
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            if not dev:
                await query.edit_message_text("❌ المشترك غير موجود.")
                return
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = hub.devices[mac].snapshot() if mac in hub.devices else {"online": False, "outlets": []}
        text = await _render_dashboard_text(mac, dev, snap)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 2. Toggle Outlet
    elif data.startswith("cb:toggle:"):
        parts = data.split(":")
        mac, ch, action = parts[2], int(parts[3]), parts[4]
        is_on = action == "on"

        # Execute toggle
        await DeviceService.toggle_outlet(mac, ch, is_on)

        # Re-fetch state
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            if not dev:
                return
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = hub.devices[mac].snapshot() if mac in hub.devices else {"online": False, "outlets": []}
        text = await _render_dashboard_text(mac, dev, snap)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    # 3. Refresh State
    elif data.startswith("cb:refresh:"):
        mac = data.split(":")[2]
        session = hub.get_session(mac)
        if session:
            await session.refresh()
            await session.diagnostics()

        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            if not dev:
                return
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = hub.devices[mac].snapshot() if mac in hub.devices else {"online": False, "outlets": []}
        text = await _render_dashboard_text(mac, dev, snap)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi)
        try:
            await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass

    # 4. Timer Select Outlet
    elif data.startswith("cb:timer_ch:"):
        mac = data.split(":")[2]
        async with AsyncSessionLocal() as db:
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
        text = "⏱️ *اختر المخرج لضبط المؤقت الزمني:*"
        kb = select_outlet_for_timer_keyboard(mac, outlets_db)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 5. Timer Select Duration
    elif data.startswith("cb:timer_dur:"):
        parts = data.split(":")
        mac, ch = parts[2], int(parts[3])
        ch_name = f"مخرج {ch}" if ch > 0 else "المشترك بالكامل"
        text = f"⏱️ *اختر مدة المؤقت لإيقاف [{ch_name}]:*"
        kb = timer_durations_keyboard(mac, ch)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 6. Set Timer
    elif data.startswith("cb:set_timer:"):
        parts = data.split(":")
        mac, ch, seconds, action = parts[2], int(parts[3]), int(parts[4]), parts[5]
        await SchedulerService.create_countdown(mac, ch, action, seconds, user.telegram_id)
        minutes = seconds // 60
        ch_name = f"مخرج {ch}" if ch > 0 else "المشترك بالكامل"
        await query.answer(f"✅ تم ضبط المؤقت لإيقاف {ch_name} بعد {minutes} دقيقة", show_alert=True)

        # Return to dashboard
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = hub.devices[mac].snapshot() if mac in hub.devices else {"online": False, "outlets": []}
        text = await _render_dashboard_text(mac, dev, snap)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 7. Energy Stats
    elif data.startswith("cb:stats:"):
        mac = data.split(":")[2]
        summary = await EnergyService.get_device_summary(mac)
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            dev_name = dev.name if dev else mac

        stats_text = (
            f"📊 *تقرير استهلاك الطاقة — {dev_name}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⚡ استهلاك اليوم: *{summary['today_kwh']} kWh*\n"
            f"💰 تكلفة اليوم التقديرية: *{summary['today_cost_egp']} جنيه*\n"
            f"🔋 الاستهلاك الكلي المسجل: *{summary['total_kwh']} kWh*\n"
            f"💵 التكلفة الكلية التقديرية: *{summary['total_cost_egp']} جنيه*\n"
            f"🏷️ سعر الكيلووات المحسوب: *{summary['rate_per_kwh']} ج.م*\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=f"cb:view:{mac}")]])
        await query.edit_message_text(stats_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 8. Rename Menu
    elif data.startswith("cb:rename_menu:"):
        mac = data.split(":")[2]
        async with AsyncSessionLocal() as db:
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
        text = "✏️ *اختر ما تريد إعادة تسميته:*"
        kb = rename_menu_keyboard(mac, outlets_db)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 9. Prompt Rename
    elif data.startswith("cb:prompt_rename:"):
        parts = data.split(":")
        mac, target_type, ch = parts[2], parts[3], int(parts[4])
        _pending_renames[user.telegram_id] = (mac, target_type, ch)
        target_label = "اسم المشترك" if target_type == "dev" else f"المخرج {ch}"
        await query.edit_message_text(
            f"✏️ أرسل الآن في رسالة الاسم الجديد لـ *{target_label}* (مثال: الراوتر، التلفزيون، شاحن اللابتوب):",
            parse_mode=ParseMode.MARKDOWN
        )

    # 10. List Devices
    elif data == "cb:list_devices":
        async with AsyncSessionLocal() as db:
            devices = await DeviceService.get_all_devices(db, user.telegram_id)
        text = "⚡ *المشتركات المسجلة بحسابك:*\nاختر المشترك الذي تريد التحكم به:"
        kb = devices_menu_keyboard(devices)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 11. Claim Prompt
    elif data == "cb:claim_prompt":
        await query.edit_message_text(
            "➕ لربط مشترك جديد، أرسل عنوان الماك (MAC Address) الخاص به في رسالة نصية مباشرة.",
            parse_mode=ParseMode.MARKDOWN
        )


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user = await _get_or_create_user(update)

    # Check if user is in renaming state
    if user.telegram_id in _pending_renames:
        mac, target_type, ch = _pending_renames.pop(user.telegram_id)
        async with AsyncSessionLocal() as db:
            if target_type == "dev":
                await DeviceService.rename_device(db, mac, text)
                await update.message.reply_text(f"✅ تم تغيير اسم المشترك إلى: *{text}*", parse_mode=ParseMode.MARKDOWN)
            else:
                await DeviceService.rename_outlet(db, mac, ch, text)
                await update.message.reply_text(f"✅ تم تغيير اسم مخرج {ch} إلى: *{text}*", parse_mode=ParseMode.MARKDOWN)
        # Show updated dashboard
        await start_command(update, context)
        return

    # Check if user is trying to claim a MAC address (e.g. "AABBCCDDEEFF" or "AA:BB:CC:DD:EE:FF" or 7-12 hex chars)
    clean_mac = re.sub(r"[:\-\s]", "", text).upper()
    if 6 <= len(clean_mac) <= 12 and all(c in "0123456789ABCDEF" for c in clean_mac):
        # Look for matching device in DB or Hub
        matched_mac = None
        for dev_mac in hub.devices.keys():
            if clean_mac in dev_mac:
                matched_mac = dev_mac
                break

        if not matched_mac:
            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Device.mac))
                all_macs = res.scalars().all()
                for m in all_macs:
                    if clean_mac in m:
                        matched_mac = m
                        break

        if not matched_mac:
            matched_mac = clean_mac  # assume exact or pre-registration

        async with AsyncSessionLocal() as db:
            ok, msg = await DeviceService.claim_device(db, matched_mac, user.telegram_id)
            await update.message.reply_text(msg)
            if ok:
                await start_command(update, context)
            return

    await update.message.reply_text(
        "⚡ للتحكم بمشتركك أو ربط جهاز جديد، استخدم الأمر /start",
        parse_mode=ParseMode.MARKDOWN
    )
