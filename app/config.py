import socket
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

def detect_local_ipv4() -> str:
    try:
        ips = socket.gethostbyname_ex(socket.gethostname())[2]
        cands = [i for i in ips if not i.startswith(("127.", "169.254."))]
        if cands:
            return cands[0]
    except OSError:
        pass
    return "127.0.0.1"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DEVICE_PORT: int = 10086
    SETUP_HOST: str = "192.168.1.1"
    SETUP_PORT: int = 30300
    WEB_PORT: int = 8080
    HOST: str = "0.0.0.0"
    LOCAL_IP: Optional[str] = None

    API_TOKEN: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///powerk.db"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_ENABLED: bool = True

    POLL_INTERVAL: float = 5.0
    DIAGNOSTICS_INTERVAL: float = 15.0
    TELEMETRY_LOG_INTERVAL: float = 60.0
    ELECTRICITY_COST_PER_KWH: float = 1.85

    @property
    def effective_local_ip(self) -> str:
        if self.LOCAL_IP and self.LOCAL_IP.strip():
            return self.LOCAL_IP.strip()
        return detect_local_ipv4()


settings = Settings()
