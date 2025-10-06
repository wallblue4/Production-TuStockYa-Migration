# app/modules/transfers_new/service.py - VERSIÓN CORREGIDA

from typing import Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from .repository import TransfersRepository
from .schemas import TransferRequestCreate, TransferRequestResponse, MyTransferRequestsResponse, ReceptionConfirmation , ReturnRequestCreate , ReturnRequestResponse, ReturnReceptionConfirmation
from app.shared.database.models import ProductSize, Product, Location ,TransferRequest, ReturnNotification

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


    async def create_return_request(
        self,
        return_data: ReturnRequestCreate,
        requester_id: int
    ) -> ReturnRequestResponse:
        """
        VE006: Crear solicitud de devolución de producto
        
        Proceso:
        1. Validar transferencia original existe y completada
        2. Validar permisos (solo solicitante original)
        3. Validar cantidad a devolver
        4. Crear nueva transferencia con ruta INVERTIDA
        5. Marcar como tipo 'return'
        6. Crear notificación
        """
        try:
            logger.info(f"🔄 Creando devolución - Usuario: {requester_id}")
            logger.info(f"   Transfer original: {return_data.original_transfer_id}")
            
            # ==================== VALIDACIÓN 1: TRANSFERENCIA ORIGINAL ====================
            original = self.db.query(TransferRequest).filter(
                TransferRequest.id == return_data.original_transfer_id
            ).first()
            
            if not original:
                logger.error(f"❌ Transferencia original no encontrada")
                raise HTTPException(
                    status_code=404,
                    detail=f"Transferencia #{return_data.original_transfer_id} no existe"
                )
            
            logger.info(f"✅ Transfer original encontrado: {original.sneaker_reference_code}")
            
            # ==================== VALIDACIÓN 2: ESTADO ====================
            if original.status != 'completed':
                logger.error(f"❌ Estado inválido: {original.status}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se pueden devolver transferencias completadas. Estado actual: {original.status}"
                )
            
            # ==================== VALIDACIÓN 3: PERMISOS ====================
            if original.requester_id != requester_id:
                logger.error(f"❌ Usuario no autorizado: {requester_id} != {original.requester_id}")
                raise HTTPException(
                    status_code=403,
                    detail="Solo el solicitante original puede crear devolución"
                )
            
            # ==================== VALIDACIÓN 4: CANTIDAD ====================
            if return_data.quantity_to_return > original.quantity:
                logger.error(
                    f"❌ Cantidad excede lo recibido: "
                    f"{return_data.quantity_to_return} > {original.quantity}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Cantidad a devolver ({return_data.quantity_to_return}) "
                           f"excede lo recibido originalmente ({original.quantity})"
                )
            
            # ==================== VALIDACIÓN 5: NO DEVOLVER DOS VECES ====================
            existing_return = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.original_transfer_id == original.id,
                    TransferRequest.status.in_(['pending', 'accepted', 'in_transit', 'delivered'])
                )
            ).first()
            
            if existing_return:
                logger.warning(f"⚠️ Ya existe devolución activa: {existing_return.id}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya existe una devolución activa para esta transferencia (ID: {existing_return.id})"
                )
            
            logger.info(f"✅ Todas las validaciones pasaron")
            
            # ==================== CREAR RETURN (INVERTIR ORIGEN-DESTINO) ====================
            logger.info(f"📝 Creando return en BD")

            return_pickup_type = return_data.pickup_type
            
            return_transfer = TransferRequest(
                original_transfer_id=original.id,
                requester_id=requester_id,
                
                # ← INVERTIR ubicaciones (clave del return)
                source_location_id=original.destination_location_id,  # Local vendedor
                destination_location_id=original.source_location_id,  # Bodega
                
                # Mismos datos de producto
                sneaker_reference_code=original.sneaker_reference_code,
                brand=original.brand,
                model=original.model,
                size=original.size,
                quantity=return_data.quantity_to_return,
                
                # Marcar como return
                purpose='return',
                pickup_type=return_pickup_type,  # Returns siempre con corredor
                destination_type='bodega',
                request_type='return',  # Explícito
                
                status='pending',
                notes=(
                    f"DEVOLUCIÓN de Transfer #{original.id}\n"
                    f"Razón: {return_data.reason}\n"
                    f"Condición: {return_data.product_condition}\n"
                    f"{return_data.notes or ''}"
                ),
                requested_at=datetime.now()
            )
            
            self.db.add(return_transfer)
            self.db.flush()
            self.db.refresh(return_transfer)
            
            logger.info(f"✅ Return creado con ID: {return_transfer.id}")
            
            # ==================== CREAR NOTIFICACIÓN ====================
            source_location = self.db.query(Location).filter(
                Location.id == original.source_location_id
            ).first()
            
            notification = ReturnNotification(
                transfer_request_id=return_transfer.id,
                returned_to_location=source_location.name if source_location else "Bodega",
                notes=return_data.notes or f"Devolución por: {return_data.reason}",
                read_by_requester=True,
                created_at=datetime.now()
            )
            self.db.add(notification)
            
            # ==================== COMMIT ====================
            self.db.commit()
            
            logger.info(f"✅ Devolución creada exitosamente")
            
            # ==================== RESPUESTA ====================
            if return_pickup_type == 'vendedor':
                workflow_steps = [
                    "1. 📋 Bodeguero aceptará la solicitud (BG001-BG002)",
                    "2. 🚶 TÚ deberás llevar el producto a bodega personalmente",
                    "3. 🏪 Bodeguero confirmará que recibió el producto físicamente",
                    "4. 🔍 Bodeguero verificará condición y restaurará inventario (BG010)"
                ]
                estimated_time = "10-20 minutos (depende de tu disponibilidad)"
                message = "Devolución creada - Llevarás el producto a bodega personalmente"
                next_action = "Esperar que bodeguero acepte, luego ir a bodega con el producto"
            else:
                workflow_steps = [
                    "1. 📋 Bodeguero aceptará la solicitud (BG001-BG002)",
                    "2. 🚚 Corredor recogerá el producto en tu local (CO002-CO003)",
                    "3. 🚚 Corredor entregará en bodega (CO004)",
                    "4. 🔍 Bodeguero confirmará recepción y restaurará inventario (BG010)"
                ]
                estimated_time = "15 minutos"
                message = "Devolución creada - Un corredor recogerá el producto"
                next_action = "Esperar que bodeguero acepte, luego corredor coordinará recogida"

            return ReturnRequestResponse(
                success=True,
                message=f"Devolución creada - Sigue el mismo flujo que transferencia normal",
                return_id=return_transfer.id,
                original_transfer_id=original.id,
                status="pending",
                pickup_type=return_pickup_type,
                estimated_return_time="2-3 horas",
                workflow_steps=workflow_steps,
                priority="normal",
                next_action=next_action
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error inesperado creando devolución")
            self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error creando devolución: {str(e)}"
            )
    
    async def get_my_returns(self, vendor_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """Obtener mis devoluciones activas"""
        returns = self.repository.get_returns_by_vendor(vendor_id)
        
        summary = {
            "total_returns": len(returns),
            "pending": len([r for r in returns if r['status'] == 'pending']),
            "in_progress": len([r for r in returns if r['status'] in ['accepted', 'in_transit']]),
            "completed": len([r for r in returns if r['status'] == 'completed'])
        }
        
        return {
            "success": True,
            "message": "Mis devoluciones",
            "returns": returns,
            "count": len(returns),
            "summary": summary,
            "vendor_info": {
                "name": f"{user_info['first_name']} {user_info['last_name']}",
                "vendor_id": vendor_id
            }
        }