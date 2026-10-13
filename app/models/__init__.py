import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_token():
    return uuid.uuid4().hex + uuid.uuid4().hex[:16]


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    user_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=generate_token)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    pin_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        "Scene", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )


class Device(Base):
    __tablename__ = "devices"

    mac: Mapped[str] = mapped_column(String(17), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), default="مشترك الكهرباء")
    model: Mapped[str] = mapped_column(String(64), default="MTTL-W01")
    fw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    online: Mapped[bool] = mapped_column(Boolean, default=False)
    voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Multi-tenancy & Protection Settings
    owner_telegram_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True, index=True)
    owner: Mapped[User | None] = relationship("User", back_populates="devices", lazy="selectin")

    min_voltage: Mapped[float] = mapped_column(Float, default=190.0)
    max_voltage: Mapped[float] = mapped_column(Float, default=245.0)
    max_power_w: Mapped[float] = mapped_column(Float, default=3200.0)
    child_lock_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    away_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    surge_router_channel: Mapped[int] = mapped_column(Integer, default=1)  # Router socket gets immediate ON on boot

    outlets: Mapped[list["Outlet"]] = relationship(
        "Outlet", back_populates="device", cascade="all, delete-orphan", order_by="Outlet.channel", lazy="selectin"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )
    scenes: Mapped[list["Scene"]] = relationship(
        "Scene", back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )
    shares: Mapped[list["DeviceShare"]] = relationship(
        "DeviceShare", back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    channel: Mapped[int] = mapped_column(Integer)  # 1, 2, 3, 4
    name: Mapped[str] = mapped_column(String(64))  # e.g., "الراوتر", "الكمبيوتر"
    icon: Mapped[str] = mapped_column(String(32), default="outlet")  # router, pc, tv, charger, lamp, fan, etc.
    is_on: Mapped[bool] = mapped_column(Boolean, default=False)
    power_w: Mapped[float] = mapped_column(Float, default=0.0)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    temp_c: Mapped[int] = mapped_column(Integer, default=0)

    # Outlet Smart Protection
    auto_off_minutes: Mapped[int] = mapped_column(Integer, default=0)  # Auto turn-off after X mins of turning ON
    standby_cutoff_w: Mapped[float] = mapped_column(Float, default=0.0)  # Power cutoff if idle below this wattage
    standby_cutoff_minutes: Mapped[int] = mapped_column(Integer, default=15)
    is_surge_priority: Mapped[bool] = mapped_column(Boolean, default=False)
    last_turned_on: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    device: Mapped[Device] = relationship("Device", back_populates="outlets")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    outlet_channel: Mapped[int] = mapped_column(Integer, default=0)  # 0 = All outlets, 1-4 = specific
    action: Mapped[str] = mapped_column(String(16))  # "on" or "off"
    schedule_type: Mapped[str] = mapped_column(String(32))  # "countdown" or "recurring"
    target_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(8), nullable=True)  # "HH:MM" for recurring
    days_of_week: Mapped[str | None] = mapped_column(String(32), default="0,1,2,3,4,5,6")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    device: Mapped[Device] = relationship("Device", back_populates="schedules")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"), index=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(64))  # e.g. "Work Mode", "Bedtime", "Gaming"
    icon: Mapped[str] = mapped_column(String(32), default="play")
    actions_json: Mapped[str] = mapped_column(Text, default="{}")  # '{"1": true, "2": false, "3": false, "4": true}'
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship("User", back_populates="scenes")
    device: Mapped[Device] = relationship("Device", back_populates="scenes")


class DeviceShare(Base):
    __tablename__ = "device_shares"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="CASCADE"))
    shared_telegram_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    shared_email: Mapped[str | None] = mapped_column(String(128), nullable=True)
    share_code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    can_control: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    device: Mapped[Device] = relationship("Device", back_populates="shares")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    outlet_channel: Mapped[int] = mapped_column(Integer, default=0)  # 0 is aggregate
    power_w: Mapped[float] = mapped_column(Float, default=0.0)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    voltage_v: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_a: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_c: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
