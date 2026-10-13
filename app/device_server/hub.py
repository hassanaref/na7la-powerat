import asyncio
import logging
from typing import Callable, Coroutine, Any, Optional
from app.device_server.protocol import (
    BOOTINFO_RE,
    EVENT_RE,
    ONOFF_ACK_RE,
    POWER_REPORT_RE,
    QUERY_RE,
    parse_getinfo,
)
from app.device_server.session import DeviceSession, LiveDeviceState

logger = logging.getLogger("powerk.hub")


class DeviceHub:
    def __init__(self):
        self.sessions: dict[str, DeviceSession] = {}
        self.devices: dict[str, LiveDeviceState] = {}
        self._listeners: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = {
            "device_connected": [],
            "device_disconnected": [],
            "state_updated": [],
            "button_pressed": [],
        }

    def register_listener(self, event: str, callback: Callable[..., Coroutine[Any, Any, None]]):
        if event in self._listeners:
            self._listeners[event].append(callback)

    async def _emit(self, event: str, *args, **kwargs):
        for cb in self._listeners.get(event, []):
            try:
                res = cb(*args, **kwargs)
                if asyncio.iscoroutine(res):
                    asyncio.create_task(res)
            except Exception as e:
                logger.error(f"Error executing listener for {event}: {e}")

    def get_session(self, mac: str) -> Optional[DeviceSession]:
        s = self.sessions.get(mac.upper())
        if s and s.device and s.device.online and not s.writer.is_closing():
            return s
        return None

    def get_device(self, mac: str) -> Optional[LiveDeviceState]:
        return self.devices.get(mac.upper())

    def snapshot(self) -> dict[str, Any]:
        return {"devices": [d.snapshot() for d in self.devices.values()]}

    async def set_outlets(self, mac: str, channels: list[int], on: bool) -> bool:
        session = self.get_session(mac)
        if not session:
            return False
        ok = await session.set_outlets(channels, on)
        if ok and session.device:
            await self._emit("state_updated", mac, session.device.snapshot())
        return ok

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        ip = peer[0] if peer else "unknown"
        session = DeviceSession(ip, reader, writer)
        logger.info(f"Incoming connection from device at {ip}")

        try:
            while True:
                raw = await reader.readline()
                if not raw:
                    break
                if len(raw) > 8192:
                    raise ValueError("Protocol line too long")

                line = raw.replace(b"\x00", b"").decode("utf-8", "replace").strip("\r\n ")
                session.last_rx = line

                # 1. Bootinfo message
                m_boot = BOOTINFO_RE.match(line)
                if m_boot:
                    mac = m_boot.group(2).upper()
                    model = m_boot.group(1)
                    fw = m_boot.group(4)

                    dev = self.devices.get(mac)
                    if not dev:
                        dev = LiveDeviceState(mac, model, fw, ip)
                        self.devices[mac] = dev
                    else:
                        dev.model, dev.fw, dev.ip, dev.online = model, fw, ip, True

                    session.device = dev

                    old_session = self.sessions.get(mac)
                    if old_session and old_session is not session:
                        try:
                            old_session.writer.close()
                        except Exception:
                            pass

                    self.sessions[mac] = session
                    logger.info(f"Device registered: {dev.name} (MAC: {mac}, IP: {ip}, FW: {fw})")
                    await self._emit("device_connected", mac, ip, model, fw)
                    from app.services.protection_service import ProtectionService
                    asyncio.create_task(ProtectionService.handle_cold_boot_surge_delay(mac))
                    asyncio.create_task(session.refresh())
                    continue

                if not session.device:
                    continue

                # 2. GetInfo message (relay state, power, energy, temp)
                if line.startswith("up:getinfo:"):
                    records = parse_getinfo(line)
                    if len(records) == 4:
                        for r in records:
                            ch = r["channel"]
                            outlet = session.device.outlets[ch]
                            outlet.on = r["on"]
                            outlet.power_w = r["power_w"]
                            outlet.energy_kwh = r["energy_kwh"]
                            outlet.temp_c = r["temp_c"]

                        session.got_getinfo.set()
                        await self._emit("state_updated", session.device.mac, session.device.snapshot())
                        from app.services.protection_service import ProtectionService
                        total_w = sum(r["power_w"] for r in records)
                        asyncio.create_task(ProtectionService.check_overload_guard(session.device.mac, total_w))
                    continue

                # 3. Power report (voltage in mV >= 50000)
                if line.lower().startswith("up:power_report:"):
                    m_pow = POWER_REPORT_RE.fullmatch(line)
                    if m_pow:
                        val = int(m_pow.group(2))
                        if val >= 50000:
                            session.device.voltage_v = round(val / 1000.0, 1)
                            from app.services.protection_service import ProtectionService
                            asyncio.create_task(ProtectionService.check_voltage_guard(session.device.mac, session.device.voltage_v))
                    continue

                # 4. Wi-Fi RSSI query response
                m_query = QUERY_RE.fullmatch(line)
                if m_query:
                    session.device.rssi = int(m_query.group(1))
                    continue

                # 5. Hardware physical button event
                m_event = EVENT_RE.fullmatch(line)
                if m_event:
                    ch = int(m_event.group(1))
                    on = m_event.group(2).lower() == "on"
                    if ch in (1, 2, 3, 4):
                        session.device.outlets[ch].on = on
                    elif ch == 0:
                        for o in session.device.outlets.values():
                            o.on = on
                    logger.info(f"Hardware button pressed on {session.device.mac}: outlet {ch} -> {on}")
                    await self._emit("button_pressed", session.device.mac, ch, on)
                    await self._emit("state_updated", session.device.mac, session.device.snapshot())
                    from app.services.protection_service import ProtectionService
                    asyncio.create_task(ProtectionService.handle_button_event_child_lock(session.device.mac, ch, on))
                    continue

                if ONOFF_ACK_RE.fullmatch(line):
                    continue

        except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
            pass
        except Exception as e:
            logger.warning(f"Session error for {ip}: {e} (last_cmd={session.last_cmd!r}, last_rx={session.last_rx!r})")
        finally:
            if session.device:
                mac = session.device.mac
                if self.sessions.get(mac) is session:
                    self.sessions.pop(mac, None)
                    session.device.online = False
                    logger.warning(f"Device disconnected: {session.device.name} (MAC: {mac})")
                    await self._emit("device_disconnected", mac)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass


hub = DeviceHub()
