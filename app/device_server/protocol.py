import re
from typing import Any

BOOTINFO_RE = re.compile(
    r"^up:bootinfo:([^;\r\n]+);([0-9A-Fa-f]{12});([0-9A-Fa-f]{12});([^;\r\n]+);connect$"
)

GETINFO_RE = re.compile(
    r"(?P<ch>[1-5]):(?P<runtime>-?\d+);(?P<relay>on|off);(?P<state>-?\d+);"
    r"(?P<overload>[^;:]+);(?P<overheat>[^;:]+);(?P<power>-?\d+);"
    r"(?P<energy>[0-9A-Fa-f]{8});(?P<previous>[0-9A-Fa-f]{8});"
    r"(?P<config>[0-9A-Fa-f]{8});(?P<status>[^;:]+);"
    r"(?P<event>[0-9A-Fa-f]{2});(?P<temperature>-?\d+)",
    re.I,
)

ONOFF_ACK_RE = re.compile(r"^up:onoff:([1-4]):(on|off)$", re.I)
EVENT_RE = re.compile(r"^up:event:onoff:([0-4]):(on|off)$", re.I)
POWER_REPORT_RE = re.compile(r"^up:power_report:([1-5]):(-?\d+)$", re.I)
QUERY_RE = re.compile(r"^up:query:(-?\d+)$")


def parse_getinfo(line: str) -> list[dict[str, Any]]:
    """Parse 'up:getinfo:...' into per-outlet records (1-4). Channel 5 is aggregate, ignored here."""
    text = line.strip("\r\n\x00 ")
    if text.startswith("up:getinfo:"):
        text = text[len("up:getinfo:"):]
    out = []
    for m in GETINFO_RE.finditer(text):
        g = m.groupdict()
        ch = int(g["ch"])
        if ch > 4:
            continue
        out.append({
            "channel": ch,
            "on": g["relay"].lower() == "on",
            "power_w": round(int(g["power"]) / 1000.0, 2),
            "energy_kwh": round(int(g["energy"], 16) / 1000.0, 3),
            "temp_c": int(g["temperature"]),
        })
    return out


def cmd_getinfo_all() -> str:
    return "up:getinfo:all"


def cmd_onoff(channel: int, on: bool) -> str:
    return f"up:onoff:{channel}:{'on' if on else 'off'}"


def cmd_diagnostics_vol() -> str:
    return "up:power_report:1:vol"


def cmd_diagnostics_rssi() -> str:
    return "up:query:wifirssi"
