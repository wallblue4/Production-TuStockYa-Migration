# app/modules/transfers_new/service.py - VERSIÓN CORREGIDA

from typing import Dict, Any , Optional ,List
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from .repository import TransfersRepository
from .schemas import (TransferRequestCreate, TransferRequestResponse, MyTransferRequestsResponse
                        , ReceptionConfirmation , ReturnRequestCreate 
                        , ReturnRequestResponse, ReturnReceptionConfirmation,  ReturnReceptionConfirmation,ReturnSplitInfo,
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
        🆕 ACTUALIZADO: Crear solicitud de devolución con soporte para:
        - Pies individuales (left_only, right_only)
        - Pares completos
        - Partición automática de pares cuando sea necesario
        
        Flujo:
        1. Validar transfer original y permisos
        2. Validar disponibilidad (considerando pies sueltos + pares)
        3. Si requiere partición, partir pares automáticamente
        4. Crear TransferRequest de tipo 'return'
        5. Registrar operación en historial
        6. Retornar respuesta con información de partición
        
        Args:
            return_data: Datos de la devolución (incluye inventory_type y foot_side)
            requester_id: ID del usuario que solicita la devolución
            company_id: ID de la compañía
        
        Returns:
            ReturnRequestResponse con información completa de la devolución
        
        Raises:
            HTTPException 400: Si no se puede cumplir la devolución
            HTTPException 403: Si no tiene permisos
            HTTPException 404: Si no se encuentra el transfer original
        """
        
        try:
            logger.info(f"📦 Creando devolución - Usuario: {requester_id}")
            logger.info(f"   Transfer original: {return_data.original_transfer_id}")
            logger.info(f"   Cantidad: {return_data.quantity_to_return}")
            logger.info(f"   Tipo: {return_data.inventory_type}")
            if return_data.foot_side:
                logger.info(f"   Lado: {return_data.foot_side}")
            
            # ========== 1. VALIDAR TRANSFER ORIGINAL ==========
            original_transfer = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.id == return_data.original_transfer_id,
                    TransferRequest.company_id == company_id
                )
            ).first()
            
            if not original_transfer:
                raise HTTPException(
                    status_code=404,
                    detail="Transfer original no encontrado"
                )
            
            # Validar que esté completado
            if original_transfer.status != 'completed':
                raise HTTPException(
                    status_code=400,
                    detail=f"Solo se pueden devolver transfers completados. Estado actual: {original_transfer.status}"
                )
            
            # Validar que sea el solicitante original
            if original_transfer.requester_id != requester_id:
                raise HTTPException(
                    status_code=403,
                    detail="Solo el solicitante original puede devolver el producto"
                )
            
            # Validar que no se haya devuelto antes
            existing_return = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.original_transfer_id == return_data.original_transfer_id,
                    TransferRequest.company_id == company_id
                )
            ).first()
            
            if existing_return:
                raise HTTPException(
                    status_code=400,
                    detail=f"Este transfer ya fue devuelto (Return ID: {existing_return.id})"
                )
            
            # Validar cantidad
            quantity_received = original_transfer.received_quantity or original_transfer.quantity
            if return_data.quantity_to_return > quantity_received:
                raise HTTPException(
                    status_code=400,
                    detail=f"No puedes devolver más de lo que recibiste. Recibido: {quantity_received}"
                )
            
            logger.info(f"   ✅ Transfer original validado")
            
            # ========== 2. OBTENER INFORMACIÓN DEL PRODUCTO Y UBICACIONES ==========
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == original_transfer.sneaker_reference_code,
                    Product.company_id == company_id
                )
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail="Producto no encontrado"
                )
            
            # Ubicación actual (destino del transfer original = origen del return)
            current_location = self.db.query(Location).filter(
                and_(
                    Location.id == original_transfer.destination_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            # Ubicación destino (origen del transfer original = destino del return)
            destination_location = self.db.query(Location).filter(
                and_(
                    Location.id == original_transfer.source_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            if not current_location or not destination_location:
                raise HTTPException(
                    status_code=404,
                    detail="Ubicación no encontrada"
                )
            
            logger.info(f"   📍 Ubicación actual: {current_location.name}")
            logger.info(f"   📍 Ubicación destino: {destination_location.name}")
            
            # ========== 3. 🆕 VALIDAR DISPONIBILIDAD CON LÓGICA DE PARTICIÓN ==========
            inventory_type = return_data.inventory_type or InventoryTypeEnum.PAIR
            inventory_type_str = inventory_type.value if isinstance(inventory_type, InventoryTypeEnum) else inventory_type
            
            logger.info(f"   🔍 Validando disponibilidad para tipo: {inventory_type_str}")
            
            validation = self.repository.validate_return_availability(
                product_id=product.id,
                size=original_transfer.size,
                inventory_type=inventory_type_str,
                location_name=current_location.name,
                quantity_requested=return_data.quantity_to_return,
                company_id=company_id
            )
            
            if not validation['can_fulfill']:
                logger.error(f"   ❌ {validation.get('error', 'Stock insuficiente')}")
                raise HTTPException(
                    status_code=400,
                    detail=validation.get('error', 'Stock insuficiente para devolución')
                )
            
            logger.info(f"   ✅ Disponibilidad validada")
            
            # ========== 4. 🆕 SI REQUIERE PARTICIÓN, EJECUTARLA ==========
            split_info = None
            
            if validation.get('requires_split'):
                pairs_to_split = validation['pairs_to_split']
                logger.info(f"   🔪 Devolución requiere partir {pairs_to_split} par(es)")
                
                try:
                    split_result = self.repository.split_pair_for_return(
                        product_id=product.id,
                        size=original_transfer.size,
                        location_name=current_location.name,
                        inventory_type_needed=inventory_type_str,
                        pairs_to_split=pairs_to_split,
                        company_id=company_id,
                        user_id=requester_id,
                        return_id=0  # Se actualizará después de crear el return
                    )
                    
                    logger.info(f"   ✅ Partición completada exitosamente")
                    logger.info(f"      - Pares partidos: {split_result['pairs_split']}")
                    logger.info(f"      - Pies opuestos agregados: {split_result['opposite_feet_added']}")
                    logger.info(f"      - Pares restantes: {split_result['pairs_remaining']}")
                    
                    # Crear objeto de información de partición
                    split_info = ReturnSplitInfo(
                        requires_split=True,
                        loose_feet_used=validation['loose_feet_to_use'],
                        pairs_to_split=validation['pairs_to_split'],
                        remaining_opposite_feet=validation['remaining_opposite_feet'],
                        total_available=validation['total_feet_available']
                    )
                    
                except Exception as e:
                    logger.exception(f"   ❌ Error ejecutando partición: {str(e)}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Error al partir pares para devolución: {str(e)}"
                    )
            else:
                logger.info(f"   ℹ️ No requiere partición de pares")
            
            # ========== 5. CREAR TRANSFERREQUEST DE DEVOLUCIÓN ==========
            logger.info(f"   📝 Creando TransferRequest de devolución")
            
            # Preparar notas con información de devolución
            return_notes = f"Razón: {return_data.reason}\n"
            if return_data.product_condition != 'good':
                return_notes += f"Condición: {return_data.product_condition}\n"
            if return_data.notes:
                return_notes += f"{return_data.notes}\n"
            if split_info:
                return_notes += f"\n⚠️ PARTICIÓN AUTOMÁTICA: {split_info.pairs_to_split} par(es) partido(s)"
            
            return_transfer = TransferRequest(
                company_id=company_id,
                requester_id=requester_id,
                source_location_id=original_transfer.destination_location_id,  # Invertido
                destination_location_id=original_transfer.source_location_id,   # Invertido
                sneaker_reference_code=original_transfer.sneaker_reference_code,
                brand=original_transfer.brand,
                model=original_transfer.model,
                size=original_transfer.size,
                quantity=return_data.quantity_to_return,
                inventory_type=inventory_type_str,  # 🆕 Guardar tipo correcto
                purpose='return',
                notes=return_notes,
                pickup_type=return_data.pickup_type,
                destination_type='bodega o local',
                request_type="return",
                status='pending',  
                requested_at=datetime.now(),
                original_transfer_id=return_data.original_transfer_id
            )
            
            self.db.add(return_transfer)
            self.db.commit()
            self.db.refresh(return_transfer)
            
            logger.info(f"   ✅ TransferRequest creado - ID: {return_transfer.id}")
            
            # ========== 6. ACTUALIZAR REFERENCE_ID EN INVENTORY_CHANGE SI HUBO SPLIT ==========
            if split_info:
                logger.info(f"   📝 Actualizando reference_id en InventoryChange")
                
                from app.shared.database.models import InventoryChange
                
                self.db.query(InventoryChange).filter(
                    and_(
                        InventoryChange.product_id == product.id,
                        InventoryChange.reference_id == 0,
                        InventoryChange.change_type == 'pair_split_for_return',
                        InventoryChange.size == original_transfer.size,
                        InventoryChange.company_id == company_id
                    )
                ).update({"reference_id": return_transfer.id})
                
                self.db.commit()
                logger.info(f"   ✅ Reference_id actualizado")
            
            # ========== 7. GENERAR WORKFLOW STEPS ==========
            workflow_steps = self._generate_return_workflow_steps(
                return_data.pickup_type,
                destination_location.type
            )
            
            # Agregar mensaje sobre partición si aplica
            if split_info:
                opposite_type_name = (
                    "derecho(s)" if inventory_type_str == 'left_only' 
                    else "izquierdo(s)"
                )
                
                split_message = (
                    f"✂️ Se partieron {split_info.pairs_to_split} par(es) automáticamente para la devolución. "
                    f"Quedan {split_info.remaining_opposite_feet} pie(s) {opposite_type_name} en tu inventario."
                )
                workflow_steps.insert(0, split_message)
            
            # ========== 8. CONSTRUIR Y RETORNAR RESPUESTA ==========
            response_message = self._generate_return_message(
                return_data.pickup_type,
                split_info,
                inventory_type_str
            )
            
            logger.info(f"✅ Devolución creada exitosamente - ID: {return_transfer.id}")
            
            return ReturnRequestResponse(
                success=True,
                message=response_message,
                return_id=return_transfer.id,
                original_transfer_id=return_data.original_transfer_id,
                status=return_transfer.status,
                pickup_type=return_data.pickup_type,
                workflow_steps=workflow_steps,
                priority='normal',
                split_info=split_info,
                inventory_type=inventory_type_str
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"❌ Error creando devolución: {str(e)}")
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


    def _generate_return_message(
        self,
        pickup_type: str,
        split_info: Optional[ReturnSplitInfo],
        inventory_type: str
    ) -> str:
        """
        🆕 Generar mensaje apropiado según tipo de pickup y si hubo partición
        
        Args:
            pickup_type: 'corredor' o 'vendedor'
            split_info: Información de partición (None si no hubo)
            inventory_type: Tipo de inventario ('pair', 'left_only', 'right_only')
        
        Returns:
            str: Mensaje descriptivo para el usuario
        """
        
        # Mensaje base según tipo de pickup
        if pickup_type == 'vendedor':
            base_message = "Devolución creada exitosamente. Llevarás el producto tú mismo a bodega"
        else:
            base_message = "Devolución creada exitosamente. Un corredor recogerá el producto"
        
        # Agregar información sobre partición si aplica
        if split_info and split_info.requires_split:
            foot_type = (
                "izquierdos" if inventory_type == 'left_only'
                else "derechos" if inventory_type == 'right_only'
                else "pares"
            )
            
            opposite_type = (
                "derechos" if inventory_type == 'left_only'
                else "izquierdos" if inventory_type == 'right_only'
                else ""
            )
            
            if inventory_type in ['left_only', 'right_only']:
                split_detail = (
                    f". Se partieron automáticamente {split_info.pairs_to_split} par(es) "
                    f"para obtener los {split_info.pairs_to_split} pie(s) {foot_type} necesarios. "
                    f"Los {split_info.remaining_opposite_feet} pie(s) {opposite_type} permanecen en tu inventario"
                )
                return base_message + split_detail
        
        return base_message

    async def _reverse_pair_before_return(
        self,
        return_transfer: TransferRequest,
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """
        🆕 Revertir par auto-formado antes de procesar devolución
        
        Escenario:
        - Vendedor recibió pie individual (Transfer A)
        - Sistema auto-formó par con pie opuesto existente (Transfer B)
        - Vendedor devuelve Transfer A
        - ANTES de restaurar inventario en bodega, debemos:
        1. Separar el par en pies individuales
        2. Mantener el pie de Transfer B en el local
        3. Devolver solo el pie de Transfer A a bodega
        
        Proceso:
        1. Validar que el par existe en el local del vendedor
        2. Restar 1 del inventario de 'pair'
        3. Sumar 1 a cada pie individual (left_only y right_only)
        4. Registrar reversión en historial
        
        Args:
            return_transfer: El TransferRequest de return que tiene auto_formed_pair_id
            warehouse_keeper_id: ID del bodeguero que procesa
        
        Returns:
            Dict con resultado de la reversión
        """
        
        try:
            logger.info(f"🔄 Iniciando reversión de par auto-formado")
            logger.info(f"   Return Transfer ID: {return_transfer.id}")
            logger.info(f"   Original Transfer ID: {return_transfer.original_transfer_id}")
            logger.info(f"   Vinculado con Transfer ID: {return_transfer.auto_formed_pair_id}")
            
            # ==================== OBTENER TRANSFERENCIA ORIGINAL ====================
            original_transfer = self.db.query(TransferRequest).filter(
                TransferRequest.id == return_transfer.original_transfer_id
            ).first()
            
            if not original_transfer:
                raise ValueError("Transferencia original no encontrada")
            
            # ==================== OBTENER UBICACIÓN DEL VENDEDOR ====================
            # El vendedor está en destination_location del transfer original
            vendor_location = self.db.query(Location).filter(
                and_(
                    Location.id == original_transfer.destination_location_id,
                    Location.company_id == self.company_id
                )
            ).first()
            
            if not vendor_location:
                raise ValueError("Ubicación del vendedor no encontrada")
            
            logger.info(f"   Ubicación vendedor: {vendor_location.name}")
            
            # ==================== OBTENER PRODUCTO ====================
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == return_transfer.sneaker_reference_code,
                    Product.company_id == self.company_id
                )
            ).first()
            
            if not product:
                raise ValueError(f"Producto {return_transfer.sneaker_reference_code} no encontrado")
            
            # ==================== BUSCAR EL PAR EN EL LOCAL DEL VENDEDOR ====================
            pair_inventory = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == return_transfer.size,
                    ProductSize.location_name == vendor_location.name,
                    ProductSize.inventory_type == 'pair',
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            if not pair_inventory or pair_inventory.quantity < 1:
                # Posiblemente el vendedor ya vendió el par
                logger.warning(f"⚠️ No hay par disponible para revertir")
                logger.warning(f"   Es posible que el vendedor ya haya vendido el par")
                return {
                    "reversed": False,
                    "reason": "pair_not_available",
                    "message": "El par ya no está disponible (posiblemente vendido)"
                }
            
            pair_qty_before = pair_inventory.quantity
            logger.info(f"   Par encontrado: quantity={pair_qty_before}")
            
            # ==================== REVERTIR: RESTAR DEL PAR ====================
            pair_inventory.quantity -= 1
            pair_inventory.updated_at = datetime.now()
            
            logger.info(f"   ✅ Par decrementado: {pair_qty_before} → {pair_inventory.quantity}")
            
            # ==================== BUSCAR/CREAR PIE IZQUIERDO ====================
            left_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == return_transfer.size,
                    ProductSize.location_name == vendor_location.name,
                    ProductSize.inventory_type == 'left_only',
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            if left_foot:
                left_before = left_foot.quantity
                left_foot.quantity += 1
                left_foot.updated_at = datetime.now()
                logger.info(f"   ✅ Pie izquierdo incrementado: {left_before} → {left_foot.quantity}")
            else:
                left_foot = ProductSize(
                    product_id=product.id,
                    size=return_transfer.size,
                    quantity=1,
                    inventory_type='left_only',
                    location_name=vendor_location.name,
                    company_id=self.company_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(left_foot)
                logger.info(f"   ✅ Pie izquierdo creado: quantity=1")
            
            # ==================== BUSCAR/CREAR PIE DERECHO ====================
            right_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == return_transfer.size,
                    ProductSize.location_name == vendor_location.name,
                    ProductSize.inventory_type == 'right_only',
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            if right_foot:
                right_before = right_foot.quantity
                right_foot.quantity += 1
                right_foot.updated_at = datetime.now()
                logger.info(f"   ✅ Pie derecho incrementado: {right_before} → {right_foot.quantity}")
            else:
                right_foot = ProductSize(
                    product_id=product.id,
                    size=return_transfer.size,
                    quantity=1,
                    inventory_type='right_only',
                    location_name=vendor_location.name,
                    company_id=self.company_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(right_foot)
                logger.info(f"   ✅ Pie derecho creado: quantity=1")
            
            # ==================== REGISTRAR EN HISTORIAL ====================
            from app.shared.database.models import InventoryChange
            
            reversal_change = InventoryChange(
                product_id=product.id,
                change_type='pair_reversal_for_return',
                size=return_transfer.size,
                quantity_before=pair_qty_before,
                quantity_after=pair_inventory.quantity,
                user_id=warehouse_keeper_id,
                reference_id=return_transfer.id,
                company_id=self.company_id,
                notes=(
                    f"REVERSIÓN DE PAR AUTO-FORMADO\n"
                    f"Return Transfer: #{return_transfer.id}\n"
                    f"Original Transfer: #{original_transfer.id}\n"
                    f"Ubicación: {vendor_location.name}\n"
                    f"Par → Pies individuales:\n"
                    f"  - pair: {pair_qty_before} → {pair_inventory.quantity}\n"
                    f"  - left_only: {left_foot.quantity - 1} → {left_foot.quantity}\n"
                    f"  - right_only: {right_foot.quantity - 1} → {right_foot.quantity}\n"
                    f"Razón: Preparar devolución de {return_transfer.inventory_type}"
                ),
                created_at=datetime.now()
            )
            self.db.add(reversal_change)
            
            # ==================== COMMIT ====================
            self.db.commit()
            
            logger.info(f"🎉 ¡REVERSIÓN COMPLETADA EXITOSAMENTE!")
            logger.info(f"   Par separado en pies individuales")
            logger.info(f"   Ahora se puede procesar la devolución del pie {return_transfer.inventory_type}")
            
            return {
                "reversed": True,
                "reason": "pair_reversed_successfully",
                "message": "Par revertido a pies individuales para procesar devolución",
                "location": vendor_location.name,
                "details": {
                    "pair_before": pair_qty_before,
                    "pair_after": pair_inventory.quantity,
                    "left_only": left_foot.quantity,
                    "right_only": right_foot.quantity
                }
            }
            
        except Exception as e:
            logger.exception(f"❌ Error revirtiendo par: {str(e)}")
            self.db.rollback()
            raise ValueError(f"Error al revertir par: {str(e)}")


    # app/modules/transfers_new/service.py

    def _generate_return_workflow_steps(
        self,
        pickup_type: str,
        destination_type: str
    ) -> List[str]:
        """
        Generar pasos del workflow de devolución
        
        Args:
            pickup_type: 'corredor' o 'vendedor'
            destination_type: Tipo de ubicación destino (generalmente 'bodega')
        
        Returns:
            List[str]: Lista de pasos del workflow
        """
        
        if pickup_type == 'vendedor':
            return [
                "1. Bodeguero aceptará la solicitud de devolución",
                "2. Llevarás el producto personalmente a bodega",
                "3. Bodeguero verificará el producto",
                "4. Bodeguero confirmará la recepción",
                "5. Inventario se restaurará en bodega automáticamente"
            ]
        else:
            return [
                "1. Bodeguero aceptará la solicitud de devolución",
                "2. Se asignará un corredor para la recogida",
                "3. Corredor recogerá el producto en tu ubicación",
                "4. Corredor transportará a bodega",
                "5. Bodeguero verificará y confirmará recepción",
                "6. Inventario se restaurará en bodega automáticamente"
            ]