from fastapi import APIRouter, Depends, Response, status

from app.services.health_service import HealthService

router = APIRouter()


@router.get("/ready", deprecated=True, include_in_schema=False)
async def ready(response: Response, health_service: HealthService = Depends(HealthService)):
    """Deprecated compatibility route; use `/health/ready`."""
    result = await health_service.check_health()
    if result["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@router.get("/", include_in_schema=False)
async def root():
    return {"message": "Basarat API"}
