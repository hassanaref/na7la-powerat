import asyncio
import logging
from app.config import settings
from app.device_server.hub import hub

logger = logging.getLogger("powerk.server")


async def poll_devices_task():
    """Background task to query active devices periodically."""
    cycle = 0
    diag_every = max(1, int(settings.DIAGNOSTICS_INTERVAL / settings.POLL_INTERVAL))
    while True:
        try:
            await asyncio.sleep(settings.POLL_INTERVAL)
            cycle += 1
            for session in list(hub.sessions.values()):
                if not session.device:
                    continue
                try:
                    refreshed = await session.refresh()
                    if not refreshed:
                        logger.debug(f"{session.device.name} poll timeout")
                    elif cycle % diag_every == 0:
                        await session.diagnostics()
                except Exception as err:
                    logger.debug(f"Device poll error for {session.device.name}: {err}")
        except asyncio.CancelledError:
            break
        except Exception as err:
            logger.error(f"Unexpected error in poll loop: {err}")


async def run_tcp_server():
    server = await asyncio.start_server(hub.handle_client, settings.HOST, settings.DEVICE_PORT)
    logger.info(f"TCP Device Server listening on {settings.HOST}:{settings.DEVICE_PORT}")
    return server
