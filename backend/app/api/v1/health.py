from fastapi import APIRouter, Depends

from app.services.health_service import HealthService

router = APIRouter()


@router.get("/health")
async def health_check(
    health_service: HealthService = Depends(HealthService),
):
    return await health_service.check_health()