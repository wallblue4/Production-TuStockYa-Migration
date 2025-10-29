# app/modules/vendor/router.py
from fastapi import APIRouter, Depends, Query , Body , HTTPException , Path, Form
from sqlalchemy.orm import Session
import json

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from .service import VendorService
from .schemas import VendorDashboardResponse, TransferSummaryResponse, CompletedTransfersResponse , DeliveryNotes

router = APIRouter()

@router.get("/dashboard", response_model=VendorDashboardResponse)
async def get_vendor_dashboard(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Dashboard completo del vendedor con todas las métricas del día
    
    **Incluye (igual que backend antiguo):**
    - Ventas del día (confirmadas y pendientes)
    - Desglose por métodos de pago
    - Gastos del día
    - Ingreso neto calculado
    - Solicitudes de transferencia pendientes
    - Solicitudes de descuento
    - Notificaciones de devolución
    - Acciones rápidas disponibles
    """
    service = VendorService(db, current_company_id)
    
    # Información del usuario
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'email': current_user.email,
        'role': current_user.role,
        'location_id': current_user.location_id
    }
    
    return await service.get_dashboard(current_user.id, user_info)

@router.get("/pending-transfers", response_model=TransferSummaryResponse)
async def get_vendor_pending_transfers(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Transferencias pendientes para el vendedor (recepciones por confirmar)
    
    **Funcionalidad:**
    - Lista de productos entregados esperando confirmación
    - Priorización por urgencia (cliente vs restock)
    - Tiempo transcurrido desde entrega
    - Información del corredor
    """
    service = VendorService(db, current_company_id)
    return await service.get_pending_transfers(current_user.id)

@router.get("/completed-transfers", response_model=CompletedTransfersResponse)
async def get_vendor_completed_transfers(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Transferencias completadas del día (historial)
    
    **Funcionalidad:**
    - Historial de transferencias del día
    - Estadísticas de éxito
    - Duración promedio
    - Performance del vendedor
    """
    service = VendorService(db, current_company_id)
    return await service.get_completed_transfers(current_user.id)

@router.post("/confirm-reception/{request_id}")
async def confirm_reception(
    request_id: int,
    received_quantity: int = Query(..., description="Cantidad recibida"),
    condition_ok: bool = Query(..., description="Condición del producto OK"),
    notes: str = Query("", description="Notas de recepción"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    db: Session = Depends(get_db),
    company_id: int = Depends(get_current_company_id)
):
    """
    VE008: Confirmar recepción de transferencia con actualización automática de inventario
    
    **Funcionalidad:**
    - Confirmar recepción de producto transferido
    - Validar cantidad y condición
    - Actualizar inventario automáticamente
    - Completar el ciclo de transferencia
    """
    # Esta funcionalidad debe delegarse al módulo transfers
    # pero mantenemos el endpoint aquí por compatibilidad con frontend
    from app.shared.database.models import TransferRequest
    from app.modules.transfers_new.service import TransfersService
    
    service = VendorService(db,company_id)
    return await service.confirm_reception(
        request_id, received_quantity, condition_ok, notes, current_user.id
    )

@router.post("/sell-from-transfer/{request_id}")
async def sell_product_from_transfer(
    request_id: int,
    total_amount: float = Form(..., description="Monto total de la venta", gt=0),
    payment_methods: str = Form(..., description="JSON string con métodos de pago"),
    notes: str = Form("", description="Notas adicionales"),
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Registrar venta de producto recibido por transferencia
    
    **Funcionalidad:**
    - Validar que la transferencia esté en estado 'completed'
    - Crear venta automática del producto recibido
    - Actualizar estado de transferencia a 'selled'
    - Descontar inventario automáticamente
    
    **Flujo:**
    1. Vendedor ya confirmó recepción (status='completed')
    2. Vendedor vende el producto al cliente
    3. Sistema registra venta y marca transferencia como 'selled'
    
    **Request Form Data:**
    - total_amount: Monto total de la venta
    - payment_methods: JSON string con métodos de pago
      Ejemplo: [{"type": "efectivo", "amount": 1500.00, "reference": null}]
    - notes: Notas adicionales (opcional)
    """
    service = VendorService(db, company_id)
    
    try:
        # Parsear métodos de pago
        payment_methods_data = json.loads(payment_methods)
        
        return await service.sell_product_from_transfer(
            request_id=request_id,
            total_amount=total_amount,
            payment_methods=payment_methods_data,
            notes=notes,
            seller_id=current_user.id,
            location_id=current_user.location_id,
            company_id=company_id
        )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"payment_methods JSON inválido: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando venta: {str(e)}")

@router.get("/my-pickup-assignments")
async def get_my_pickup_assignments(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    VE009: Ver transferencias que el vendedor debe recoger personalmente
    
    **Caso de uso:**
    - Vendedor solicitó producto con pickup_type = 'vendedor'
    - Bodeguero aceptó y preparó el producto
    - Vendedor debe ir a bodega a recogerlo personalmente
    - No hay corredor involucrado en el transporte
    
    **Funcionalidad:**
    - Lista de productos listos para recoger
    - Ubicación y datos de contacto de la bodega
    - Información del bodeguero responsable
    - Tiempo transcurrido desde que está listo
    - Indicador de urgencia (cliente presente vs restock)
    
    **Estados incluidos:**
    - `accepted`: Producto listo, esperando que vendedor vaya a recoger
    - `in_transit`: Vendedor ya recogió, en camino a su local
    
    **Acciones disponibles:**
    - Ver dirección y teléfono de bodega
    - Contactar al bodeguero
    - Confirmar llegada con el producto
    """
    service = VendorService(db, current_company_id)
    
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name
    }
    
    return await service.get_my_pickup_assignments(current_user.id, user_info)



@router.post("/deliver-return-to-warehouse/{return_id}")
async def deliver_return_to_warehouse(
    request_body: DeliveryNotes,
    return_id: int = Path(..., description="ID del return", gt=0), 
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Confirmar que llevé el producto de devolución a bodega personalmente
    
    **Caso de uso:**
    - Return con pickup_type = 'vendedor'
    - Estado = 'accepted' (bodeguero ya aceptó)
    - YO llevé el producto físicamente a bodega
    - Bodeguero debe confirmar que lo recibió
    
    **Proceso:**
    1. Validar que es MI return con pickup_type = 'vendedor'
    2. Validar estado = 'accepted'
    3. Cambiar estado a 'delivered'
    4. Registrar timestamp de entrega
    5. Esperar confirmación del bodeguero (BG010)
    
    **Validaciones:**
    - Solo el vendedor solicitante puede confirmar
    - Return debe estar en estado 'accepted'
    - pickup_type debe ser 'vendedor'
    - No se puede confirmar dos veces
    
    **Siguiente paso:**
    - Bodeguero hará control de calidad
    - Bodeguero confirmará recepción (BG010)
    - Ahí se restaura el inventario
    
    **Request:**
    ```json
        {
        "delivery_notes": "Entregué el producto en bodega - 15:30 hrs"
        }
        **Response:**
    {
    "success": true,
    "message": "Entrega confirmada - Esperando que bodeguero valide recepción",
    "return_id": 135,
    "status": "delivered",
    "delivered_at": "2025-10-06T15:30:00",
    "next_step": "Bodeguero debe confirmar recepción y restaurar inventario"
    }
    """
    # Inicialización del servicio de negocio
    service = VendorService(db, current_company_id)

    try:
        # Llamada a la lógica del servicio
        result = await service.deliver_return_to_warehouse(
            return_id,
            request_body.delivery_notes,
            current_user.id
        )
        
        # Retorno de la respuesta exitosa
        return {
            "success": True,
            "message": "Entrega confirmada - Esperando que bodeguero valide recepción",
            **result # Desempaqueta los resultados del servicio (e.g., status, delivered_at)
        }
        
    except ValueError as e:
        # Manejo de errores de negocio o validación (código HTTP 400 Bad Request)
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        # Manejo de errores internos del servidor (código HTTP 500 Internal Server Error)
        raise HTTPException(500, detail=str(e))


@router.get("/health")
async def vendor_health():
    """Health check del módulo vendor"""
    return {
        "service": "vendor",
        "status": "healthy",
        "version": "1.1.0",
        "features": [
            "Dashboard completo del vendedor",
            "Métricas en tiempo real",
            "Transferencias pendientes",
            "Asignaciones de pickup personal",
            "Historial del día",
            "Confirmación de recepciones",
            "Venta directa desde transferencias"
        ]
    }