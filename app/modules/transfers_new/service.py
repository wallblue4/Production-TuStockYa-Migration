# app/modules/transfers_new/service.py - VERSIÓN CORREGIDA

from typing import Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from .repository import TransfersRepository
from .schemas import (TransferRequestCreate, TransferRequestResponse, MyTransferRequestsResponse
                        , ReceptionConfirmation , ReturnRequestCreate 
                        , ReturnRequestResponse, ReturnReceptionConfirmation,  ReturnReceptionConfirmation,
    SingleFootTransferResponse)
from app.shared.schemas.inventory_distribution import (
    SingleFootTransferRequest,
    PairFormationResult,
    OppositeFootInfo,
    InventoryTypeEnum
)

from app.shared.database.models import Product, Location, TransferRequest ,ReturnNotification, ProductSize

logger = logging.getLogger(__name__)

class TransfersService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = TransfersRepository(db)
    
    # async def create_transfer_request(
    #     self,
    #     transfer_data: TransferRequestCreate,
    #     requester_id: int,
    #     company_id: int
    # ) -> TransferRequestResponse:
    #     """Crear solicitud de transferencia con validación de stock"""
        
    #     try:
    #         logger.info(f"📦 Creando transferencia - Usuario: {requester_id}")
    #         logger.info(f"   Producto: {transfer_data.sneaker_reference_code}")
    #         logger.info(f"   Talla: {transfer_data.size}")
    #         logger.info(f"   Cantidad: {transfer_data.quantity}")
    #         logger.info(f"   Origen ID: {transfer_data.source_location_id}")
    #         logger.info(f"   Destino ID: {transfer_data.destination_location_id}")
            
    #         # ✅ OBTENER NOMBRE REAL DE UBICACIÓN ORIGEN
    #         source_location = self.db.query(Location).filter(
    #             Location.id == transfer_data.source_location_id,
    #             Location.company_id == company_id
    #         ).first()
            
    #         if not source_location:
    #             logger.error(f"❌ Ubicación origen no encontrada: ID {transfer_data.source_location_id}")
    #             raise HTTPException(
    #                 status_code=404,
    #                 detail=f"Ubicación origen con ID {transfer_data.source_location_id} no existe"
    #             )
            
    #         # ✅ OBTENER NOMBRE REAL DE UBICACIÓN DESTINO
    #         destination_location = self.db.query(Location).filter(
    #             Location.id == transfer_data.destination_location_id,
    #             Location.company_id == company_id
    #         ).first()
            
    #         if not destination_location:
    #             logger.error(f"❌ Ubicación destino no encontrada: ID {transfer_data.destination_location_id}")
    #             raise HTTPException(
    #                 status_code=404,
    #                 detail=f"Ubicación destino con ID {transfer_data.destination_location_id} no existe"
    #             )
            
    #         logger.info(f"✅ Ubicación origen: '{source_location.name}'")
    #         logger.info(f"✅ Ubicación destino: '{destination_location.name}'")
            
    #         # ✅ VALIDAR STOCK CON NOMBRE REAL + MULTI-TENANT
    #         product_size = self.db.query(ProductSize).join(Product).filter(
    #             and_(
    #                 Product.reference_code == transfer_data.sneaker_reference_code,
    #                 ProductSize.size == transfer_data.size,
    #                 ProductSize.location_name == source_location.name,  # ✅ NOMBRE REAL
    #                 Product.company_id == company_id,  # ✅ MULTI-TENANT
    #                 ProductSize.company_id == company_id  # ✅ MULTI-TENANT
    #             )
    #         ).first()
            
    #         # Validar disponibilidad
    #         if not product_size:
    #             logger.warning(
    #                 f"❌ Producto no encontrado: {transfer_data.sneaker_reference_code} "
    #                 f"talla {transfer_data.size} en '{source_location.name}'"
    #             )
    #             raise HTTPException(
    #                 status_code=404,
    #                 detail=f"Producto {transfer_data.sneaker_reference_code} talla {transfer_data.size} "
    #                        f"no existe en '{source_location.name}'"
    #             )
            
    #         if product_size.quantity < transfer_data.quantity:
    #             logger.warning(
    #                 f"❌ Stock insuficiente en '{source_location.name}': "
    #                 f"disponible={product_size.quantity}, solicitado={transfer_data.quantity}"
    #             )
    #             raise HTTPException(
    #                 status_code=400,
    #                 detail=f"Stock insuficiente en '{source_location.name}'. "
    #                        f"Disponible: {product_size.quantity}, Solicitado: {transfer_data.quantity}"
    #             )
            
    #         logger.info(f"✅ Stock validado en '{source_location.name}': {product_size.quantity} unidades disponibles")
            
    #         # Crear transferencia
    #         transfer_dict = transfer_data.dict()
    #         transfer = self.repository.create_transfer_request(transfer_dict, requester_id, company_id)
            
    #         logger.info(f"✅ Transferencia creada: ID #{transfer.id}")
    #         logger.info(f"   Origen: {source_location.name} (ID: {source_location.id})")
    #         logger.info(f"   Destino: {destination_location.name} (ID: {destination_location.id})")
            
    #         # Determinar tiempo estimado y prioridad
    #         estimated_time = "30 minutos" if transfer_data.purpose == "cliente" else "45 minutos"
    #         priority = "high" if transfer_data.purpose == "cliente" else "normal"
            
    #         # Calcular expiración de reserva (si aplica)
    #         reservation_expires_at = None
    #         if transfer_data.purpose == "cliente":
    #             reservation_expires_at = (datetime.now() + timedelta(minutes=45)).isoformat()
            
    #         return TransferRequestResponse(
    #             success=True,
    #             message=f"Solicitud creada: {source_location.name} → {destination_location.name}",
    #             transfer_request_id=transfer.id,
    #             status=transfer.status,
    #             estimated_time=estimated_time,
    #             priority=priority,
    #             next_steps=[
    #                 f"Bodeguero de '{source_location.name}' revisará la solicitud",
    #                 "Se confirmará disponibilidad del producto",
    #                 "Se asignará corredor para el transporte",
    #                 f"Producto será entregado en '{destination_location.name}'"
    #             ],
    #             reservation_expires_at=reservation_expires_at
    #         )
            
    #     except HTTPException:
    #         # Re-lanzar HTTPExceptions tal como están
    #         raise
    #     except Exception as e:
    #         # Capturar error completo
    #         logger.exception("❌ Error inesperado creando transferencia")
    #         raise HTTPException(
    #             status_code=500, 
    #             detail=f"Error creando transferencia: {str(e)}"
    #         )


    async def create_transfer_request(
        self,
        transfer_data: TransferRequestCreate,
        requester_id: int,
        company_id: int
    ) -> TransferRequestResponse:
        """
        Crear solicitud de transferencia con validación de stock
        ✅ MEJORADO: Ahora soporta pies individuales
        """
        
        try:
            logger.info(f"📦 Creando transferencia - Usuario: {requester_id}")
            logger.info(f"   Producto: {transfer_data.sneaker_reference_code}")
            logger.info(f"   Talla: {transfer_data.size}")
            logger.info(f"   Cantidad: {transfer_data.quantity}")
            logger.info(f"   Tipo Inventario: {transfer_data.inventory_type}")
            logger.info(f"   Origen ID: {transfer_data.source_location_id}")
            logger.info(f"   Destino ID: {transfer_data.destination_location_id}")
            
            # 1. Validar ubicaciones
            source_location = self.db.query(Location).filter(
                and_(
                    Location.id == transfer_data.source_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            destination_location = self.db.query(Location).filter(
                and_(
                    Location.id == transfer_data.destination_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            if not source_location or not destination_location:
                raise HTTPException(status_code=404, detail="Ubicación no encontrada")
            
            logger.info(f"   ✅ Ubicaciones validadas: {source_location.name} → {destination_location.name}")
            
            # 2. Buscar producto
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == transfer_data.sneaker_reference_code,
                    Product.company_id == company_id
                )
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto {transfer_data.sneaker_reference_code} no encontrado"
                )
            
            logger.info(f"   ✅ Producto encontrado: {product.brand} {product.model}")
            
            # 3. ✅ VALIDAR DISPONIBILIDAD POR TIPO DE INVENTARIO
            if transfer_data.inventory_type != InventoryTypeEnum.PAIR:
                # Es un pie individual - validar disponibilidad específica
                validation = self.repository.validate_single_foot_availability(
                    product_id=product.id,
                    size=transfer_data.size,
                    inventory_type=transfer_data.inventory_type,
                    location_name=source_location.name,
                    quantity=transfer_data.quantity,
                    company_id=company_id
                )
                
                if not validation['can_fulfill']:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Stock insuficiente de pie {transfer_data.inventory_type}. "
                            f"Disponible: {validation['current_stock']}, "
                            f"Solicitado: {transfer_data.quantity}"
                        )
                    )
                
                logger.info(f"   ✅ Disponibilidad validada: {validation['current_stock']} {transfer_data.inventory_type}")
            else:
                # Es un par completo - validación normal
                product_size = self.db.query(ProductSize).filter(
                    and_(
                        ProductSize.product_id == product.id,
                        ProductSize.size == transfer_data.size,
                        ProductSize.location_name == source_location.name,
                        ProductSize.inventory_type == 'pair',
                        ProductSize.company_id == company_id
                    )
                ).first()
                
                if not product_size or product_size.quantity < transfer_data.quantity:
                    available = product_size.quantity if product_size else 0
                    raise HTTPException(
                        status_code=400,
                        detail=f"Stock insuficiente. Disponible: {available}, Solicitado: {transfer_data.quantity}"
                    )
                
                logger.info(f"   ✅ Disponibilidad validada: {product_size.quantity} pares")
            
            # 4. ✅ BUSCAR PIE OPUESTO EN DESTINO (si es pie individual)
            opposite_foot_info = None
            pair_formation_potential = {
                "opposite_foot_available": False,
                "can_form_pairs": False,
                "quantity_formable": 0
            }
            
            if transfer_data.inventory_type in [InventoryTypeEnum.LEFT_ONLY, InventoryTypeEnum.RIGHT_ONLY]:
                opposite_foot_info = self.repository.find_opposite_foot_in_location(
                    reference_code=transfer_data.sneaker_reference_code,
                    size=transfer_data.size,
                    location_id=transfer_data.destination_location_id,
                    received_inventory_type=transfer_data.inventory_type,
                    company_id=company_id
                )
                
                if opposite_foot_info and opposite_foot_info.get("exits"):
                    pair_formation_potential = {
                        "opposite_foot_available": True,
                        "can_form_pairs": True,
                        "quantity_formable": min(transfer_data.quantity, opposite_foot_info.quantity)
                    }
                    logger.info(f"   🎉 Pie opuesto disponible en destino! Se pueden formar {pair_formation_potential['quantity_formable']} par(es)")
            
            # 5. Determinar prioridad
            priority = self._calculate_priority(transfer_data.purpose)
            
            # 6. Crear transferencia
            transfer_dict = {
                "source_location_id": transfer_data.source_location_id,
                "destination_location_id": transfer_data.destination_location_id,
                "sneaker_reference_code": transfer_data.sneaker_reference_code,
                "brand": transfer_data.brand,
                "model": transfer_data.model,
                "size": transfer_data.size,
                "quantity": transfer_data.quantity,
                "purpose": transfer_data.purpose,
                "pickup_type": transfer_data.pickup_type,
                "destination_type": transfer_data.destination_type,
                "notes": transfer_data.notes,
                "inventory_type": transfer_data.inventory_type  # ✅ NUEVO
            }
            
            new_transfer = self.repository.create_transfer_request(
                transfer_dict, 
                requester_id, 
                company_id
            )
            
            logger.info(f"   ✅ Transferencia creada - ID: {new_transfer.id}")
            
            # 7. Generar próximos pasos
            next_steps = self._generate_next_steps(new_transfer, source_location.type)
            
            # 8. Retornar respuesta
            return TransferRequestResponse(
                success=True,
                message="Solicitud de transferencia creada exitosamente",
                transfer_request_id=new_transfer.id,
                status=new_transfer.status,
                estimated_time=self._estimate_delivery_time(source_location.type, destination_location.type),
                priority=priority,
                next_steps=next_steps,
                inventory_type=transfer_data.inventory_type,
                opposite_foot_info=opposite_foot_info,
                pair_formation_potential=pair_formation_potential
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error creando transferencia")
            raise HTTPException(
                status_code=500,
                detail=f"Error creando transferencia: {str(e)}"
            )


    async def create_single_foot_transfer(
        self,
        request: SingleFootTransferRequest,
        user_id: int,
        company_id: int
    ) -> SingleFootTransferResponse:
        """
        🆕 Crear transferencia de un pie individual
        ✅ CORRECCIÓN: Mapear foot_side correctamente a inventory_type
        """
        
        try:
            logger.info(f"👟 Creando transferencia de pie individual")
            logger.info(f"   Lado: {request.foot_side}")
            logger.info(f"   Producto: {request.sneaker_reference_code}")
            logger.info(f"   Talla: {request.size}")
            logger.info(f"   Cantidad: {request.quantity}")
            
            # ✅ MAPEAR CORRECTAMENTE foot_side → inventory_type
            inventory_type = 'left_only' if request.foot_side == 'left' else 'right_only'
            logger.info(f"   ✅ Inventory type: {inventory_type}")
            
            # 1. Buscar producto
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == request.sneaker_reference_code,
                    Product.company_id == company_id
                )
            ).first()
            
            if not product:
                raise HTTPException(404, "Producto no encontrado")
            
            # 2. Buscar ubicaciones
            source_location = self.db.query(Location).filter(
                and_(
                    Location.id == request.source_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            destination_location = self.db.query(Location).filter(
                and_(
                    Location.id == request.destination_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            if not source_location or not destination_location:
                raise HTTPException(404, "Ubicación no encontrada")
            
            # 3. Validar disponibilidad del pie específico
            validation = self.repository.validate_single_foot_availability(
                product_id=product.id,
                size=request.size,
                inventory_type=inventory_type,  # ✅ Usar inventory_type correcto
                location_name=source_location.name,
                quantity=request.quantity,
                company_id=company_id
            )
            
            if not validation['can_fulfill']:
                raise HTTPException(
                    400,
                    f"Stock insuficiente. Disponible: {validation['current_stock']} pie(s) {request.foot_side}"
                )
            
            logger.info(f"   ✅ Stock disponible: {validation['current_stock']}")
            
            # 4. Buscar pie opuesto en destino
            opposite_foot_info = self.repository.find_opposite_foot_in_location(
                reference_code=request.sneaker_reference_code,
                size=request.size,
                location_id=request.destination_location_id,
                received_inventory_type=inventory_type,  # ✅ Usar inventory_type correcto
                company_id=company_id
            )
            
            can_auto_form = False
            quantity_formable = 0
            
            # Acceder como diccionario
            if opposite_foot_info and opposite_foot_info.get('exists'):
                can_auto_form = True
                quantity_formable = min(request.quantity, opposite_foot_info.get('quantity', 0))
                logger.info(f"   🎉 Pie opuesto encontrado! Se pueden formar {quantity_formable} par(es)")
            else:
                logger.info(f"   ℹ️ No hay pie opuesto en destino - no se formará par automáticamente")
            
            # 5. Crear transferencia usando el método base
            transfer_data = TransferRequestCreate(
                source_location_id=request.source_location_id,
                destination_location_id=request.destination_location_id,
                sneaker_reference_code=request.sneaker_reference_code,
                brand=product.brand,
                model=product.model,
                size=request.size,
                quantity=request.quantity,
                purpose=request.purpose,
                pickup_type=request.pickup_type,
                destination_type='bodega',
                notes=request.notes,
                inventory_type=inventory_type  # ✅ CRÍTICO: Pasar inventory_type correcto
            )
            
            logger.info(f"   📦 Creando TransferRequest con inventory_type='{inventory_type}'")
            
            base_response = await self.create_transfer_request(
                transfer_data,
                user_id,
                company_id
            )
            
            # 6. Construir respuesta especializada
            next_steps = [
                "1. Bodega procesará la solicitud",
                "2. Se notificará cuando esté listo para recoger"
            ]
            
            if can_auto_form:
                next_steps.append(
                    f"3. ¡BONUS! Al recibir, se formará automáticamente {quantity_formable} par(es) con el pie opuesto disponible"
                )
            
            logger.info(f"   ✅ Transferencia creada exitosamente - ID: {base_response.transfer_request_id}")
            
            return SingleFootTransferResponse(
                success=True,
                message=f"Transferencia de pie {request.foot_side} creada exitosamente",
                transfer_request_id=base_response.transfer_request_id,
                inventory_type=inventory_type,  # ✅ Retornar el correcto
                foot_side=request.foot_side,
                opposite_foot_available=opposite_foot_info is not None and opposite_foot_info.get('exists', False),
                can_auto_form_pair=can_auto_form,
                quantity_formable=quantity_formable,
                status="pending",
                next_steps=next_steps
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"❌ Error creando transferencia de pie individual: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error: {str(e)}"
            )
    
    async def confirm_reception(
        self,
        transfer_id: int,
        received_quantity: int,
        condition_ok: bool,
        notes: str,
        current_user: Any,
        company_id: int
    ) -> Dict[str, Any]:
        """VE008: Confirmar recepción con actualización automática de inventario"""
        
        try:
            logger.info(f"✅ Confirmando recepción - Transferencia: {transfer_id}")
            logger.info(f"   Cantidad: {received_quantity}")
            logger.info(f"   Condición OK: {condition_ok}")
            logger.info(f"   Usuario: {current_user.id}")
            
            success = self.repository.confirm_reception(
                transfer_id, received_quantity, condition_ok, notes, current_user.id, company_id
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


    async def get_my_transfer_requests(self, user_id: int, user_info: Dict[str, Any], company_id: int) -> Dict[str, Any]:
        """Obtener mis solicitudes de transferencia"""
        transfers = self.repository.get_transfer_requests_by_user(user_id, company_id)
        summary = self.repository.get_transfer_summary(user_id, company_id)
        
        return {
            "success": True,
            "message": "Mis solicitudes de transferencia",
            "transfers": transfers,
            "count": len(transfers),
            "summary": summary,
            "user_info": {
                "name": f"{user_info['first_name']} {user_info['last_name']}",
                "user_id": user_id
            }
        }

    async def create_return_request(
        self,
        return_data: ReturnRequestCreate,
        requester_id: int,
        company_id: int
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
                TransferRequest.id == return_data.original_transfer_id,
                TransferRequest.company_id == company_id
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
                    TransferRequest.company_id == company_id,
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
                company_id=company_id,
                
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
                Location.id == original.source_location_id,
                Location.company_id == company_id
            ).first()
            
            notification = ReturnNotification(
                transfer_request_id=return_transfer.id,
                returned_to_location=source_location.name if source_location else "Bodega",
                notes=return_data.notes or f"Devolución por: {return_data.reason}",
                read_by_requester=True,
                created_at=datetime.now(),
                company_id=company_id
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
    
    async def get_my_returns(self, vendor_id: int, user_info: Dict[str, Any], company_id: int) -> Dict[str, Any]:
        """Obtener mis devoluciones activas"""
        returns = self.repository.get_returns_by_vendor(vendor_id, company_id)
        
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
    
    def _calculate_priority(self, purpose: str) -> str:
        """Calcular prioridad basada en propósito"""
        if purpose == "cliente":
            return "alta"
        elif purpose == "exhibition":
            return "media"
        else:
            return "normal"
    
    def _estimate_delivery_time(self, source_type: str, destination_type: str) -> str:
        """Estimar tiempo de entrega"""
        if source_type == "bodega" and destination_type == "local":
            return "30-45 minutos"
        elif source_type == "local" and destination_type == "bodega":
            return "20-30 minutos"
        else:
            return "45-60 minutos"
    
    def _generate_next_steps(self, transfer: TransferRequest, source_type: str) -> list:
        """Generar próximos pasos según el flujo"""
        if source_type == "bodega":
            return [
                "1. Bodeguero procesará la solicitud",
                "2. Se notificará cuando esté listo",
                "3. Corredor/Vendedor recogerá el producto"
            ]
        else:
            return [
                "1. Esperando que el vendedor prepare el producto",
                "2. Corredor recogerá y entregará"
            ]