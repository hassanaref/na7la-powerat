from typing import List, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.models import Device, Outlet


def devices_menu_keyboard(devices: List[Device], lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for d in devices:
        status = "🟢" if d.online else "🔴"
        buttons.append([InlineKeyboardButton(f"{status} {d.name} ({d.mac[-4:]})", callback_data=f"cb:view:{d.mac}")])

    claim_label = "➕ Link New Strip" if lang == "en" else "➕ ربط مشترك إضافي"
    buttons.append([InlineKeyboardButton(claim_label, callback_data="cb:claim_prompt")])

    lang_toggle = "🌐 العربية" if lang == "en" else "🌐 English"
    target_lang = "ar" if lang == "en" else "en"
    buttons.append([InlineKeyboardButton(lang_toggle, callback_data=f"cb:set_lang:{target_lang}")])

    return InlineKeyboardMarkup(buttons)


def device_dashboard_keyboard(
    mac: str,
    snapshot: Dict[str, Any],
    outlets_db: Dict[int, Outlet],
    multi_device: bool = False,
    lang: str = "en"
) -> InlineKeyboardMarkup:
    buttons = []

    # 4 Outlets rows
    outlets_snap = {o["channel"]: o for o in snapshot.get("outlets", [])}
    for ch in range(1, 5):
        snap_o = outlets_snap.get(ch, {"on": False, "power_w": 0.0, "temp_c": 0})
        is_on = snap_o["on"]
        power_w = snap_o["power_w"]

        default_name = f"Outlet {ch}" if lang == "en" else f"مخرج {ch}"
        custom_name = outlets_db[ch].name if ch in outlets_db else default_name
        status_icon = "🟢" if is_on else "⚪"
        action_target = "off" if is_on else "on"

        btn_text = f"{status_icon} {ch}. {custom_name} | {power_w}W"
        cb_data = f"cb:toggle:{mac}:{ch}:{action_target}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

    # Master controls row
    all_on_text = "⚡ Turn All ON" if lang == "en" else "⚡ تشغيل الكل"
    all_off_text = "🛑 Turn All OFF" if lang == "en" else "🛑 إيقاف الكل"
    buttons.append([
        InlineKeyboardButton(all_on_text, callback_data=f"cb:toggle:{mac}:0:on"),
        InlineKeyboardButton(all_off_text, callback_data=f"cb:toggle:{mac}:0:off")
    ])

    # Features row (Timers & Renaming)
    timer_text = "⏱️ Timer" if lang == "en" else "⏱️ مؤقت زمني"
    rename_text = "✏️ Rename" if lang == "en" else "✏️ تغيير الأسماء"
    buttons.append([
        InlineKeyboardButton(timer_text, callback_data=f"cb:timer_ch:{mac}"),
        InlineKeyboardButton(rename_text, callback_data=f"cb:rename_menu:{mac}")
    ])

    # Stats & Refresh row
    stats_text = "📊 Power Stats" if lang == "en" else "📊 استهلاك الكهرباء"
    refresh_text = "🔄 Refresh" if lang == "en" else "🔄 تحديث"
    buttons.append([
        InlineKeyboardButton(stats_text, callback_data=f"cb:stats:{mac}"),
        InlineKeyboardButton(refresh_text, callback_data=f"cb:refresh:{mac}")
    ])

    # Language toggle & Device list
    bottom_row = []
    if multi_device:
        list_text = "🔙 Devices" if lang == "en" else "🔙 قائمة المشتركات"
        bottom_row.append(InlineKeyboardButton(list_text, callback_data="cb:list_devices"))

    lang_toggle = "🌐 العربية" if lang == "en" else "🌐 English"
    target_lang = "ar" if lang == "en" else "en"
    bottom_row.append(InlineKeyboardButton(lang_toggle, callback_data=f"cb:set_lang:{target_lang}:{mac}"))
    buttons.append(bottom_row)

    return InlineKeyboardMarkup(buttons)


def select_outlet_for_timer_keyboard(mac: str, outlets_db: Dict[int, Outlet], lang: str = "en") -> InlineKeyboardMarkup:
    buttons = []
    for ch in range(1, 5):
        default_name = f"Outlet {ch}" if lang == "en" else f"مخرج {ch}"
        name = outlets_db[ch].name if ch in outlets_db else default_name
        buttons.append([InlineKeyboardButton(f"{ch}. {name}", callback_data=f"cb:timer_dur:{mac}:{ch}")])

    all_label = "All Outlets (Entire Strip)" if lang == "en" else "الكل (المشترك بالكامل)"
    back_label = "🔙 Back" if lang == "en" else "🔙 رجوع"
    buttons.append([InlineKeyboardButton(all_label, callback_data=f"cb:timer_dur:{mac}:0")])
    buttons.append([InlineKeyboardButton(back_label, callback_data=f"cb:view:{mac}")])
    return InlineKeyboardMarkup(buttons)


def timer_durations_keyboard(mac: str, channel: int, lang: str = "en") -> InlineKeyboardMarkup:
    m15 = "⏱️ 15 Mins" if lang == "en" else "⏱️ 15 دقيقة"
    m30 = "⏱️ 30 Mins" if lang == "en" else "⏱️ 30 دقيقة"
    h1 = "⏱️ 1 Hour" if lang == "en" else "⏱️ 1 ساعة"
    h2 = "⏱️ 2 Hours" if lang == "en" else "⏱️ 2 ساعة"
    h4 = "⏱️ 4 Hours" if lang == "en" else "⏱️ 4 ساعات"
    h8 = "⏱️ 8 Hours" if lang == "en" else "⏱️ 8 ساعات"
    back = "🔙 Back" if lang == "en" else "🔙 رجوع"

    buttons = [
        [
            InlineKeyboardButton(m15, callback_data=f"cb:set_timer:{mac}:{channel}:900:off"),
            InlineKeyboardButton(m30, callback_data=f"cb:set_timer:{mac}:{channel}:1800:off")
        ],
        [
            InlineKeyboardButton(h1, callback_data=f"cb:set_timer:{mac}:{channel}:3600:off"),
            InlineKeyboardButton(h2, callback_data=f"cb:set_timer:{mac}:{channel}:7200:off")
        ],
        [
            InlineKeyboardButton(h4, callback_data=f"cb:set_timer:{mac}:{channel}:14400:off"),
            InlineKeyboardButton(h8, callback_data=f"cb:set_timer:{mac}:{channel}:28800:off")
        ],
        [
            InlineKeyboardButton(back, callback_data=f"cb:view:{mac}")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def rename_menu_keyboard(mac: str, outlets_db: Dict[int, Outlet], lang: str = "en") -> InlineKeyboardMarkup:
    dev_label = "🏷️ Strip Name" if lang == "en" else "🏷️ اسم المشترك بالكامل"
    buttons = [
        [InlineKeyboardButton(dev_label, callback_data=f"cb:prompt_rename:{mac}:dev:0")]
    ]
    for ch in range(1, 5):
        default_name = f"Outlet {ch}" if lang == "en" else f"مخرج {ch}"
        name = outlets_db[ch].name if ch in outlets_db else default_name
        rename_label = f"Rename Outlet {ch} ({name})" if lang == "en" else f"تسمية مخرج {ch} ({name})"
        buttons.append([
            InlineKeyboardButton(rename_label, callback_data=f"cb:prompt_rename:{mac}:out:{ch}")
        ])

    back_label = "🔙 Back" if lang == "en" else "🔙 رجوع"
    buttons.append([InlineKeyboardButton(back_label, callback_data=f"cb:view:{mac}")])
    return InlineKeyboardMarkup(buttons)
