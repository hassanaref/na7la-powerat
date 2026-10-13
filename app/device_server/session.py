import asyncio
import time
from typing import Any, Optional
from app.device_server.protocol import cmd_getinfo_all, cmd_onoff, cmd_diagnostics_vol, cmd_diagnostics_rssi


class LiveOutletState:
    def __init__(self, channel: int):
        self.channel = channel
        self.on = False
        self.power_w = 0.0
        self.energy_kwh = 0.0
        self.temp_c = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "on": self.on,
            "power_w": self.power_w,
            "energy_kwh": self.energy_kwh,
            "temp_c": self.temp_c,
        }


class LiveDeviceState:
    def __init__(self, mac: str, model: str, fw: str, ip: str):
        self.mac = mac.upper()
        self.model = model
        self.fw = fw
        self.ip = ip
        self.online = True
        self.voltage_v: Optional[float] = None
        self.rssi: Optional[int] = None
        self.last_seen = time.time()
        self.outlets: dict[int, LiveOutletState] = {
            i: LiveOutletState(i) for i in range(1, 5)
        }

    @property
    def name(self) -> str:
        return f"MTTL {self.mac[-7:]}"

    @property
    def current_a(self) -> float:
        if not self.voltage_v or self.voltage_v <= 0:
            return 0.0
        total_w = sum(o.power_w for o in self.outlets.values())
        return round(total_w / self.voltage_v, 2)

    def snapshot(self) -> dict[str, Any]:
        outlets_list = [o.to_dict() for o in self.outlets.values()]
        return {
            "mac": self.mac,
            "name": self.name,
            "model": self.model,
            "fw": self.fw,
            "ip": self.ip,
            "online": self.online,
            "on": any(o.on for o in self.outlets.values()),
            "power_w": round(sum(o.power_w for o in self.outlets.values()), 2),
            "energy_kwh": round(sum(o.energy_kwh for o in self.outlets.values()), 3),
            "voltage": self.voltage_v,
            "current_a": self.current_a,
            "rssi": self.rssi,
            "outlets": outlets_list,
            "last_seen": self.last_seen,
        }


class DeviceSession:
    """Manages one TCP connection to an MTTL-W01 device."""

    def __init__(self, ip: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.ip = ip
        self.reader = reader
        self.writer = writer
        self.lock = asyncio.Lock()
        self.device: Optional[LiveDeviceState] = None
        self.got_getinfo = asyncio.Event()
        self.last_cmd = ""
        self.last_rx = ""

    async def send(self, cmd: str) -> None:
        self.last_cmd = cmd
        self.writer.write((cmd + "\r\n").encode("ascii"))
        await self.writer.drain()

    async def refresh(self, timeout: float = 5.0) -> bool:
        async with self.lock:
            self.got_getinfo.clear()
            await self.send(cmd_getinfo_all())
            try:
                await asyncio.wait_for(self.got_getinfo.wait(), timeout)
                if self.device:
                    self.device.last_seen = time.time()
                return True
            except asyncio.TimeoutError:
                return False

    async def set_outlets(self, channels: list[int], on: bool) -> bool:
        async with self.lock:
            for ch in channels:
                await self.send(cmd_onoff(ch, on))
            await asyncio.sleep(0.3)  # Allow relay to settle before querying state
            self.got_getinfo.clear()
            await self.send(cmd_getinfo_all())
            try:
                await asyncio.wait_for(self.got_getinfo.wait(), 4.0)
                if self.device:
                    self.device.last_seen = time.time()
                return True
            except asyncio.TimeoutError:
                return False

    async def diagnostics(self) -> None:
        async with self.lock:
            await self.send(cmd_diagnostics_vol())
            await self.send(cmd_diagnostics_rssi())
