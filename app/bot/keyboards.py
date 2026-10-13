from typing import List, Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.models import Device, Outlet


def devices_menu_keyboard(devices: List[Device]) -> InlineKeyboardMarkup:
    buttons = []
    for d in devices:
        status = "🟢" if d.online else "🔴"
        buttons.append([InlineKeyboardButton(f"{status} {d.name} ({d.mac[-4:]})", callback_data=f"cb:view:{d.mac}")])
    buttons.append([InlineKeyboardButton("➕ ربط مشترك إضافي", callback_data="cb:claim_prompt")])
    return InlineKeyboardMarkup(buttons)


def device_dashboard_keyboard(
    mac: str,
    snapshot: Dict[str, Any],
    outlets_db: Dict[int, Outlet],
    multi_device: bool = False
) -> InlineKeyboardMarkup:
    buttons = []

    # 4 Outlets rows
    outlets_snap = {o["channel"]: o for o in snapshot.get("outlets", [])}
    for ch in range(1, 5):
        snap_o = outlets_snap.get(ch, {"on": False, "power_w": 0.0, "temp_c": 0})
        is_on = snap_o["on"]
        power_w = snap_o["power_w"]

        custom_name = outlets_db[ch].name if ch in outlets_db else f"مخرج {ch}"
        status_icon = "🟢" if is_on else "⚪"
        action_target = "off" if is_on else "on"

        btn_text = f"{status_icon} {ch}. {custom_name} | {power_w}W"
        cb_data = f"cb:toggle:{mac}:{ch}:{action_target}"
        buttons.append([InlineKeyboardButton(btn_text, callback_data=cb_data)])

    # Master controls row
    buttons.append([
        InlineKeyboardButton("⚡ تشغيل الكل", callback_data=f"cb:toggle:{mac}:0:on"),
        InlineKeyboardButton("🛑 إيقاف الكل", callback_data=f"cb:toggle:{mac}:0:off")
    ])

    # Features row (Timers & Renaming)
    buttons.append([
        InlineKeyboardButton("⏱️ مؤقت زمني", callback_data=f"cb:timer_ch:{mac}"),
        InlineKeyboardButton("✏️ تغيير الأسماء", callback_data=f"cb:rename_menu:{mac}")
    ])

    # Stats & Refresh row
    buttons.append([
        InlineKeyboardButton("📊 استهلاك الكهرباء", callback_data=f"cb:stats:{mac}"),
        InlineKeyboardButton("🔄 تحديث", callback_data=f"cb:refresh:{mac}")
    ])

    if multi_device:
        buttons.append([InlineKeyboardButton("🔙 قائمة المشتركات", callback_data="cb:list_devices")])

    return InlineKeyboardMarkup(buttons)


def select_outlet_for_timer_keyboard(mac: str, outlets_db: Dict[int, Outlet]) -> InlineKeyboardMarkup:
    buttons = []
    for ch in range(1, 5):
        name = outlets_db[ch].name if ch in outlets_db else f"مخرج {ch}"
        buttons.append([InlineKeyboardButton(f"{ch}. {name}", callback_data=f"cb:timer_dur:{mac}:{ch}")])
    buttons.append([InlineKeyboardButton("الكل (المشترك بالكامل)", callback_data=f"cb:timer_dur:{mac}:0")])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cb:view:{mac}")])
    return InlineKeyboardMarkup(buttons)


def timer_durations_keyboard(mac: str, channel: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton("⏱️ 15 دقيقة", callback_data=f"cb:set_timer:{mac}:{channel}:900:off"),
            InlineKeyboardButton("⏱️ 30 دقيقة", callback_data=f"cb:set_timer:{mac}:{channel}:1800:off")
        ],
        [
            InlineKeyboardButton("⏱️ 1 ساعة", callback_data=f"cb:set_timer:{mac}:{channel}:3600:off"),
            InlineKeyboardButton("⏱️ 2 ساعة", callback_data=f"cb:set_timer:{mac}:{channel}:7200:off")
        ],
        [
            InlineKeyboardButton("⏱️ 4 ساعات", callback_data=f"cb:set_timer:{mac}:{channel}:14400:off"),
            InlineKeyboardButton("⏱️ 8 ساعات", callback_data=f"cb:set_timer:{mac}:{channel}:28800:off")
        ],
        [
            InlineKeyboardButton("🔙 رجوع", callback_data=f"cb:view:{mac}")
        ]
    ]
    return InlineKeyboardMarkup(buttons)


def rename_menu_keyboard(mac: str, outlets_db: Dict[int, Outlet]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("🏷️ اسم المشترك بالكامل", callback_data=f"cb:prompt_rename:{mac}:dev:0")]
    ]
    for ch in range(1, 5):
        name = outlets_db[ch].name if ch in outlets_db else f"مخرج {ch}"
        buttons.append([
            InlineKeyboardButton(f"تسمية مخرج {ch} ({name})", callback_data=f"cb:prompt_rename:{mac}:out:{ch}")
        ])
    buttons.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cb:view:{mac}")])
    return InlineKeyboardMarkup(buttons)
