from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class OutletResponse(BaseModel):
    channel: int
    name: str
    is_on: bool
    power_w: float
    energy_kwh: float
    temp_c: int


class DeviceResponse(BaseModel):
    mac: str
    name: str
    model: str
    fw: Optional[str] = None
    ip: Optional[str] = None
    online: bool
    voltage_v: Optional[float] = None
    current_a: Optional[float] = None
    rssi: Optional[int] = None
    last_seen: Optional[datetime] = None
    owner_telegram_id: Optional[int] = None
    outlets: List[OutletResponse] = []


class DeviceRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class OutletRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class OutletToggleRequest(BaseModel):
    mac: str
    outlet: int = Field(..., ge=0, le=4, description="0 for all, 1-4 for specific outlet")
    on: bool


class DeviceClaimRequest(BaseModel):
    mac: str
    user_telegram_id: int


class CountdownCreateRequest(BaseModel):
    device_mac: str
    outlet_channel: int = Field(0, ge=0, le=4)
    action: str = Field("off", pattern="^(on|off)$")
    delay_seconds: int = Field(..., gt=0, le=86400 * 7)


class ScheduleResponse(BaseModel):
    id: int
    device_mac: str
    outlet_channel: int
    action: str
    schedule_type: str
    target_time: Optional[datetime] = None
    time_of_day: Optional[str] = None
    days_of_week: Optional[str] = None
    is_active: bool
    created_at: datetime


class EnergySummaryResponse(BaseModel):
    mac: str
    total_kwh: float
    today_kwh: float
    today_cost_egp: float
    total_cost_egp: float
    rate_per_kwh: float
