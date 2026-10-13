#!/usr/bin/env python3
"""Na7la Powerat 2.0 (نحلة باورات) - Smart Power Strip Backend & Telegram Bot.

Commands:
  python powerk.py serve       Run FastAPI server + TCP 10086/21197 device server + Telegram Bot (default)
  python powerk.py provision   Provision the strip with Wi-Fi & server IP (while in SoftAP mode)
  python powerk.py selftest    Run offline protocol, database, and backend validation
"""
from __future__ import annotations

import argparse
import asyncio
import ipaddress
import os
import socket
import sys

# Configure UTF-8 encoding on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import settings, detect_local_ipv4

DEVICE_PORT = settings.DEVICE_PORT
SETUP_HOST = settings.SETUP_HOST
SETUP_PORT = settings.SETUP_PORT
WEB_PORT = settings.WEB_PORT


def local_ipv4s() -> list[str]:
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        ips = []
    return [i for i in ips if not i.startswith(("127.", "169.254."))]


def setup_command(cmd: str, expect: str, host: str, timeout: float = 6.0) -> str:
    with socket.create_connection((host, SETUP_PORT), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall((cmd + "\r\n").encode())
        buf = b""
        deadline = time.monotonic() + timeout
        while b"\n" not in buf and time.monotonic() < deadline:
            try:
                chunk = s.recv(1024)
            except socket.timeout:
                break
            if not chunk:
                break
            buf += chunk
    text = buf.decode("utf-8", "replace").strip()
    if expect and expect not in text:
        raise SystemExit(f"strip answered {text!r}, expected {expect!r} (command {cmd!r})")
    return text


def cmd_provision(args) -> int:
    for value in (args.ssid, args.password):
        if any(c in value for c in ":\r\n"):
            raise SystemExit("the strip's command protocol cannot use ':' or newlines in the SSID/password")

    if not args.ip:
        print("Need the IP this PC/Server will have on your home Wi-Fi (the strip connects to it).")
        cands = local_ipv4s()
        print("Candidates found right now:", ", ".join(cands) or "none")
        print("Run `python powerk.py` on the home Wi-Fi first; it prints the exact IP. Then:")
        print('  python powerk.py provision --ip 192.168.0.50 --ssid "YOURWIFI" --password "..."')
        return 2

    try:
        args.ip = str(ipaddress.IPv4Address(args.ip))
    except ValueError:
        raise SystemExit(f"--ip must be an IPv4 address (got {args.ip!r})")

    print(f"Looking for the strip's setup service at {args.host}:{SETUP_PORT} ...")
    deadline = time.monotonic() + args.wait
    while True:
        try:
            with socket.create_connection((args.host, SETUP_PORT), timeout=2):
                break
        except OSError:
            if time.monotonic() > deadline:
                print("Not reachable. Do this first:")
                print("  1. hold the strip's main button ~10s until the LED blinks fast")
                print("  2. join the Wi-Fi network 'TONLY_TAP_XXXXXXX' from this PC")
                print("     (password: LGU_XXXXXXX - the same 7 characters as in the name)")
                print("  3. re-run this command")
                return 1
            time.sleep(2)

    print(f"  {setup_command(f'up:ip:{args.ip}', 'up:ip:ip_ok', args.host)}")
    print(f"  {setup_command(f'up:connect:{args.ssid}:{args.password}', 'up:connect:connect_ok', args.host)}")
    print(f"\nDone. Reconnect this PC to your home Wi-Fi and start `python powerk.py`.")
    print(f"The strip will connect to {args.ip}:{DEVICE_PORT} shortly.")
    return 0


async def _selftest() -> None:
    from app.device_server.hub import hub
    from app.device_server.protocol import parse_getinfo
    from app.database import init_db, AsyncSessionLocal
    from app.services.device_service import DeviceService
    from app.services.scheduler_service import SchedulerService
    from app.services.energy_service import EnergyService

    print("Running Powerk 2.0 backend self-tests...")
    await init_db()

    # 1. Test getinfo protocol parsing
    sample_getinfo = (
        "1:100;on;1;0;0;12500;0000000A;00000000;00000000;0;00;31:"
        "2:200;off;0;0;0;0;00000005;00000000;00000000;0;00;32:"
        "3:300;on;1;0;0;45000;0000000C;00000000;00000000;0;00;33:"
        "4:400;off;0;0;0;0;00000002;00000000;00000000;0;00;34:"
        "5:1000;on;1;0;0;57500;00000023;00000000;00000000;0;00;34"
    )
    records = parse_getinfo(sample_getinfo)
    assert len(records) == 4, f"Expected 4 outlets, got {len(records)}"
    assert records[0]["on"] is True and records[0]["power_w"] == 12.5 and records[0]["temp_c"] == 31
    assert records[1]["on"] is False and records[1]["power_w"] == 0.0
    print("  [OK] Protocol parser validation OK")

    # 2. Test mock device connection and DB sync
    test_mac = "TEST00112233"
    await DeviceService.on_device_connected(test_mac, "192.168.1.99", "LGUTAP", "1.0.66")
    async with AsyncSessionLocal() as db:
        dev = await DeviceService.get_device(db, test_mac)
        assert dev is not None and dev.online is True
        assert len(dev.outlets) == 4
        # Test renaming outlet
        await DeviceService.rename_outlet(db, test_mac, 1, "راوتر الصالة")
        dev = await DeviceService.get_device(db, test_mac)
        assert dev.outlets[0].name == "راوتر الصالة"
    print("  [OK] Database models & outlet renaming OK")

    # 3. Test scheduler creation
    sched = await SchedulerService.create_countdown(test_mac, 1, "off", 300)
    assert sched.is_active is True and sched.outlet_channel == 1
    print("  [OK] Scheduler countdown engine OK")

    # 4. Test energy calculation
    summary = await EnergyService.get_device_summary(test_mac)
    assert "total_kwh" in summary and "today_cost_egp" in summary
    print("  [OK] Energy analytics & cost calculation OK")

    print("\nAll self-tests passed successfully! Backend is ready for production.")


def cmd_serve(args) -> int:
    import uvicorn

    if args.port:
        os.environ["DEVICE_PORT"] = str(args.port)
        settings.DEVICE_PORT = args.port
    if args.web_port:
        os.environ["WEB_PORT"] = str(args.web_port)
        settings.WEB_PORT = args.web_port
    if args.ip:
        os.environ["LOCAL_IP"] = args.ip
        settings.LOCAL_IP = args.ip
    if args.token:
        os.environ["API_TOKEN"] = args.token
        settings.API_TOKEN = args.token

    local_ip = settings.effective_local_ip
    bot_status = "ENABLED (@Na7laPoweratBot)" if (settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN) else "DISABLED"

    print("=" * 60)
    print("  🐝⚡ NA7LA POWERAT 2.0 - SMART STRIP BACKEND & BOT")
    print("=" * 60)
    print(f"  Web Dashboard:    http://{local_ip}:{settings.WEB_PORT}")
    print(f"  API Docs (Swagger): http://{local_ip}:{settings.WEB_PORT}/docs")
    print(f"  Device Server:    TCP {settings.DEVICE_PORT} (listening for MTTL-W01)")
    print(f"  Telegram Bot:     {bot_status}")
    print(f"  Auth Token:       {'Token Required' if settings.API_TOKEN else 'None (Open on Local Network)'}")
    print(f"  Database:         {settings.DATABASE_URL}")
    print("-" * 60)
    print(f"  To provision a new strip:")
    print(f"    python powerk.py provision --ip {local_ip} --ssid <YOUR_WIFI> --password <PASS>")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.WEB_PORT,
        log_level="info",
        reload=False
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    s = sub.add_parser("serve", help="Run device server + web UI + Telegram Bot (default)")
    s.add_argument("--port", type=int, default=DEVICE_PORT, help=f"device TCP port (default {DEVICE_PORT})")
    s.add_argument("--web-port", type=int, default=WEB_PORT, help=f"web server port (default {WEB_PORT})")
    s.add_argument("--ip", help="IP to advertise to devices and web clients (default: auto-detected)")
    s.add_argument("--token", default="", help="security token required for web API")

    p = sub.add_parser("provision", help="Send Wi-Fi + this server IP to a strip in setup mode")
    p.add_argument("--ip", help="IPv4 address of this server on home Wi-Fi")
    p.add_argument("--ssid", required=True, help="Home Wi-Fi SSID (2.4 GHz)")
    p.add_argument("--password", required=True, help="Home Wi-Fi Password")
    p.add_argument("--host", default=SETUP_HOST, help=f"Strip setup SoftAP IP (default {SETUP_HOST})")
    p.add_argument("--wait", type=float, default=20.0, help="seconds to wait for strip setup service")

    sub.add_parser("selftest", help="Run offline validation checks")

    args = ap.parse_args()

    if args.cmd == "provision":
        return cmd_provision(args)
    if args.cmd == "selftest":
        asyncio.run(_selftest())
        return 0
    if args.cmd in (None, "serve"):
        args.port = getattr(args, "port", DEVICE_PORT)
        args.web_port = getattr(args, "web_port", WEB_PORT)
        args.ip = getattr(args, "ip", None)
        args.token = getattr(args, "token", "")
        return cmd_serve(args)

    ap.error("unknown command")


if __name__ == "__main__":
    sys.exit(main())
