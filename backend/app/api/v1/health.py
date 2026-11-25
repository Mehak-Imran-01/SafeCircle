from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="API v1 Health check")
async def api_v1_health_check():
    return {
        "status": "healthy",
        "api_version": "v1",
        "service": "SafeCircle Backend API",
    }
