from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config.database import get_db
from app.core.auth.dependencies import require_roles
from .service import InventoryService
from .schemas import ProductResponse, InventorySearchParams

router = APIRouter()

@router.get("/products/search", response_model=List[ProductResponse])
async def search_inventory(
    reference_code: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    location_name: Optional[str] = None,
    size: Optional[str] = None,
    is_active: Optional[int] = None,
    current_user = Depends(require_roles(["seller", "admin", "warehouse"])),
    db: Session = Depends(get_db)
):
    """Buscar productos en inventario con múltiples filtros"""
    service = InventoryService(db)
    search_params = InventorySearchParams(
        reference_code=reference_code,
        brand=brand,
        model=model,
        location_name=location_name,
        size=size,
        is_active=is_active
    )
    return await service.search_inventory(search_params)

@router.get("/health")
async def inventory_health():
    """Health check del módulo de inventario"""
    return {
        "service": "inventory",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "Consulta de inventario",
            "Búsqueda por filtros",
            "Información de tallas"
        ]
    }
