import asyncio
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.device_server.server import run_tcp_servers, poll_devices_task
from app.services.scheduler_service import scheduler_loop
from app.services.energy_service import energy_logger_loop
from app.bot.bot import start_bot, stop_bot
from app.static_page import WEB_PAGE_HTML

from app.api.legacy import router as legacy_router, is_authorized, verify_auth
from app.api.v1.devices import router as devices_v1_router
from app.api.v1.outlets import router as outlets_v1_router
from app.api.v1.schedules import router as schedules_v1_router
from app.api.v1.stats import router as stats_v1_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("powerk.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Powerk Backend & Database...")
    await init_db()

    # 1. Start TCP Device Servers (Ports 10086 and 21197)
    tcp_servers = await run_tcp_servers()
    poll_task = asyncio.create_task(poll_devices_task())

    # 2. Start Scheduler & Energy Background Loops
    sched_task = asyncio.create_task(scheduler_loop())
    energy_task = asyncio.create_task(energy_logger_loop())

    # 3. Start Telegram Bot
    if settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN:
        try:
            await start_bot()
            logger.info("Telegram Bot started successfully.")
        except Exception as e:
            logger.error(f"Failed to start Telegram Bot: {e}")

    yield

    logger.info("Shutting down Powerk services...")
    # Stop Telegram Bot
    await stop_bot()

    # Cancel background tasks
    poll_task.cancel()
    sched_task.cancel()
    energy_task.cancel()

    # Close TCP servers
    for srv in tcp_servers:
        srv.close()
        await srv.wait_closed()
    logger.info("All services stopped.")


app = FastAPI(
    title="Powerk Smart Strip Backend",
    description="Modern Async Python Backend with Telegram Bot control for LG U+ MTTL-W01 Power Strip (Voltra Alternative)",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
@app.get("/index.html", response_class=HTMLResponse)
async def index_page(request: Request):
    if settings.API_TOKEN and not is_authorized(request):
        verify_auth(request)
    return HTMLResponse(content=WEB_PAGE_HTML)


# Include API Routers
app.include_router(legacy_router)
app.include_router(devices_v1_router, prefix="/api/v1")
app.include_router(outlets_v1_router, prefix="/api/v1")
app.include_router(schedules_v1_router, prefix="/api/v1")
app.include_router(stats_v1_router, prefix="/api/v1")
