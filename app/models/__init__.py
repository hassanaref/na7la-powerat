from datetime import datetime, timezone
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    devices: Mapped[list["Device"]] = relationship(
        "Device", back_populates="owner", cascade="all, delete-orphan", lazy="selectin"
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

    owner_telegram_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.telegram_id", ondelete="SET NULL"), nullable=True)
    owner: Mapped[User | None] = relationship("User", back_populates="devices", lazy="selectin")

    outlets: Mapped[list["Outlet"]] = relationship(
        "Outlet", back_populates="device", cascade="all, delete-orphan", order_by="Outlet.channel", lazy="selectin"
    )
    schedules: Mapped[list["Schedule"]] = relationship(
        "Schedule", back_populates="device", cascade="all, delete-orphan", lazy="selectin"
    )


class Outlet(Base):
    __tablename__ = "outlets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_mac: Mapped[str] = mapped_column(String(17), ForeignKey("devices.mac", ondelete="CASCADE"), index=True)
    channel: Mapped[int] = mapped_column(Integer)  # 1, 2, 3, 4
    name: Mapped[str] = mapped_column(String(64))  # e.g., "الراوتر", "الكمبيوتر"
    is_on: Mapped[bool] = mapped_column(Boolean, default=False)
    power_w: Mapped[float] = mapped_column(Float, default=0.0)
    energy_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    temp_c: Mapped[int] = mapped_column(Integer, default=0)

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
