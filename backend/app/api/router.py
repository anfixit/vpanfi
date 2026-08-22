from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.cabinet import router as cabinet_router
from app.api.routes.payments import router as payments_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(cabinet_router)
api_router.include_router(payments_router)
api_router.include_router(admin_router)
