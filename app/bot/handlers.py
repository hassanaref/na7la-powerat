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
# In-memory preference for user language: user_id -> "en" or "ar"
_user_lang_pref: Dict[int, str] = {}


def get_user_lang(update: Update) -> str:
    user_id = update.effective_user.id if update.effective_user else 0
    if user_id in _user_lang_pref:
        return _user_lang_pref[user_id]
    user_code = getattr(update.effective_user, "language_code", "en") or "en"
    return "ar" if user_code.lower().startswith("ar") else "en"


def set_user_lang(user_id: int, lang: str):
    _user_lang_pref[user_id] = lang


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


def make_device_snapshot(dev: Device, hub_dev: Optional[Any] = None) -> dict:
    if hub_dev:
        return hub_dev.snapshot()
    outlets_list = []
    total_w = 0.0
    total_kwh = 0.0
    has_on = False
    for o in dev.outlets:
        outlets_list.append({
            "channel": o.channel,
            "on": o.is_on,
            "power_w": o.power_w,
            "energy_kwh": o.energy_kwh,
            "temp_c": o.temp_c,
        })
        total_w += o.power_w
        total_kwh += o.energy_kwh
        if o.is_on:
            has_on = True
    return {
        "mac": dev.mac,
        "name": dev.name,
        "model": dev.model,
        "fw": dev.fw,
        "ip": dev.ip,
        "online": dev.mac in hub.sessions,
        "on": has_on,
        "power_w": round(total_w, 2),
        "energy_kwh": round(total_kwh, 3),
        "voltage": dev.voltage_v,
        "current_a": 0.0,
        "rssi": dev.rssi,
        "outlets": outlets_list,
    }


async def _render_dashboard_text(mac: str, db_device: Device, snapshot: Dict[str, Any], lang: str = "en") -> str:
    online = snapshot.get("online", False)
    total_w = snapshot.get("power_w", 0.0)
    total_kwh = snapshot.get("energy_kwh", 0.0)
    voltage = snapshot.get("voltage")
    current_a = snapshot.get("current_a", 0.0)
    rssi = snapshot.get("rssi")

    if lang == "en":
        status_str = "🟢 Online" if online else "🔴 Offline"
        voltage_str = f"{voltage} V" if voltage else "-- V"
        rssi_str = f"{rssi} dBm" if rssi else "--"
        text = (
            f"🔌 *{db_device.name}* (`{mac}`)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📶 Status: *{status_str}* | Signal: `{rssi_str}`\n"
            f"⚡ Active Power: *{total_w} W*\n"
            f"🔋 Total Energy: *{total_kwh} kWh*\n"
            f"⚡ Voltage: *{voltage_str}* | Current: *{current_a} A*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Tap any outlet button below to switch ON/OFF:"
        )
    else:
        status_str = "🟢 متصل" if online else "🔴 غير متصل"
        voltage_str = f"{voltage} V" if voltage else "-- V"
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
    lang = get_user_lang(update)

    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Device).where(Device.owner_telegram_id == user.telegram_id))
        devices = list(res.scalars().all())

    if not devices:
        # Check unclaimed devices currently in hub
        unclaimed_list = []
        for mac, dev in hub.devices.items():
            async with AsyncSessionLocal() as db:
                db_d = await DeviceService.get_device(db, mac)
                if db_d and not db_d.owner_telegram_id:
                    unclaimed_list.append(db_d)

        if lang == "en":
            welcome_text = (
                f"👋 Welcome *{update.effective_user.first_name}* to **Na7la Powerat Bot** 🐝⚡\n"
                f"(Your smart control hub — replace Voltra with full outlet control, timers, and power monitoring!)\n\n"
                f"No smart strip is linked to your account yet.\n"
            )
            if unclaimed_list:
                welcome_text += "\nDetected active strips on server:\n"
                for d in unclaimed_list:
                    welcome_text += f"• `{d.mac}` ({d.name})\n"
                welcome_text += "\nSend the MAC address in a message to claim it."
            else:
                welcome_text += (
                    "\nTo link your strip, power it on and send its **MAC Address** here "
                    "(found on the sticker on the back of the strip or during Wi-Fi setup, e.g. `91C0C4C11223`)."
                )
        else:
            welcome_text = (
                f"👋 أهلاً بك يا *{update.effective_user.first_name}* في **بوت نحلة باورات** 🐝⚡\n"
                f"(البديل الكامل لتطبيق Voltra — تحكم بكل المخارج والمؤقتات وسجل الكهرباء)\n\n"
                f"لم تقم بربط أي مشترك بحسابك بعد.\n"
            )
            if unclaimed_list:
                welcome_text += "\nتم اكتشاف المشتركات التالية المتصلة بالخادم:\n"
                for d in unclaimed_list:
                    welcome_text += f"• `{d.mac}` ({d.name})\n"
                welcome_text += "\nأرسل عنوان الماك (MAC Address) مباشرة في رسالة لربطه."
            else:
                welcome_text += (
                    "\nلربط مشتركك، قم بتوصيله بالكهرباء ثم أرسل عنوان الماك (MAC Address) الخاص به "
                    "(المكتوب على ظهر المشترك أو في إعدادات الواي فاي)."
                )

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        lang_toggle = "🌐 العربية" if lang == "en" else "🌐 English"
        target_lang = "ar" if lang == "en" else "en"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(lang_toggle, callback_data=f"cb:set_lang:{target_lang}")]])

        await update.message.reply_text(welcome_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
        return

    if len(devices) == 1:
        dev = devices[0]
        snap = make_device_snapshot(dev, hub.devices.get(dev.mac))
        async with AsyncSessionLocal() as db:
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == dev.mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}

        text = await _render_dashboard_text(dev.mac, dev, snap, lang=lang)
        kb = device_dashboard_keyboard(dev.mac, snap, outlets_db, multi_device=False, lang=lang)
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)
    else:
        text = "⚡ *Your Registered Strips:*\nChoose a device to control:" if lang == "en" else "⚡ *المشتركات المسجلة بحسابك:*\nاختر المشترك الذي تريد التحكم به:"
        kb = devices_menu_keyboard(devices, lang=lang)
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)


async def set_lang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cmd = update.message.text.lower()
    lang = "ar" if "ar" in cmd else "en"
    set_user_lang(update.effective_user.id, lang)
    msg = "Language switched to English 🇬🇧" if lang == "en" else "تم تغيير اللغة إلى العربية 🇪🇬"
    await update.message.reply_text(msg)
    await start_command(update, context)


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    user = await _get_or_create_user(update)
    lang = get_user_lang(update)

    # Language switcher callback
    if data.startswith("cb:set_lang:"):
        parts = data.split(":")
        new_lang = parts[2]
        set_user_lang(user.telegram_id, new_lang)
        lang = new_lang
        mac = parts[3] if len(parts) > 3 else None
        if mac:
            data = f"cb:view:{mac}"
        else:
            data = "cb:list_devices"

    # 1. View Device
    if data.startswith("cb:view:"):
        mac = data.split(":")[2]
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            if not dev:
                err = "❌ Device not found." if lang == "en" else "❌ المشترك غير موجود."
                await query.edit_message_text(err)
                return
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = make_device_snapshot(dev, hub.devices.get(mac))
        text = await _render_dashboard_text(mac, dev, snap, lang=lang)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi, lang=lang)
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

        snap = make_device_snapshot(dev, hub.devices.get(mac))
        text = await _render_dashboard_text(mac, dev, snap, lang=lang)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi, lang=lang)
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

        snap = make_device_snapshot(dev, hub.devices.get(mac))
        text = await _render_dashboard_text(mac, dev, snap, lang=lang)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi, lang=lang)
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
        text = "⏱️ *Select outlet to set timer:*" if lang == "en" else "⏱️ *اختر المخرج لضبط المؤقت الزمني:*"
        kb = select_outlet_for_timer_keyboard(mac, outlets_db, lang=lang)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 5. Timer Select Duration
    elif data.startswith("cb:timer_dur:"):
        parts = data.split(":")
        mac, ch = parts[2], int(parts[3])
        if lang == "en":
            ch_name = f"Outlet {ch}" if ch > 0 else "All Outlets"
            text = f"⏱️ *Select timer duration to turn off [{ch_name}]:*"
        else:
            ch_name = f"مخرج {ch}" if ch > 0 else "المشترك بالكامل"
            text = f"⏱️ *اختر مدة المؤقت لإيقاف [{ch_name}]:*"
        kb = timer_durations_keyboard(mac, ch, lang=lang)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 6. Set Timer
    elif data.startswith("cb:set_timer:"):
        parts = data.split(":")
        mac, ch, seconds, action = parts[2], int(parts[3]), int(parts[4]), parts[5]
        await SchedulerService.create_countdown(mac, ch, action, seconds, user.telegram_id)
        minutes = seconds // 60
        if lang == "en":
            ch_name = f"Outlet {ch}" if ch > 0 else "All Outlets"
            alert_msg = f"✅ Timer set: turning off {ch_name} in {minutes} minutes."
        else:
            ch_name = f"مخرج {ch}" if ch > 0 else "المشترك بالكامل"
            alert_msg = f"✅ تم ضبط المؤقت لإيقاف {ch_name} بعد {minutes} دقيقة."
        await query.answer(alert_msg, show_alert=True)

        # Return to dashboard
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
            multi = len(await DeviceService.get_all_devices(db, user.telegram_id)) > 1

        snap = make_device_snapshot(dev, hub.devices.get(mac))
        text = await _render_dashboard_text(mac, dev, snap, lang=lang)
        kb = device_dashboard_keyboard(mac, snap, outlets_db, multi_device=multi, lang=lang)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 7. Energy Stats
    elif data.startswith("cb:stats:"):
        mac = data.split(":")[2]
        summary = await EnergyService.get_device_summary(mac)
        async with AsyncSessionLocal() as db:
            dev = await DeviceService.get_device(db, mac)
            dev_name = dev.name if dev else mac

        if lang == "en":
            stats_text = (
                f"📊 *Power Consumption Report — {dev_name}*\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"⚡ Today's Energy: *{summary['today_kwh']} kWh*\n"
                f"💰 Today's Est. Cost: *{summary['today_cost_egp']} EGP*\n"
                f"🔋 Total Recorded Energy: *{summary['total_kwh']} kWh*\n"
                f"💵 Total Est. Cost: *{summary['total_cost_egp']} EGP*\n"
                f"🏷️ Electricity Tariff: *{summary['rate_per_kwh']} EGP/kWh*\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
            back_text = "🔙 Back"
        else:
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
            back_text = "🔙 رجوع"

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(back_text, callback_data=f"cb:view:{mac}")]])
        await query.edit_message_text(stats_text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 8. Rename Menu
    elif data.startswith("cb:rename_menu:"):
        mac = data.split(":")[2]
        async with AsyncSessionLocal() as db:
            outlets_res = await db.execute(select(Outlet).where(Outlet.device_mac == mac))
            outlets_db = {o.channel: o for o in outlets_res.scalars().all()}
        text = "✏️ *Select item to rename:*" if lang == "en" else "✏️ *اختر ما تريد إعادة تسميته:*"
        kb = rename_menu_keyboard(mac, outlets_db, lang=lang)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 9. Prompt Rename
    elif data.startswith("cb:prompt_rename:"):
        parts = data.split(":")
        mac, target_type, ch = parts[2], parts[3], int(parts[4])
        _pending_renames[user.telegram_id] = (mac, target_type, ch)
        if lang == "en":
            target_label = "Strip Name" if target_type == "dev" else f"Outlet {ch}"
            prompt_text = f"✏️ Send the new name for *{target_label}* in a message (e.g. Router, TV, Laptop Charger):"
        else:
            target_label = "اسم المشترك" if target_type == "dev" else f"المخرج {ch}"
            prompt_text = f"✏️ أرسل الآن في رسالة الاسم الجديد لـ *{target_label}* (مثال: الراوتر، التلفزيون، شاحن اللابتوب):"
        await query.edit_message_text(prompt_text, parse_mode=ParseMode.MARKDOWN)

    # 10. List Devices
    elif data == "cb:list_devices":
        async with AsyncSessionLocal() as db:
            devices = await DeviceService.get_all_devices(db, user.telegram_id)
        text = "⚡ *Your Registered Strips:*\nChoose a device to control:" if lang == "en" else "⚡ *المشتركات المسجلة بحسابك:*\nاختر المشترك الذي تريد التحكم به:"
        kb = devices_menu_keyboard(devices, lang=lang)
        await query.edit_message_text(text, reply_markup=kb, parse_mode=ParseMode.MARKDOWN)

    # 11. Claim Prompt
    elif data == "cb:claim_prompt":
        prompt_text = (
            "➕ To link a new strip, send its **MAC Address** in a message (e.g. `91C0C4C11223`)."
            if lang == "en" else
            "➕ لربط مشترك جديد، أرسل عنوان الماك (MAC Address) الخاص به في رسالة نصية مباشرة."
        )
        await query.edit_message_text(prompt_text, parse_mode=ParseMode.MARKDOWN)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip()
    user = await _get_or_create_user(update)
    lang = get_user_lang(update)

    # Check language commands
    if text.lower() in ("/en", "/english"):
        set_user_lang(user.telegram_id, "en")
        await update.message.reply_text("Language set to English 🇬🇧")
        await start_command(update, context)
        return
    elif text.lower() in ("/ar", "/arabic"):
        set_user_lang(user.telegram_id, "ar")
        await update.message.reply_text("تم ضبط اللغة على العربية 🇪🇬")
        await start_command(update, context)
        return

    # Check if user is in renaming state
    if user.telegram_id in _pending_renames:
        mac, target_type, ch = _pending_renames.pop(user.telegram_id)
        async with AsyncSessionLocal() as db:
            if target_type == "dev":
                await DeviceService.rename_device(db, mac, text)
                ack = f"✅ Renamed strip to: *{text}*" if lang == "en" else f"✅ تم تغيير اسم المشترك إلى: *{text}*"
                await update.message.reply_text(ack, parse_mode=ParseMode.MARKDOWN)
            else:
                await DeviceService.rename_outlet(db, mac, ch, text)
                ack = f"✅ Renamed Outlet {ch} to: *{text}*" if lang == "en" else f"✅ تم تغيير اسم مخرج {ch} إلى: *{text}*"
                await update.message.reply_text(ack, parse_mode=ParseMode.MARKDOWN)
        # Show updated dashboard
        await start_command(update, context)
        return

    # Check if user is trying to claim a MAC address (e.g. "2CE0.32C6.E5E7", "2C:E0:32:C6:E5:E7", "2CE032C6E5E7")
    clean_mac = re.sub(r"[^0-9A-Fa-f]", "", text).upper()
    if 6 <= len(clean_mac) <= 12:
        matched_mac = None
        for dev_mac in hub.devices.keys():
            if clean_mac in dev_mac or dev_mac in clean_mac:
                matched_mac = dev_mac
                break

        if not matched_mac:
            async with AsyncSessionLocal() as db:
                res = await db.execute(select(Device.mac))
                all_macs = res.scalars().all()
                for m in all_macs:
                    if clean_mac in m or m in clean_mac:
                        matched_mac = m
                        break

        if not matched_mac:
            matched_mac = clean_mac

        async with AsyncSessionLocal() as db:
            ok, msg = await DeviceService.claim_device(db, matched_mac, user.telegram_id)
            if lang == "en":
                msg = f"✅ Smart Strip [{matched_mac}] linked successfully to your account!" if ok else f"❌ {msg}"
            await update.message.reply_text(msg)
            if ok:
                await start_command(update, context)
            return

    help_msg = (
        "⚡ Send /start to open the dashboard, or send a MAC address to link a device."
        if lang == "en" else
        "⚡ للتحكم بمشتركك أو ربط جهاز جديد، استخدم الأمر /start"
    )
    await update.message.reply_text(help_msg, parse_mode=ParseMode.MARKDOWN)
