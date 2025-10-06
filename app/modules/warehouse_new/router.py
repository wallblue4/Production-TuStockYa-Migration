
# app/modules/warehouse_new/router.py
from fastapi import APIRouter, Depends, Path , HTTPException, Body
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.auth.dependencies import require_roles
from .service import WarehouseService
from .schemas import (
    WarehouseRequestAcceptance, CourierDelivery, 
    PendingRequestsResponse, AcceptedRequestsResponse, InventoryByLocationResponse ,VendorDelivery ,
)
from app.modules.transfers_new.schemas import (
    ReturnReceptionConfirmation, ReturnReceptionResponse
)

router = APIRouter()

@router.get("/pending-requests", response_model=PendingRequestsResponse)
async def get_pending_requests(
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    BG001: Recibir y procesar solicitudes de productos
    
    **Funcionalidad:**
    - Lista unificada de transferencias y devoluciones pendientes
    - Priorización automática (cliente > restock)
    - Información completa del producto y stock disponible
    - Tiempo transcurrido desde solicitud
    - Vista por ubicaciones asignadas al bodeguero
    
    **Información incluida:**
    - Detalles del producto (imagen, precio, stock)
    - Información del solicitante
    - Ubicaciones origen y destino
    - Nivel de urgencia y prioridad
    """
    service = WarehouseService(db)
    
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name
    }
    
    return await service.get_pending_requests(current_user.id, user_info)

@router.post("/accept-request")
async def accept_request(
    acceptance: WarehouseRequestAcceptance,
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    BG002: Confirmar disponibilidad y preparar productos
    
    **Funcionalidad:**
    - Aceptar o rechazar solicitud después de verificar stock
    - Establecer tiempo estimado de preparación
    - Una vez aceptada, queda disponible para corredores
    - Actualizar estado y asignar bodeguero responsable
    
    **Validaciones:**
    - Solo bodegueros asignados a la ubicación pueden aceptar
    - Verificación de disponibilidad de stock
    - Solicitud debe estar en estado 'pending'
    """
    service = WarehouseService(db)
    return await service.accept_request(acceptance, current_user.id)

@router.get("/accepted-requests", response_model=AcceptedRequestsResponse)
async def get_accepted_requests(
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    Ver solicitudes aceptadas y en preparación
    
    **Funcionalidad:**
    - Solicitudes aceptadas por este bodeguero
    - Estados: accepted, courier_assigned, in_transit
    - Información de corredor asignado cuando disponible
    - Productos listos para entrega
    """
    service = WarehouseService(db)
    
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name
    }
    
    return await service.get_accepted_requests(current_user.id, user_info)

@router.post("/deliver-to-courier")
async def deliver_to_courier(
    delivery: CourierDelivery,
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    BG003: Entregar productos a corredor
    
    **Funcionalidad CRÍTICA:**
    - Entregar producto físicamente al corredor
    - **Descuento automático de inventario** (requerimiento BG003)
    - Cambiar estado a 'in_transit'
    - Registrar timestamp de entrega
    - Actualizar historial de movimientos
    
    **Proceso:**
    1. Corredor llega a bodega
    2. Bodeguero entrega producto
    3. Sistema descuenta inventario automáticamente
    4. Producto queda en tránsito hacia destino
    """
    service = WarehouseService(db)
    
    try:
        result = await service.deliver_to_courier(delivery, current_user.id)
        return result
    except ValueError as e:
        # Errores de validación (400 Bad Request)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # Errores del sistema (500 Internal Server Error)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/inventory-by-location/{location_id}", response_model=InventoryByLocationResponse)
async def get_inventory_by_location(
    location_id: int = Path(..., description="ID de la ubicación"),
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    BG006: Consultar inventario disponible por ubicación general
    
    **Funcionalidad:**
    - Inventario completo de una ubicación específica
    - Información detallada de cada producto
    - Stock disponible y en exhibición
    - Precios unitarios y por caja
    - Valor total del inventario
    - Estado de stock por producto
    """
    service = WarehouseService(db)
    return await service.get_inventory_by_location(location_id)

@router.post("/deliver-to-vendor/{transfer_id}")
async def deliver_to_vendor(
    transfer_id: int = Path(..., description="ID de la transferencia", gt=0),
    delivery: VendorDelivery = Body(...),
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    Entregar producto directamente al vendedor (self-pickup)
    
    **Caso de uso:**
    - El vendedor viene personalmente a recoger el producto
    - No se requiere corredor para transporte
    - pickup_type debe ser 'vendedor'
    
    **Funcionalidad CRÍTICA:**
    - Entregar producto físicamente al vendedor
    - **Descuento automático de inventario** (igual que corredor)
    - Cambiar estado a 'in_transit'
    - Registrar timestamp de entrega
    - Actualizar historial de movimientos
    
    **Proceso:**
    1. Vendedor llega a bodega
    2. Bodeguero valida y entrega producto
    3. Sistema descuenta inventario automáticamente
    4. Vendedor debe confirmar llegada a su ubicación
    
    **Validaciones:**
    - Solo transferencias con pickup_type = 'vendedor'
    - Estado debe ser 'accepted'
    - Bodeguero debe gestionar la ubicación origen
    - Stock debe ser suficiente
    
    **Diferencia con deliver-to-courier:**
    - NO requiere corredor intermedio
    - Vendedor actúa como su propio transportista
    - Flujo más corto (sin estado 'courier_assigned')
    """
    service = WarehouseService(db)
    
    try:
        result = await service.deliver_to_vendor(transfer_id, delivery, current_user.id)
        return result
    except ValueError as e:
        # Errores de validación (400 Bad Request)
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        # Errores del sistema (500 Internal Server Error)
        raise HTTPException(status_code=500, detail=str(e))



# app/modules/warehouse_new/router.py

@router.post("/confirm-return-reception/{return_id}", response_model=ReturnReceptionResponse)
async def confirm_return_reception(
    return_id: int = Path(..., description="ID de la devolución", gt=0),
    reception: ReturnReceptionConfirmation = Body(...),
    current_user = Depends(require_roles(["bodeguero", "administrador", "boss"])),
    db: Session = Depends(get_db)
):
    """
    BG010: Confirmar recepción de devolución con RESTAURACIÓN de inventario
    
    **Caso de uso:**
    - Corredor entregó producto devuelto en bodega
    - Bodeguero inspecciona producto
    - Verifica condición y calidad
    - Decide si regresa a inventario vendible
    
    **Proceso CRÍTICO:**
    1. Validar que es una devolución (return)
    2. Verificar condición del producto:
       - `good`: Regresa a inventario normal → SUMA cantidad
       - `damaged`: Marca para reparación → SUMA con nota de daño
       - `unusable`: Descarta → NO suma a inventario
    3. RESTAURAR inventario en bodega (reversión del descuento original)
    4. Marcar return como completado
    5. Registrar en historial de movimientos
    
    **Diferencia CLAVE con transferencia normal:**
    - Transfer normal: VE008 confirma recepción → SUMA en destino
    - Return: BG010 confirma recepción → RESTAURA (SUMA) en bodega origen
    
    **Control de calidad:**
    - `quality_check_passed=True`: Producto apto para venta
    - `quality_check_passed=False`: Requiere revisión adicional
    
    **Validaciones:**
    - Solo bodegueros de la ubicación destino (bodega origen original)
    - Return debe estar en estado 'delivered'
    - Cantidad no puede exceder lo devuelto
    - Solo se puede confirmar una vez
    
    **Inventario según condición:**
    good + quality_check_passed=True → Inventario normal
    damaged + quality_check_passed=True → Inventario con nota de daño
    unusable → NO regresa a inventario (pérdida registrada)
    """
    service = WarehouseService(db)
    
    try:
        # ✅ CORRECCIÓN: service.confirm_return_reception() YA retorna el dict completo
        result = await service.confirm_return_reception(return_id, reception, current_user.id)
        
        # ✅ El result del service YA tiene "success": True
        # Solo necesitas construir la respuesta con los campos del schema
        return ReturnReceptionResponse(
            success=result["success"],  # ← Ya viene en result
            message=result["message"],
            return_id=result["return_id"],
            original_transfer_id=result["original_transfer_id"],
            received_quantity=result["received_quantity"],
            product_condition=result["product_condition"],
            inventory_restored=result["inventory_restored"],
            warehouse_location=result["warehouse_location"],
            inventory_change=result["inventory_change"]
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def warehouse_health():
    """Health check del módulo warehouse"""
    return {
        "service": "warehouse",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "BG001 - Procesamiento de solicitudes",
            "BG002 - Confirmación y preparación",
            "BG003 - Entrega con descuento automático",
            "BG006 - Consulta de inventario por ubicación",
            "Sistema de prioridades",
            "Vista unificada transferencias/devoluciones"
        ]
    }