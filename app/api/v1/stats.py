from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas import EnergySummaryResponse
from app.services.energy_service import EnergyService
from app.services.auth_service import AuthService, get_current_user

router = APIRouter(prefix="/stats", tags=["Stats"])


@router.get("/{mac}", response_model=EnergySummaryResponse)
async def get_energy_summary(
    mac: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    await AuthService.verify_device_access(db, current_user, mac)
    res = await EnergyService.get_device_summary(mac)
    return res
