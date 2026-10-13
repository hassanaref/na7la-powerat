from fastapi import APIRouter
from app.schemas import EnergySummaryResponse
from app.services.energy_service import EnergyService

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("/{mac}", response_model=EnergySummaryResponse)
async def get_energy_summary(mac: str):
    res = await EnergyService.get_device_summary(mac)
    return res
