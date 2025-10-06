# app/modules/transfers_new/service.py - VERSIÓN CORREGIDA

from typing import Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from .repository import TransfersRepository
from .schemas import TransferRequestCreate, TransferRequestResponse, MyTransferRequestsResponse, ReceptionConfirmation
from app.shared.database.models import ProductSize, Product, Location

logger = logging.getLogger(__name__)

class TransfersService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TransfersRepository(db)
    
    async def create_transfer_request(
        self,
        transfer_data: TransferRequestCreate,
        requester_id: int
    ) -> TransferRequestResponse:
        """Crear solicitud de transferencia con validación de stock"""
        
        try:
            logger.info(f"📦 Creando transferencia - Usuario: {requester_id}")
            logger.info(f"   Producto: {transfer_data.sneaker_reference_code}")
            logger.info(f"   Talla: {transfer_data.size}")
            logger.info(f"   Cantidad: {transfer_data.quantity}")
            logger.info(f"   Origen ID: {transfer_data.source_location_id}")
            logger.info(f"   Destino ID: {transfer_data.destination_location_id}")
            
            # ✅ OBTENER NOMBRE REAL DE UBICACIÓN ORIGEN
            source_location = self.db.query(Location).filter(
                Location.id == transfer_data.source_location_id
            ).first()
            
            if not source_location:
                logger.error(f"❌ Ubicación origen no encontrada: ID {transfer_data.source_location_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Ubicación origen con ID {transfer_data.source_location_id} no existe"
                )
            
            # ✅ OBTENER NOMBRE REAL DE UBICACIÓN DESTINO
            destination_location = self.db.query(Location).filter(
                Location.id == transfer_data.destination_location_id
            ).first()
            
            if not destination_location:
                logger.error(f"❌ Ubicación destino no encontrada: ID {transfer_data.destination_location_id}")
                raise HTTPException(
                    status_code=404,
                    detail=f"Ubicación destino con ID {transfer_data.destination_location_id} no existe"
                )
            
            logger.info(f"✅ Ubicación origen: '{source_location.name}'")
            logger.info(f"✅ Ubicación destino: '{destination_location.name}'")
            
            # ✅ VALIDAR STOCK CON NOMBRE REAL
            product_size = self.db.query(ProductSize).join(Product).filter(
                and_(
                    Product.reference_code == transfer_data.sneaker_reference_code,
                    ProductSize.size == transfer_data.size,
                    ProductSize.location_name == source_location.name  # ✅ NOMBRE REAL
                )
            ).first()
            
            # Validar disponibilidad
            if not product_size:
                logger.warning(
                    f"❌ Producto no encontrado: {transfer_data.sneaker_reference_code} "
                    f"talla {transfer_data.size} en '{source_location.name}'"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto {transfer_data.sneaker_reference_code} talla {transfer_data.size} "
                           f"no existe en '{source_location.name}'"
                )
            
            if product_size.quantity < transfer_data.quantity:
                logger.warning(
                    f"❌ Stock insuficiente en '{source_location.name}': "
                    f"disponible={product_size.quantity}, solicitado={transfer_data.quantity}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Stock insuficiente en '{source_location.name}'. "
                           f"Disponible: {product_size.quantity}, Solicitado: {transfer_data.quantity}"
                )
            
            logger.info(f"✅ Stock validado en '{source_location.name}': {product_size.quantity} unidades disponibles")
            
            # Crear transferencia
            transfer_dict = transfer_data.dict()
            transfer = self.repository.create_transfer_request(transfer_dict, requester_id)
            
            logger.info(f"✅ Transferencia creada: ID #{transfer.id}")
            logger.info(f"   Origen: {source_location.name} (ID: {source_location.id})")
            logger.info(f"   Destino: {destination_location.name} (ID: {destination_location.id})")
            
            # Determinar tiempo estimado y prioridad
            estimated_time = "30 minutos" if transfer_data.purpose == "cliente" else "45 minutos"
            priority = "high" if transfer_data.purpose == "cliente" else "normal"
            
            # Calcular expiración de reserva (si aplica)
            reservation_expires_at = None
            if transfer_data.purpose == "cliente":
                reservation_expires_at = (datetime.now() + timedelta(minutes=45)).isoformat()
            
            return TransferRequestResponse(
                success=True,
                message=f"Solicitud creada: {source_location.name} → {destination_location.name}",
                transfer_request_id=transfer.id,
                status=transfer.status,
                estimated_time=estimated_time,
                priority=priority,
                next_steps=[
                    f"Bodeguero de '{source_location.name}' revisará la solicitud",
                    "Se confirmará disponibilidad del producto",
                    "Se asignará corredor para el transporte",
                    f"Producto será entregado en '{destination_location.name}'"
                ],
                reservation_expires_at=reservation_expires_at
            )
            
        except HTTPException:
            # Re-lanzar HTTPExceptions tal como están
            raise
        except Exception as e:
            # Capturar error completo
            logger.exception("❌ Error inesperado creando transferencia")
            raise HTTPException(
                status_code=500, 
                detail=f"Error creando transferencia: {str(e)}"
            )
    
    async def confirm_reception(
        self,
        transfer_id: int,
        received_quantity: int,
        condition_ok: bool,
        notes: str,
        current_user: Any
    ) -> Dict[str, Any]:
        """VE008: Confirmar recepción con actualización automática de inventario"""
        
        try:
            logger.info(f"✅ Confirmando recepción - Transferencia: {transfer_id}")
            logger.info(f"   Cantidad: {received_quantity}")
            logger.info(f"   Condición OK: {condition_ok}")
            logger.info(f"   Usuario: {current_user.id}")
            
            success = self.repository.confirm_reception(
                transfer_id, received_quantity, condition_ok, notes, current_user.id
            )
            
            if not success:
                logger.warning(f"❌ Transferencia {transfer_id} no encontrada")
                raise HTTPException(status_code=404, detail="Transferencia no encontrada")
            
            logger.info(f"✅ Recepción confirmada - Inventario actualizado")
            
            return {
                "success": True,
                "message": "Recepción confirmada - Inventario actualizado automáticamente",
                "request_id": transfer_id,
                "received_quantity": received_quantity,
                "inventory_updated": condition_ok,
                "confirmed_at": datetime.now().isoformat()
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error confirmando recepción")
            raise HTTPException(
                status_code=500,
                detail=f"Error confirmando recepción: {str(e)}"
            )