from fastapi import APIRouter, Depends, Response, status

from app.services.health_service import HealthService

router = APIRouter()


@router.get("/health")
async def health_check():
    """Liveness probe: process is able to answer HTTP."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness_check(
    response: Response,
    health_service: HealthService = Depends(HealthService),
):
    """Readiness probe: dependencies required for serving are available."""
    result = await health_service.check_health()
    if result["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
