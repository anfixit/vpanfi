from functools import lru_cache

from app.services.cabinet import CabinetService


@lru_cache
def get_cabinet_service() -> CabinetService:
    return CabinetService()
