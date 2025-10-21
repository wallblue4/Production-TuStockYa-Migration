# app/modules/warehouse_new/service.py
from typing import Dict, Any ,Optional ,Literal
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_
import logging

from .repository import WarehouseRepository
from .schemas import (
    WarehouseRequestAcceptance, CourierDelivery, 
    PendingRequestsResponse, AcceptedRequestsResponse, InventoryByLocationResponse ,VendorDelivery
)

from app.shared.schemas.inventory_distribution import PairFormationResult

from app.shared.database.models import TransferRequest , ProductSize , Location, Product

from app.modules.transfers_new.schemas import ReturnReceptionConfirmation

logger = logging.getLogger(__name__)

class WarehouseService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = WarehouseRepository(db)
    
    async def get_pending_requests(self, user_id: int, user_info: Dict[str, Any]) -> PendingRequestsResponse:
        """BG001: Obtener solicitudes pendientes para bodeguero"""
        requests = self.repository.get_pending_requests_for_warehouse(user_id, self.company_id)
        
        # Estadísticas como en backend antiguo
        breakdown = {
            "total": len(requests),
            "transfers": len([r for r in requests if r['request_type'] == 'transfer']),
            "returns": len([r for r in requests if r['request_type'] == 'return']),
            "urgent_returns": len([r for r in requests if r['request_type'] == 'return']),
            "high_priority": len([r for r in requests if r['urgent_action']])
        }
        
        return PendingRequestsResponse(
            success=True,
            message="Vista unificada: transferencias y devoluciones usan el mismo flujo de procesamiento",
            pending_requests=requests,
            count=len(requests),
            breakdown=breakdown,
            warehouse_keeper=f"{user_info['first_name']} {user_info['last_name']}"
        )
    
    async def accept_request(self, acceptance: WarehouseRequestAcceptance, warehouse_keeper_id: int) -> Dict[str, Any]:
        """BG002: Aceptar/rechazar solicitud de transferencia"""
        
        # Validar que la solicitud existe y está pendiente
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(status_code=403, detail="No tienes ubicaciones asignadas")
        
        acceptance_data = {
            'accepted': acceptance.accepted,
            'rejection_reason': acceptance.rejection_reason,
            'warehouse_notes': acceptance.warehouse_notes
        }
        
        success = self.repository.accept_transfer_request(
            acceptance.transfer_request_id, acceptance_data, warehouse_keeper_id, self.company_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada o no autorizada")
        
        return {
            "success": True,
            "message": "Solicitud aceptada - Disponible para corredores" if acceptance.accepted else "Solicitud rechazada",
            "request_id": acceptance.transfer_request_id,
            "status": "accepted" if acceptance.accepted else "rejected",
            "next_step": "Esperando asignación de corredor" if acceptance.accepted else "Solicitud finalizada"
        }
    
    async def get_accepted_requests(self, warehouse_keeper_id: int, user_info: Dict[str, Any]) -> AcceptedRequestsResponse:
        """BG002: Obtener solicitudes aceptadas y en preparación"""
        requests = self.repository.get_accepted_requests_by_warehouse_keeper(warehouse_keeper_id, self.company_id)
        
        return AcceptedRequestsResponse(
            success=True,
            message="Solicitudes aceptadas y en preparación y las devoluciones pendientes",
            accepted_requests=requests,
            count=len(requests),
            warehouse_info={
                "warehouse_keeper": f"{user_info['first_name']} {user_info['last_name']}",
                "location_assignments": len(self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id))
            }
        )
    
    # warehouse_new/service.py

    async def deliver_to_courier(
        self, 
        delivery: CourierDelivery, 
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """BG003: Entregar productos a corredor con todas las validaciones"""
        
        # Validar permisos del bodeguero
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(
                status_code=403, 
                detail="No tienes ubicaciones asignadas como bodeguero"
            )
        
        # Validar que la transferencia es de una ubicación gestionada
        transfer = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.id == delivery.transfer_request_id,
                TransferRequest.company_id == self.company_id
            )
        ).first()
        
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        
        if transfer.source_location_id not in location_ids:
            raise HTTPException(
                status_code=403, 
                detail=f"No tienes permisos para gestionar la ubicación origen (ID: {transfer.source_location_id})"
            )
        
        # Preparar datos
        delivery_data = {
            'courier_id': delivery.courier_id,
            'delivery_notes': delivery.delivery_notes
        }
        
        try:
            # Llamar al repository que hace toda la lógica
            result = self.repository.deliver_to_courier(
                delivery.transfer_request_id, 
                delivery_data,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Producto entregado a corredor - Inventario actualizado automáticamente",
                **result
            }
            
        except ValueError as e:
            # Re-lanzar errores de validación
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # Re-lanzar errores del sistema
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_inventory_by_location(self, location_id: int) -> InventoryByLocationResponse:
        """BG006: Consultar inventario disponible por ubicación"""
        inventory = self.repository.get_inventory_by_location(location_id, self.company_id)
        
        # Calcular resumen
        total_products = len(inventory)
        total_quantity = sum(item['quantity'] for item in inventory)
        total_value = sum(item['total_value'] for item in inventory)
        available_products = len([item for item in inventory if item['quantity'] > 0])
        
        return InventoryByLocationResponse(
            success=True,
            message=f"Inventario de Local #{location_id}",
            location_info={
                "location_id": location_id,
                "location_name": f"Local #{location_id}"
            },
            inventory=inventory,
            summary={
                "total_products": total_products,
                "available_products": available_products,
                "out_of_stock": total_products - available_products,
                "total_quantity": total_quantity,
                "total_value": total_value,
                "average_price": total_value / total_quantity if total_quantity > 0 else 0
            }
        )
    
    async def deliver_to_vendor(
        self, 
        transfer_id: int,
        delivery: VendorDelivery, 
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """
        Entregar producto directamente al vendedor (self-pickup)
        
        Validaciones:
        - Bodeguero tiene permisos para la ubicación origen
        - Transferencia es válida y tiene pickup_type = 'vendedor'
        - Stock disponible para entrega
        
        Proceso:
        - Descuento automático de inventario
        - Cambio de estado a 'in_transit'
        - Registro de timestamp
        """
        
        # Validar permisos del bodeguero
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(
                status_code=403, 
                detail="No tienes ubicaciones asignadas como bodeguero"
            )
        
        # Validar que la transferencia es de una ubicación gestionada
        transfer = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.id == transfer_id,
                TransferRequest.company_id == self.company_id
            )
        ).first()
        
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        
        if transfer.source_location_id not in location_ids:
            raise HTTPException(
                status_code=403, 
                detail=f"No tienes permisos para gestionar la ubicación origen (ID: {transfer.source_location_id})"
            )
        
        # Preparar datos para el repository
        delivery_data = {
            'delivered': delivery.delivered,
            'delivery_notes': delivery.delivery_notes or 'Entregado al vendedor para auto-recogida'
        }
        
        try:
            # Llamar al repository que hace toda la lógica
            result = self.repository.deliver_to_vendor(
                transfer_id, 
                delivery_data,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Producto entregado al vendedor - Inventario actualizado automáticamente",
                **result
            }
            
        except ValueError as e:
            # Re-lanzar errores de validación
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # Re-lanzar errores del sistema
            raise HTTPException(status_code=500, detail=str(e))

    # AGREGAR AL FINAL DE app/modules/warehouse_new/service.py

    async def confirm_return_reception(
        self,
        return_id: int,
        reception: ReturnReceptionConfirmation,
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """
        BG010: Confirmar recepción de devolución con RESTAURACIÓN de inventario
        
        Proceso:
        1. Validar que es un return (original_transfer_id != NULL)
        2. Validar permisos del bodeguero
        3. Verificar condición del producto
        4. SUMAR inventario en bodega (reversión)
        5. Marcar como completado
        6. Registrar en historial
        """
        
        try:
            logger.info(f"📦 Confirmando recepción de return #{return_id}")
            
            # Validar permisos
            managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
            location_ids = [loc['location_id'] for loc in managed_locations]
            
            if not location_ids:
                raise HTTPException(403, detail="No tienes ubicaciones asignadas")
            
            # Llamar al repository
            result = self.repository.confirm_return_reception(
                return_id,
                reception.dict(),
                warehouse_keeper_id,
                location_ids,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Devolución recibida - Inventario restaurado automáticamente",
                "return_id": result["return_id"],
                "original_transfer_id": result["original_transfer_id"],
                "received_quantity": result["received_quantity"],
                "product_condition": result["product_condition"],
                "inventory_restored": result["inventory_restored"],
                "warehouse_location": result["warehouse_location"],
                "inventory_change": result["inventory_change"]
            }
            
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(500, detail=str(e))

    async def confirm_delivery(
        self,
        confirmation: ReturnReceptionConfirmation,
        receiver_id: int
    ) -> Dict[str, Any]:
        """
        Confirmar recepción de transferencia
        ✅ MEJORADO: Ahora intenta formar pares automáticamente
        """
        
        transfer_id = confirmation.transfer_request_id
        received_quantity = confirmation.received_quantity
        condition_ok = confirmation.condition_ok
        notes = confirmation.notes
        
        try:
            # Validar que la solicitud existe y está en tránsito
            managed_location = self.repository.get_managed_location(receiver_id, self.company_id)
            
            transfer = self.repository.get_transfer_by_id(transfer_id, self.company_id)
            
            if not transfer:
                raise HTTPException(404, "Transferencia no encontrada")
            
            if transfer.status != "in_transit":
                raise HTTPException(
                    400, 
                    f"La transferencia debe estar 'in_transit'. Estado actual: {transfer.status}"
                )
            
            # Validar destino
            if transfer.destination_location_id != managed_location.id:
                raise HTTPException(403, "No autorizado para confirmar esta entrega")
            
            logger.info(f"📦 Confirmando recepción - Transfer ID: {transfer_id}")
            logger.info(f"   Cantidad recibida: {received_quantity}")
            logger.info(f"   Tipo inventario: {transfer.inventory_type}")
            
            # Actualizar estado de transferencia
            transfer.status = "completed"
            transfer.delivered_at = datetime.now()
            transfer.confirmed_reception_at = datetime.now()
            transfer.received_quantity = received_quantity
            transfer.reception_notes = notes
            
            # ✅ ACTUALIZAR INVENTARIO SEGÚN TIPO
            if condition_ok:
                logger.info("📊 Actualizando inventario...")
                
                product = self.db.query(Product).filter(
                    and_(
                        Product.reference_code == transfer.sneaker_reference_code,
                        Product.company_id == self.company_id
                    )
                ).first()
                
                if product:
                    # Buscar o crear ProductSize con el inventory_type correcto
                    product_size = self.db.query(ProductSize).filter(
                        and_(
                            ProductSize.product_id == product.id,
                            ProductSize.size == transfer.size,
                            ProductSize.location_name == managed_location.name,
                            ProductSize.inventory_type == transfer.inventory_type,  # ✅ FILTRAR POR TIPO
                            ProductSize.company_id == self.company_id
                        )
                    ).first()
                    
                    if product_size:
                        product_size.quantity += received_quantity
                        logger.info(f"   ✅ Inventario actualizado: +{received_quantity} {transfer.inventory_type}")
                    else:
                        # Crear nuevo ProductSize con el tipo correcto
                        product_size = ProductSize(
                            product_id=product.id,
                            size=transfer.size,
                            quantity=received_quantity,
                            inventory_type=transfer.inventory_type,  # ✅ TIPO CORRECTO
                            location_name=managed_location.name,
                            company_id=self.company_id
                        )
                        self.db.add(product_size)
                        logger.info(f"   ✅ Nuevo ProductSize creado: {received_quantity} {transfer.inventory_type}")
            
            self.db.commit()
            
            # ✅ NUEVO: INTENTAR AUTO-FORMACIÓN DE PARES
            pair_formation_result = None
            
            if transfer.inventory_type in ['left_only', 'right_only'] and condition_ok:
                logger.info("🔍 Verificando si se puede formar par automáticamente...")
                pair_formation_result = await self._attempt_pair_formation(
                    transfer=transfer,
                    receiver_id=receiver_id
                )
            
            logger.info("✅ Recepción confirmada - Inventario actualizado")
            
            return {
                "success": True,
                "message": "Recepción confirmada - Inventario actualizado automáticamente",
                "request_id": transfer_id,
                "received_quantity": received_quantity,
                "inventory_type": transfer.inventory_type,
                "inventory_updated": condition_ok,
                "confirmed_at": datetime.now().isoformat(),
                "pair_formation": pair_formation_result  # ✅ NUEVO
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("❌ Error confirmando recepción")
            raise HTTPException(
                status_code=500,
                detail=f"Error confirmando recepción: {str(e)}"
            )
    
    
    # ========== NUEVO MÉTODO: INTENTAR FORMACIÓN DE PAR ==========
    async def _attempt_pair_formation(
        self,
        transfer: TransferRequest,
        receiver_id: int
    ) -> Optional[PairFormationResult]:
        """
        🆕 Intentar formar par automáticamente al recibir un pie
        
        Proceso:
        1. Buscar pie opuesto en la misma ubicación
        2. Si existe, formar par automáticamente
        3. Actualizar inventarios
        4. Registrar en historial
        """
        
        try:
            logger.info(f"🔍 Buscando pie opuesto para auto-formación...")
            logger.info(f"   Producto: {transfer.sneaker_reference_code}")
            logger.info(f"   Talla: {transfer.size}")
            logger.info(f"   Pie recibido: {transfer.inventory_type}")
            
            # Buscar ubicación destino
            destination_location = self.db.query(Location).filter(
                Location.id == transfer.destination_location_id
            ).first()
            
            if not destination_location:
                logger.warning("❌ Ubicación destino no encontrada")
                return None
            
            # Buscar producto
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == transfer.sneaker_reference_code,
                    Product.company_id == self.company_id
                )
            ).first()
            
            if not product:
                logger.warning("❌ Producto no encontrado")
                return None
            
            # Determinar qué pie buscar
            opposite_type = 'right_only' if transfer.inventory_type == 'left_only' else 'left_only'
            
            # Buscar pie opuesto
            opposite_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == transfer.size,
                    ProductSize.location_name == destination_location.name,
                    ProductSize.inventory_type == opposite_type,
                    ProductSize.quantity > 0,
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            if not opposite_foot:
                logger.info(f"ℹ️ No se encontró pie opuesto ({opposite_type}) - no se puede formar par")
                return PairFormationResult(
                    formed=False,
                    location_name=destination_location.name,
                    quantity_formed=0
                )
            
            logger.info(f"✅ Pie opuesto encontrado: {opposite_foot.quantity} disponible(s)")
            
            # Calcular cuántos pares se pueden formar
            received_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == transfer.size,
                    ProductSize.location_name == destination_location.name,
                    ProductSize.inventory_type == transfer.inventory_type,
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            if not received_foot:
                logger.warning("❌ No se encontró el pie recibido en inventario")
                return None
            
            quantity_formable = min(received_foot.quantity, opposite_foot.quantity)
            
            if quantity_formable == 0:
                logger.info("ℹ️ No hay cantidad suficiente para formar pares")
                return PairFormationResult(
                    formed=False,
                    location_name=destination_location.name,
                    quantity_formed=0
                )
            
            logger.info(f"🎉 Formando {quantity_formable} par(es) automáticamente...")
            
            # Formar pares
            result = await self._form_pair_locally(
                product_id=product.id,
                size=transfer.size,
                location_name=destination_location.name,
                quantity=quantity_formable,
                left_foot=received_foot if transfer.inventory_type == 'left_only' else opposite_foot,
                right_foot=opposite_foot if transfer.inventory_type == 'left_only' else received_foot,
                transfer_id=transfer.id
            )
            
            return result
            
        except Exception as e:
            logger.exception(f"❌ Error intentando formar par: {str(e)}")
            return None
    
    
    # ========== NUEVO MÉTODO: FORMAR PAR LOCALMENTE ==========
    async def _form_pair_locally(
        self,
        product_id: int,
        size: str,
        location_name: str,
        quantity: int,
        left_foot: ProductSize,
        right_foot: ProductSize,
        transfer_id: Optional[int] = None
    ) -> PairFormationResult:
        """
        🆕 Formar pares desde pies individuales en la misma ubicación
        
        Proceso:
        1. Restar de left_only
        2. Restar de right_only
        3. Sumar/crear pair
        4. Registrar cambio en historial
        """
        
        try:
            logger.info(f"🔨 Formando {quantity} par(es)...")
            logger.info(f"   Izquierdos disponibles: {left_foot.quantity}")
            logger.info(f"   Derechos disponibles: {right_foot.quantity}")
            
            # Validar cantidades
            if left_foot.quantity < quantity or right_foot.quantity < quantity:
                raise ValueError(
                    f"Cantidades insuficientes para formar {quantity} par(es). "
                    f"Izq: {left_foot.quantity}, Der: {right_foot.quantity}"
                )
            
            # 1. Restar de pies individuales
            left_foot.quantity -= quantity
            right_foot.quantity -= quantity
            
            logger.info(f"   ✅ Restado de pies individuales")
            logger.info(f"      Izquierdos restantes: {left_foot.quantity}")
            logger.info(f"      Derechos restantes: {right_foot.quantity}")
            
            # 2. Buscar o crear ProductSize de tipo 'pair'
            pair = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product_id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == 'pair',
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            if pair:
                pair.quantity += quantity
                logger.info(f"   ✅ Pares actualizados: {pair.quantity}")
            else:
                pair = ProductSize(
                    product_id=product_id,
                    size=size,
                    quantity=quantity,
                    inventory_type='pair',
                    location_name=location_name,
                    company_id=self.company_id
                )
                self.db.add(pair)
                logger.info(f"   ✅ Nuevo ProductSize 'pair' creado: {quantity}")
            
            # 3. Registrar en historial
            from app.shared.database.models import InventoryChange
            
            change = InventoryChange(
                product_id=product_id,
                change_type='pair_formation',
                quantity_before=0,
                quantity_after=quantity,
                user_id=1,  # Sistema
                company_id=self.company_id,
                notes=f"Par formado automáticamente al recibir transfer {transfer_id}. "
                      f"Formados: {quantity} par(es) desde pies individuales en {location_name}"
            )
            self.db.add(change)
            
            self.db.commit()
            
            logger.info(f"🎉 ¡PAR FORMADO EXITOSAMENTE!")
            logger.info(f"   Cantidad: {quantity} par(es)")
            logger.info(f"   Ubicación: {location_name}")
            
            return PairFormationResult(
                formed=True,
                pair_product_size_id=pair.id,
                left_transfer_id=transfer_id if left_foot.inventory_type == 'left_only' else None,
                right_transfer_id=transfer_id if right_foot.inventory_type == 'right_only' else None,
                location_name=location_name,
                quantity_formed=quantity,
                remaining_left=left_foot.quantity,
                remaining_right=right_foot.quantity
            )
            
        except Exception as e:
            logger.exception(f"❌ Error formando par: {str(e)}")
            raise