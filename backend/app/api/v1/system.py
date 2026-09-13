from fastapi import APIRouter

router = APIRouter()


@router.get("/ready")
async def ready():
    return {"status": "ready"}


@router.get("/")
async def root():
    return {"message": "Basarat API"}
