from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from .service import InventoryService
from .schemas import ProductResponse, InventorySearchParams, InventoryByRoleParams, GroupedInventoryResponse, SimpleInventoryResponse

router = APIRouter()

@router.get("/products/search", response_model=List[ProductResponse])
async def search_inventory(
    reference_code: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    location_name: Optional[str] = None,
    size: Optional[str] = None,
    is_active: Optional[int] = None,
    current_user = Depends(require_roles(["seller", "administrador", "bodeguero"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Buscar productos en inventario con múltiples filtros"""
    service = InventoryService(db, current_company_id)
    search_params = InventorySearchParams(
        reference_code=reference_code,
        brand=brand,
        model=model,
        location_name=location_name,
        size=size,
        is_active=is_active
    )
    return await service.search_inventory(search_params)

@router.get("/warehouse-keeper/inventory", response_model=List[ProductResponse])
async def get_warehouse_keeper_inventory(
    reference_code: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    size: Optional[str] = None,
    is_active: Optional[int] = None,
    current_user = Depends(require_roles(["bodeguero"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Obtener inventario para bodeguero - solo bodegas asignadas"""
    service = InventoryService(db, current_company_id)
    search_params = InventoryByRoleParams(
        reference_code=reference_code,
        brand=brand,
        model=model,
        size=size,
        is_active=is_active
    )
    return await service.get_warehouse_keeper_inventory(current_user.id, search_params)

@router.get("/admin/inventory", response_model=List[ProductResponse])
async def get_admin_inventory(
    reference_code: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    size: Optional[str] = None,
    is_active: Optional[int] = None,
    current_user = Depends(require_roles(["administrador"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Obtener inventario para administrador - locales y bodegas asignadas"""
    service = InventoryService(db, current_company_id)
    search_params = InventoryByRoleParams(
        reference_code=reference_code,
        brand=brand,
        model=model,
        size=size,
        is_active=is_active
    )
    return await service.get_admin_inventory(current_user.id, search_params)

@router.get("/warehouse-keeper/inventory/all", response_model=SimpleInventoryResponse)
async def get_all_warehouse_keeper_inventory(
    current_user = Depends(require_roles(["bodeguero"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Obtener TODO el inventario para bodeguero - solo bodegas asignadas con estructura simplificada"""
    service = InventoryService(db, current_company_id)
    return await service.get_simple_warehouse_keeper_inventory(current_user.id)

@router.get("/admin/inventory/all", response_model=SimpleInventoryResponse)
async def get_all_admin_inventory(
    current_user = Depends(require_roles(["administrador"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """Obtener TODO el inventario para administrador - locales y bodegas asignadas con estructura simplificada"""
    service = InventoryService(db, current_company_id)
    return await service.get_simple_admin_inventory(current_user.id)

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
            "Listado completo de inventario con estructura simplificada",
            "Información de tallas expandidas",
            "Inventario por rol (bodeguero/administrador)"
        ]
    }
