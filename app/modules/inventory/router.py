from fastapi import APIRouter, Depends ,Query, Path
from sqlalchemy.orm import Session
from typing import List, Optional ,Literal

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from .service import InventoryService
from .schemas import ProductResponse, InventorySearchParams, InventoryByRoleParams, GroupedInventoryResponse, SimpleInventoryResponse, GlobalDistributionResponse

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

# app/modules/inventory/router.py (AGREGAR ENDPOINTS)

@router.get("/distribution/{reference_code}/{size}", response_model=GlobalDistributionResponse)
async def get_global_distribution(
    reference_code: str = Path(..., description="Código de referencia del producto"),
    size: str = Path(..., description="Talla"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener distribución global de un producto-talla
    
    **Funcionalidad:**
    - Muestra distribución completa por ubicaciones
    - Incluye pares completos y pies individuales
    - Calcula pares formables
    - Identifica oportunidades de formación
    - Métricas de eficiencia de inventario
    
    **Casos de uso:**
    - Vendedor quiere ver dónde hay stock disponible
    - Admin revisa distribución del inventario
    - Planificar redistribución
    - Identificar oportunidades de formación
    
    **Respuesta incluye:**
    - Totales globales (pares, izquierdos, derechos)
    - Distribución por ubicación
    - Oportunidades de formar pares
    - Porcentaje de eficiencia
    
    **Ejemplo de respuesta:**
```json
    {
      "totals": {
        "pairs": 15,
        "left_feet": 8,
        "right_feet": 8,
        "formable_pairs": 8,
        "total_potential_pairs": 23,
        "efficiency_percentage": 65.2
      },
      "by_location": [...],
      "formation_opportunities": [...]
    }
```
    """
    
    service = InventoryService(db, current_company_id)
    repository = InventoryRepository(db)
    
    # Obtener producto
    product = repository.get_product_by_reference(reference_code, current_company_id)
    
    if not product:
        raise HTTPException(404, f"Producto con referencia {reference_code} no encontrado")
    
    # Obtener distribución
    distribution = repository.get_global_distribution(
        product_id=product.id,
        size=size,
        company_id=current_company_id,
        current_location_id=current_user.location_id if hasattr(current_user, 'location_id') else None
    )
    
    # Obtener oportunidades
    opportunities = repository.find_formation_opportunities(
        product_id=product.id,
        size=size,
        company_id=current_company_id
    )
    
    # Formatear oportunidades
    formatted_opportunities = service._format_opportunities(opportunities)
    
    return GlobalDistributionResponse(
        product_id=product.id,
        reference_code=product.reference_code,
        brand=product.brand,
        model=product.model,
        size=size,
        totals=distribution['totals'],
        by_location=[
            LocationInventoryDetail(**loc)
            for loc in distribution['by_location']
        ],
        formation_opportunities=[
            FormationOpportunity(**opp)
            for opp in formatted_opportunities
        ]
    )


@router.get("/availability/{reference_code}/{size}", response_model=dict)
async def get_detailed_availability(
    reference_code: str = Path(..., description="Código de referencia del producto"),
    size: str = Path(..., description="Talla"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener disponibilidad detallada de un producto en ubicación actual
    
    **Funcionalidad:**
    - Disponibilidad en ubicación del usuario
    - Información de pies separados
    - Análisis de qué falta para vender
    - Sugerencias de acción
    
    **Casos de uso:**
    - Vendedor consulta antes de prometer venta
    - Verificar si se puede formar par localmente
    - Decidir si solicitar transferencia
    
    **Respuesta incluye:**
    - Pares completos disponibles
    - Pies individuales (izq/der)
    - Si se puede vender ahora
    - Qué falta para completar
    - Sugerencias accionables
    """
    
    service = InventoryService(db, current_company_id)
    
    if not hasattr(current_user, 'location_id') or not current_user.location_id:
        raise HTTPException(400, "Usuario debe tener una ubicación asignada")
    
    result = await service.get_enhanced_availability(
        reference_code=reference_code,
        size=size,
        user_location_id=current_user.location_id,
        user_id=current_user.id
    )
    
    return result


@router.get("/formation-opportunities/{reference_code}/{size}")
async def get_formation_opportunities(
    reference_code: str = Path(..., description="Código de referencia del producto"),
    size: str = Path(..., description="Talla"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Listar oportunidades de formación de pares
    
    **Funcionalidad:**
    - Identificar todas las combinaciones posibles
    - Ordenar por optimización (cantidad, distancia)
    - Calcular tiempos estimados
    - Priorizar sugerencias
    
    **Casos de uso:**
    - Admin planifica redistribución
    - Vendedor evalúa opciones
    - Optimizar inventario
    
    **Respuesta incluye:**
    - Pares formables por combinación
    - Ubicaciones involucradas
    - Destino óptimo
    - Tiempo estimado
    - Prioridad
    """
    
    repository = InventoryRepository(db)
    service = InventoryService(db, current_company_id)
    
    # Obtener producto
    product = repository.get_product_by_reference(reference_code, current_company_id)
    
    if not product:
        raise HTTPException(404, f"Producto no encontrado")
    
    # Obtener oportunidades
    opportunities = repository.find_formation_opportunities(
        product_id=product.id,
        size=size,
        company_id=current_company_id
    )
    
    # Formatear
    formatted = service._format_opportunities(opportunities)
    
    return {
        "success": True,
        "product": {
            "product_id": product.id,
            "reference_code": product.reference_code,
            "brand": product.brand,
            "model": product.model,
            "size": size
        },
        "opportunities": formatted,
        "total_opportunities": len(formatted),
        "total_formable_pairs": sum(opp['formable_pairs'] for opp in formatted)
    }


@router.get("/find-opposite-foot/{reference_code}/{size}/{foot_side}")
async def find_opposite_foot(
    reference_code: str = Path(..., description="Código de referencia"),
    size: str = Path(..., description="Talla"),
    foot_side: Literal['left', 'right'] = Path(..., description="Lado del pie que se busca"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Buscar el pie opuesto más cercano
    
    **Funcionalidad:**
    - Encuentra ubicaciones con el pie opuesto
    - Ordena por distancia (cuando esté disponible)
    - Prioriza bodegas sobre locales
    - Calcula tiempos de transferencia
    
    **Casos de uso:**
    - Vendedor tiene izquierdo, busca derecho
    - Planificar transferencia específica
    - Formar par con menor tiempo
    
    **Query params:**
    - foot_side: 'left' o 'right' (el pie que buscas)
    
    **Respuesta incluye:**
    - Lista de ubicaciones con el pie buscado
    - Cantidades disponibles
    - Tipo de ubicación
    - Distancia estimada
    """
    
    repository = InventoryRepository(db)
    
    if not hasattr(current_user, 'location_id') or not current_user.location_id:
        raise HTTPException(400, "Usuario debe tener ubicación asignada")
    
    # Obtener producto
    product = repository.get_product_by_reference(reference_code, current_company_id)
    
    if not product:
        raise HTTPException(404, "Producto no encontrado")
    
    # Buscar pie opuesto
    locations = repository.find_opposite_foot(
        product_id=product.id,
        size=size,
        foot_side=foot_side,
        current_location_id=current_user.location_id,
        company_id=current_company_id
    )
    
    return {
        "success": True,
        "searching_for": foot_side,
        "opposite_found": len(locations) > 0,
        "locations": locations,
        "total_quantity": sum(loc['quantity'] for loc in locations),
        "nearest_location": locations[0] if locations else None
    }

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
