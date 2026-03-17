from fastapi import APIRouter


router = APIRouter()


@router.get("/")
async def root():
    return {"ok": True, "service": "ph-eye-backend"}


@router.get("/health")
async def health():
    return {"ok": True}

