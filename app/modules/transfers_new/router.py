# app/modules/transfers_new/router.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.core.auth.dependencies import require_roles
from app.core.auth.dependencies import get_current_company_id
from .service import TransfersService
from .schemas import TransferRequestCreate, TransferRequestResponse, MyTransferRequestsResponse , ReturnRequestCreate, ReturnRequestResponse

router = APIRouter()

@router.post("/request", response_model=TransferRequestResponse)
async def create_transfer_request(
    transfer_data: TransferRequestCreate,
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    VE003: Solicitar productos de otras ubicaciones
    
    **Funcionalidad:**
    - Crear solicitud especificando producto, cantidad y urgencia
    - Validar disponibilidad antes de crear solicitud
    - Establecer prioridad según propósito (cliente vs restock)
    - Sistema de reservas automático para clientes presentes
    
    **Casos de uso:**
    - Cliente esperando producto que no está en local
    - Solicitar productos para restock de exhibición
    - Transferencia entre bodegas
    """
    service = TransfersService(db)
    return await service.create_transfer_request(transfer_data, current_user.id, company_id)

@router.get("/my-requests", response_model=MyTransferRequestsResponse)
async def get_my_transfer_requests(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener mis solicitudes de transferencia
    
    **Vista unificada:**
    - Transferencias y devoluciones en una sola lista
    - Estado detallado con progreso
    - Información completa de participantes
    - Tiempo transcurrido y próximos pasos
    """
    service = TransfersService(db)
    
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name
    }
    
    return await service.get_my_transfer_requests(current_user.id, user_info, company_id)


@router.post("/create-return", response_model=ReturnRequestResponse)
async def create_return_request(
    return_data: ReturnRequestCreate,
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    VE006: Crear solicitud de devolución de producto
    
    **Caso de uso:**
    - Producto transferido que NO se vendió
    - Cliente rechazó el producto
    - Producto con defecto detectado
    - Sobrecupo en exhibición
    
    **Proceso:**
    1. Valida transferencia original existe y completada
    2. Crea nueva transferencia con ruta INVERTIDA (local → bodega)
    3. Marca como tipo 'return'
    4. Sigue el MISMO FLUJO que transferencia normal:
       - BG001-BG002: Bodeguero acepta
       - CO001-CO004: Corredor transporta
       - BG010: Bodeguero confirma recepción
    5. Al finalizar: RESTAURA inventario en bodega
    
    **Validaciones:**
    - Solo el solicitante original puede devolver
    - Transfer debe estar completado
    - Cantidad no puede exceder lo recibido
    - No se puede devolver dos veces
    
    **Diferencia con transfer normal:**
    - Origen y destino están INVERTIDOS
    - Prioridad siempre 'normal' (no urgente)
    - Al confirmar recepción: SUMA inventario (no resta)
    """
    service = TransfersService(db)
    return await service.create_return_request(return_data, current_user.id, company_id)

@router.get("/my-returns")
async def get_my_returns(
    current_user = Depends(require_roles(["seller", "administrador", "boss"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener mis devoluciones activas
    
    **Incluye:**
    - Devoluciones en todos los estados
    - Información del transfer original
    - Estado actual y progreso
    - Tiempo transcurrido
    - Razón de devolución
    """
    service = TransfersService(db)
    
    user_info = {
        'first_name': current_user.first_name,
        'last_name': current_user.last_name
    }
    
    return await service.get_my_returns(current_user.id, user_info, company_id)


@router.get("/health")
async def transfers_health():
    """Health check del módulo de transferencias"""
    return {
        "service": "transfers",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "VE003 - Solicitud de productos",
            "VE008 - Confirmación de recepción",
            "Sistema de prioridades",
            "Actualización automática de inventario",
            "Tracking completo de estado"
        ]
    }