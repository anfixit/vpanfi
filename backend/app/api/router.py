from fastapi import APIRouter

from app.api.routes.cabinet import router as cabinet_router

api_router = APIRouter()
api_router.include_router(cabinet_router)
