from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class OutletResponse(BaseModel):
    channel: int
    name: str
    icon: Optional[str] = "outlet"
    is_on: bool
    power_w: float
    energy_kwh: float
    temp_c: int
    auto_off_minutes: Optional[int] = 0
    standby_cutoff_w: Optional[float] = 0.0
    is_surge_priority: Optional[bool] = False


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
    min_voltage: Optional[float] = 190.0
    max_voltage: Optional[float] = 245.0
    max_power_w: Optional[float] = 3200.0
    child_lock_enabled: Optional[bool] = False
    away_mode_enabled: Optional[bool] = False
    surge_router_channel: Optional[int] = 1
    outlets: List[OutletResponse] = []


class DeviceRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class OutletRenameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class OutletSmartUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    icon: Optional[str] = Field(None, max_length=32)
    auto_off_minutes: Optional[int] = Field(None, ge=0, le=1440)
    standby_cutoff_w: Optional[float] = Field(None, ge=0.0, le=3500.0)
    standby_cutoff_minutes: Optional[int] = Field(None, ge=1, le=1440)
    is_surge_priority: Optional[bool] = None


class OutletToggleRequest(BaseModel):
    mac: str
    outlet: int = Field(..., ge=0, le=4, description="0 for all, 1-4 for specific outlet")
    on: bool


class DeviceClaimRequest(BaseModel):
    mac: str
    user_telegram_id: Optional[int] = None


class ProtectionSettingsResponse(BaseModel):
    mac: str
    min_voltage: float
    max_voltage: float
    max_power_w: float
    child_lock_enabled: bool
    away_mode_enabled: bool
    surge_router_channel: int


class ProtectionSettingsUpdate(BaseModel):
    min_voltage: Optional[float] = Field(None, ge=150.0, le=260.0)
    max_voltage: Optional[float] = Field(None, ge=200.0, le=280.0)
    max_power_w: Optional[float] = Field(None, ge=100.0, le=3800.0)
    child_lock_enabled: Optional[bool] = None
    away_mode_enabled: Optional[bool] = None
    surge_router_channel: Optional[int] = Field(None, ge=1, le=4)


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
