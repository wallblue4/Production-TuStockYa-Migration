# app/modules/vendor/service.py
from typing import Dict, Any , Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging
from fastapi import HTTPException
from sqlalchemy import and_

from .repository import VendorRepository
from .schemas import VendorDashboardResponse, TransferSummaryResponse, CompletedTransfersResponse
from app.shared.database.models import (
    TransferRequest, User, Location, Product, ProductSize, InventoryChange
)

logger = logging.getLogger(__name__)

class VendorService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = VendorRepository(db)
    
    async def get_dashboard(self, user_id: int, user_info: Dict[str, Any]) -> VendorDashboardResponse:
        """Dashboard completo del vendedor - igual estructura que backend antiguo"""
        
        # Obtener todos los datos necesarios
        sales_today = self.repository.get_sales_summary_today(user_id, self.company_id)
        payment_methods = self.repository.get_payment_methods_breakdown_today(user_id, self.company_id)
        expenses_today = self.repository.get_expenses_summary_today(user_id, self.company_id)
        transfer_stats = self.repository.get_transfer_requests_stats(user_id, self.company_id)
        discount_stats = self.repository.get_discount_requests_stats(user_id, self.company_id)
        unread_returns = self.repository.get_unread_return_notifications(user_id, self.company_id)
        
        # Calcular ingreso neto
        net_income = sales_today['confirmed_amount'] - expenses_today['total']
        
        # Estructura exacta como el backend antiguo
        return VendorDashboardResponse(
            success=True,
            message="Dashboard del vendedor",
            dashboard_timestamp=datetime.now(),
            vendor_info={
                "name": f"{user_info['first_name']} {user_info['last_name']}",
                "email": user_info['email'],
                "role": user_info['role'],
                "location_id": user_info['location_id'],
                "location_name": f"Local #{user_info['location_id']}"
            },
            today_summary={
                "date": datetime.now().date().isoformat(),
                "sales": {
                    "total_count": sales_today['total_sales'],
                    "confirmed_amount": sales_today['confirmed_amount'],
                    "pending_amount": sales_today['pending_amount'],
                    "pending_confirmations": sales_today['pending_confirmations'],
                    "total_amount": sales_today['confirmed_amount'] + sales_today['pending_amount']
                },
                "payment_methods_breakdown": payment_methods,
                "expenses": {
                    "count": expenses_today['count'],
                    "total_amount": expenses_today['total']
                },
                "net_income": net_income
            },
            pending_actions={
                "sale_confirmations": sales_today['pending_confirmations'],
                "transfer_requests": {
                    "pending": transfer_stats['pending'],
                    "in_transit": transfer_stats['in_transit'],
                    "delivered": transfer_stats['delivered']
                },
                "discount_requests": {
                    "pending": discount_stats['pending'],
                    "approved": discount_stats['approved'],
                    "rejected": discount_stats['rejected']
                },
                "return_notifications": unread_returns
            },
            quick_actions=[
                "Escanear nuevo tenis",
                "Registrar venta",
                "Registrar gasto",
                "Solicitar transferencia",
                "Ver ventas del día",
                "Ver gastos del día"
            ]
        )
    
    async def get_pending_transfers(self, user_id: int) -> TransferSummaryResponse:
        """Obtener transferencias pendientes para el vendedor"""
        pending_transfers = self.repository.get_pending_transfers_for_vendor(user_id, self.company_id)
        
        # Contar por urgencia
        urgent_count = len([t for t in pending_transfers if t['priority'] == 'high'])
        normal_count = len([t for t in pending_transfers if t['priority'] == 'normal'])
        
        return TransferSummaryResponse(
            success=True,
            message="Transferencias pendientes de confirmación",
            pending_transfers=pending_transfers,
            urgent_count=urgent_count,
            normal_count=normal_count,
            total_pending=len(pending_transfers),
            summary={
                "total_transfers": len(pending_transfers),
                "requiring_confirmation": len(pending_transfers),
                "urgent_items": urgent_count,
                "normal_items": normal_count
            },
            attention_needed=[
                transfer for transfer in pending_transfers 
                if transfer['priority'] == 'high'
            ]
        )
    
    async def get_completed_transfers(self, user_id: int) -> CompletedTransfersResponse:
        """Obtener transferencias completadas del día"""
        completed_transfers = self.repository.get_completed_transfers_today(user_id, self.company_id)
        
        # Calcular estadísticas del día
        total_transfers = len(completed_transfers)
        completed_count = len([t for t in completed_transfers if t['status'] == 'completed'])
        cancelled_count = len([t for t in completed_transfers if t['status'] == 'cancelled'])
        success_rate = (completed_count / total_transfers * 100) if total_transfers > 0 else 0
        
        return CompletedTransfersResponse(
            success=True,
            message="Transferencias completadas del día",
            date=datetime.now().date().isoformat(),
            completed_transfers=completed_transfers,
            today_stats={
                "total_transfers": total_transfers,
                "completed": completed_count,
                "cancelled": cancelled_count,
                "success_rate": round(success_rate, 1),
                "average_duration": "2.3h",  # Calcular real si es necesario
                "performance": "Buena" if success_rate >= 80 else "Regular"
            }
        )
    
    async def get_my_pickup_assignments(self, vendor_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtener asignaciones de pickup para el vendedor (self-pickup)
        """
        assignments = self.repository.get_vendor_pickup_assignments(vendor_id, self.company_id)
        
        # Calcular estadísticas
        ready_to_pickup = len([a for a in assignments if a['status'] == 'accepted'])
        in_transit = len([a for a in assignments if a['status'] == 'in_transit'])
        
        return {
            "success": True,
            "message": "Productos que debes recoger personalmente en bodega",
            "pickup_assignments": assignments,
            "count": len(assignments),
            "ready_to_pickup": ready_to_pickup,
            "in_transit": in_transit,
            "vendor_info": {
                "name": f"{user_info['first_name']} {user_info['last_name']}",
                "vendor_id": vendor_id,
                "acting_as": "recolector"
            }
        }

    async def deliver_return_to_warehouse(
        self,
        return_id: int,
        delivery_notes: str,
        vendor_id: int
    ) -> Dict[str, Any]:
        """Confirmar que vendedor entregó return en bodega"""
        
        try:
            logger.info(f"🚶 Vendedor confirma entrega - Return #{return_id}")
            
            result = self.repository.deliver_return_to_warehouse(
                return_id,
                delivery_notes,
                vendor_id,
                self.company_id
            )
            
            return result
            
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(500, detail=str(e))


    async def confirm_reception(
        self,
        request_id: int,
        received_quantity: int,
        condition_ok: bool,
        notes: Optional[str],
        vendor_id: int
    ) -> Dict[str, Any]:
        """
        VE004: Confirmar recepción de transferencia con AUTO-FORMACIÓN de pares
        
        Flujo:
        1. Validar que vendedor sea quien solicitó
        2. Sumar al inventario del vendedor (según inventory_type)
        3. Si es pie individual + existe pie opuesto → FORMAR PAR
        4. Actualizar estado a 'completed'
        5. Retornar estado del inventario y si puede vender
        """
        
        # Rollback preventivo
        try:
            self.db.rollback()
        except:
            pass
        
        try:
            logger.info(f"📦 Vendedor {vendor_id} confirmando recepción de transfer #{request_id}")
            
            # ==================== VALIDACIONES ====================
            
            # 1. Buscar transferencia
            transfer = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.id == request_id,
                    TransferRequest.company_id == self.company_id
                )
            ).first()
            
            if not transfer:
                raise HTTPException(404, "Transferencia no encontrada")
            
            logger.info(f"   Transferencia encontrada: {transfer.sneaker_reference_code}")
            
            # 2. VALIDAR que el vendedor sea quien solicitó
            if transfer.requester_id != vendor_id:
                raise HTTPException(
                    403,
                    "Solo el vendedor que solicitó la transferencia puede confirmar la recepción"
                )
            
            # 3. VALIDAR estado
            if transfer.status != 'delivered':
                raise HTTPException(
                    400,
                    f"Transferencia debe estar en estado 'delivered' (actual: {transfer.status})"
                )
            
            # 4. Obtener información del vendedor y su ubicación
            vendor = self.db.query(User).filter(
                and_(
                    User.id == vendor_id,
                    User.company_id == self.company_id
                )
            ).first()
            
            if not vendor:
                raise HTTPException(404, "Vendedor no encontrado")
            
            vendor_location = self.db.query(Location).filter(
                and_(
                    Location.id == vendor.location_id,
                    Location.company_id == self.company_id
                )
            ).first()
            
            if not vendor_location:
                raise HTTPException(404, "Ubicación del vendedor no encontrada")
            
            # 5. Validar que la transferencia sea para la ubicación del vendedor
            if transfer.destination_location_id != vendor.location_id:
                raise HTTPException(
                    400,
                    f"Esta transferencia no está destinada a tu ubicación"
                )
            
            logger.info(f"   ✅ Vendedor: {vendor.email}")
            logger.info(f"   ✅ Ubicación: {vendor_location.name}")
            logger.info(f"   ✅ Cantidad recibida: {received_quantity}")
            logger.info(f"   ✅ Tipo inventario: {transfer.inventory_type or 'pair'}")
            logger.info(f"   ✅ Condición OK: {condition_ok}")
            
            # ==================== ACTUALIZAR INVENTARIO ====================
            pair_formation_result = None
            product = None
            
            if condition_ok:
                logger.info("📊 Actualizando inventario del vendedor...")
                
                # Buscar producto
                product = self.db.query(Product).filter(
                    and_(
                        Product.reference_code == transfer.sneaker_reference_code,
                        Product.company_id == self.company_id
                    )
                ).first()
                
                if not product:
                    raise HTTPException(404, f"Producto {transfer.sneaker_reference_code} no encontrado")
                
                # ✅ SUMAR AL INVENTARIO DEL VENDEDOR (según inventory_type recibido)
                inventory_update_result = self._update_vendor_inventory(
                    product=product,
                    size=transfer.size,
                    inventory_type=transfer.inventory_type or 'pair',
                    quantity=received_quantity,
                    location_name=vendor_location.name,
                    user_id=vendor_id,
                    transfer_id=request_id,
                    notes=notes or ''
                )
                
                logger.info(f"   ✅ Inventario actualizado: {inventory_update_result}")
            
            # ==================== ACTUALIZAR ESTADO DE TRANSFERENCIA ====================
            transfer.status = 'completed'
            transfer.confirmed_reception_at = datetime.now()
            transfer.received_quantity = received_quantity
            transfer.reception_notes = notes or 'Recibido correctamente'
            
            # Commit antes de intentar formar pares
            self.db.commit()
            
            logger.info(f"✅ Transferencia completada - Estado actualizado")
            
            # ==================== AUTO-FORMACIÓN DE PARES ====================
            if transfer.inventory_type in ['left_only', 'right_only'] and condition_ok:
                logger.info("🔍 Verificando posibilidad de formar pares automáticamente...")
                
                try:
                    pair_formation_result = await self._attempt_pair_formation(
                        product=product,
                        size=transfer.size,
                        received_type=transfer.inventory_type,
                        received_quantity=received_quantity,
                        location_name=vendor_location.name,
                        vendor_id=vendor_id,
                        transfer_id=request_id
                    )
                    
                    if pair_formation_result and pair_formation_result.get('formed'):
                        logger.info(f"🎉 ¡ÉXITO! {pair_formation_result['quantity_formed']} par(es) formado(s)")
                    else:
                        logger.info(f"ℹ️ No se formó par: {pair_formation_result.get('reason', 'Pie opuesto no disponible')}")
                        
                except Exception as e:
                    logger.error(f"⚠️ Error en auto-formación: {str(e)}")
                    pair_formation_result = {
                        "formed": False,
                        "error": str(e)
                    }
            
            # ==================== OBTENER ESTADO FINAL DEL INVENTARIO ====================
            inventory_summary = self._get_vendor_inventory_summary(
                product_id=product.id if product else None,
                size=transfer.size,
                location_name=vendor_location.name
            )
            
            # ==================== DETERMINAR SI PUEDE VENDER ====================
            can_sell = inventory_summary['can_sell_pairs'] > 0
            
            # ==================== CONSTRUIR RESPUESTA ====================
            response = {
                "success": True,
                "message": self._generate_reception_message(
                    inventory_type=transfer.inventory_type or 'pair',
                    pair_formed=pair_formation_result.get('formed', False) if pair_formation_result else False,
                    can_sell=can_sell
                ),
                "timestamp": datetime.now().isoformat(),
                "transfer_id": transfer.id,
                "received_quantity": received_quantity,
                "inventory_type": transfer.inventory_type or 'pair',
                "inventory_updated": condition_ok,
                "confirmed_at": transfer.confirmed_reception_at.isoformat(),
                
                # Estado del inventario
                "your_inventory": inventory_summary,
                
                # Información de venta
                "can_sell": can_sell,
                "available_to_sell": inventory_summary['can_sell_pairs'],
                
                # Producto info
                "product_info": {
                    "reference_code": transfer.sneaker_reference_code,
                    "brand": transfer.brand,
                    "model": transfer.model,
                    "size": transfer.size
                }
            }
            
            # Agregar info de formación si aplica
            if pair_formation_result:
                response["pair_formation"] = pair_formation_result
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"❌ Error confirmando recepción: {str(e)}")
            try:
                self.db.rollback()
            except:
                pass
            raise HTTPException(500, f"Error: {str(e)}")
    
    
    def _update_vendor_inventory(
        self,
        product: Product,
        size: str,
        inventory_type: str,
        quantity: int,
        location_name: str,
        user_id: int,
        transfer_id: int,
        notes: str
    ) -> Dict[str, Any]:
        """
        Actualizar inventario del vendedor sumando la cantidad recibida
        
        Returns:
            Dict con información del cambio de inventario
        """
        
        logger.info(f"   📝 Sumando {quantity} unidad(es) de tipo '{inventory_type}'")
        
        # Buscar o crear ProductSize
        product_size = self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product.id,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                ProductSize.inventory_type == inventory_type,
                ProductSize.company_id == self.company_id
            )
        ).first()
        
        quantity_before = 0
        
        if product_size:
            # Ya existe - sumar cantidad
            quantity_before = product_size.quantity
            product_size.quantity += quantity
            product_size.updated_at = datetime.now()
            logger.info(f"   ✅ Stock actualizado: {quantity_before} → {product_size.quantity}")
        else:
            # No existe - crear nuevo
            product_size = ProductSize(
                product_id=product.id,
                size=size,
                quantity=quantity,
                quantity_exhibition=0,
                inventory_type=inventory_type,
                location_name=location_name,
                company_id=self.company_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            self.db.add(product_size)
            logger.info(f"   ✅ Nuevo ProductSize creado: {inventory_type} qty={quantity}")
        
        quantity_after = product_size.quantity
        
        # Registrar cambio en historial
        inventory_change = InventoryChange(
            product_id=product.id,
            change_type='transfer_reception',
            size=size,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            user_id=user_id,
            reference_id=transfer_id,
            notes=f"Recepción vendedor - Transfer #{transfer_id} - Tipo: {inventory_type} - {notes}",
            created_at=datetime.now(),
            company_id=self.company_id
        )
        self.db.add(inventory_change)
        
        return {
            "quantity_before": quantity_before,
            "quantity_after": quantity_after,
            "inventory_type": inventory_type
        }
    
    
    async def _attempt_pair_formation(
        self,
        product: Product,
        size: str,
        received_type: str,
        received_quantity: int,
        location_name: str,
        vendor_id: int,
        transfer_id: int
    ) -> Dict[str, Any]:
        """
        Intentar formar pares automáticamente cuando el vendedor recibe un pie individual
        
        Condiciones para formar par:
        1. Se recibió un pie individual (left_only o right_only)
        2. El vendedor YA TIENE el pie opuesto en su local
        3. Hay cantidad suficiente de ambos pies
        
        Returns:
            Dict con resultado de la formación
        """
        
        try:
            # Determinar qué pie llegó y cuál buscar
            opposite_type = 'right_only' if received_type == 'left_only' else 'left_only'
            
            logger.info(f"   🔍 Pie recibido: {received_type}")
            logger.info(f"   🔍 Buscando pie opuesto: {opposite_type}")
            
            # ✅ BUSCAR PIE OPUESTO EN EL LOCAL DEL VENDEDOR
            opposite_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == opposite_type,
                    ProductSize.quantity > 0,
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            if not opposite_foot:
                logger.info(f"   ℹ️ NO tienes pie opuesto '{opposite_type}' en tu local")
                return {
                    "formed": False,
                    "reason": f"No tienes pie {opposite_type} disponible en tu local. El pie {received_type} quedó en inventario esperando su par.",
                    "waiting_for": opposite_type,
                    "action_required": f"Solicita {opposite_type} para completar el par"
                }
            
            logger.info(f"   ✅ ¡SÍ tienes pie opuesto! Cantidad disponible: {opposite_foot.quantity}")
            
            # Calcular cuántos pares se pueden formar
            pairs_to_form = min(received_quantity, opposite_foot.quantity)
            
            if pairs_to_form == 0:
                return {
                    "formed": False,
                    "reason": "Cantidades insuficientes para formar par"
                }
            
            logger.info(f"   🎯 Se pueden formar {pairs_to_form} par(es)")
            logger.info(f"   🔧 Iniciando proceso de formación...")
            
            # ✅ BUSCAR O CREAR ProductSize PARA 'pair'
            pair_product_size = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == 'pair',
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            pairs_before = 0
            
            if pair_product_size:
                # Ya existen pares - sumar
                pairs_before = pair_product_size.quantity
                pair_product_size.quantity += pairs_to_form
                pair_product_size.updated_at = datetime.now()
                logger.info(f"   ✅ Pares en tu local: {pairs_before} → {pair_product_size.quantity}")
            else:
                # No existen pares - crear
                pair_product_size = ProductSize(
                    product_id=product.id,
                    size=size,
                    quantity=pairs_to_form,
                    quantity_exhibition=0,
                    inventory_type='pair',
                    location_name=location_name,
                    company_id=self.company_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(pair_product_size)
                logger.info(f"   ✅ Nuevos pares creados: {pairs_to_form}")
            
            # ✅ DESCONTAR PIES INDIVIDUALES
            
            # Descontar pie recibido
            received_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == received_type,
                    ProductSize.company_id == self.company_id
                )
            ).with_for_update().first()
            
            received_remaining = 0
            if received_foot:
                received_before = received_foot.quantity
                received_foot.quantity -= pairs_to_form
                received_foot.updated_at = datetime.now()
                received_remaining = received_foot.quantity
                logger.info(f"   ✅ Descontado {received_type}: {received_before} → {received_remaining}")
            
            # Descontar pie opuesto
            opposite_before = opposite_foot.quantity
            opposite_foot.quantity -= pairs_to_form
            opposite_foot.updated_at = datetime.now()
            opposite_remaining = opposite_foot.quantity
            logger.info(f"   ✅ Descontado {opposite_type}: {opposite_before} → {opposite_remaining}")
            
            # ✅ REGISTRAR CAMBIO EN HISTORIAL
            inventory_change = InventoryChange(
                product_id=product.id,
                change_type='pair_formation',
                size=size,
                quantity_before=pairs_before,
                quantity_after=pairs_before + pairs_to_form,
                user_id=vendor_id,
                reference_id=transfer_id,
                notes=f"Auto-formación en local vendedor: {pairs_to_form} par(es) formado(s) de {received_type} + {opposite_type}",
                created_at=datetime.now(),
                company_id=self.company_id
            )
            self.db.add(inventory_change)
            
            # ✅ COMMIT
            self.db.commit()
            
            logger.info(f"🎉 ¡AUTO-FORMACIÓN COMPLETADA EXITOSAMENTE!")
            logger.info(f"   📦 {pairs_to_form} par(es) formado(s)")
            logger.info(f"   👟 Pies restantes: {received_type}={received_remaining}, {opposite_type}={opposite_remaining}")
            
            return {
                "formed": True,
                "quantity_formed": pairs_to_form,
                "pairs_before": pairs_before,
                "pairs_after": pairs_before + pairs_to_form,
                "remaining_feet": {
                    received_type: received_remaining,
                    opposite_type: opposite_remaining
                },
                "can_sell_now": True,
                "message": f"✅ ¡Excelente! Se formaron {pairs_to_form} par(es) automáticamente. Ya puedes vender."
            }
            
        except Exception as e:
            logger.exception(f"❌ Error en auto-formación de pares: {str(e)}")
            try:
                self.db.rollback()
            except:
                pass
            return {
                "formed": False,
                "error": str(e)
            }
    
    
    def _get_vendor_inventory_summary(
        self,
        product_id: Optional[int],
        size: str,
        location_name: str
    ) -> Dict[str, Any]:
        """
        Obtener resumen del inventario del vendedor para una talla específica
        
        Returns:
            Dict con conteo de pares, pies izquierdos, pies derechos
        """
        
        if not product_id:
            return {
                "pairs": 0,
                "left_feet": 0,
                "right_feet": 0,
                "can_sell_pairs": 0,
                "total_shoes": 0
            }
        
        sizes = self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                ProductSize.company_id == self.company_id
            )
        ).all()
        
        summary = {
            "pairs": 0,
            "left_feet": 0,
            "right_feet": 0,
            "can_sell_pairs": 0,
            "total_shoes": 0
        }
        
        for ps in sizes:
            if ps.inventory_type == 'pair':
                summary['pairs'] = ps.quantity
                summary['can_sell_pairs'] = ps.quantity
                summary['total_shoes'] += ps.quantity * 2
            elif ps.inventory_type == 'left_only':
                summary['left_feet'] = ps.quantity
                summary['total_shoes'] += ps.quantity
            elif ps.inventory_type == 'right_only':
                summary['right_feet'] = ps.quantity
                summary['total_shoes'] += ps.quantity
        
        return summary
    
    
    def _generate_reception_message(
        self,
        inventory_type: str,
        pair_formed: bool,
        can_sell: bool
    ) -> str:
        """Generar mensaje apropiado según el resultado de la recepción"""
        
        if inventory_type == 'pair':
            return "✅ ¡Recepción confirmada! Pares completos agregados a tu inventario. Puedes vender ahora."
        
        elif pair_formed:
            return "🎉 ¡Excelente! Pie recibido y par formado automáticamente. Ya puedes vender."
        
        elif can_sell:
            return "✅ Recepción confirmada. Tienes pares disponibles para vender."
        
        else:
            foot_name = "izquierdo" if inventory_type == 'left_only' else "derecho"
            opposite_name = "derecho" if inventory_type == 'left_only' else "izquierdo"
            return f"⚠️ Pie {foot_name} recibido y guardado en inventario. Necesitas solicitar el pie {opposite_name} para completar el par y poder vender."
   
    async def sell_product_from_transfer(
        self,
        request_id: int,
        total_amount: float ,
        payment_methods: list,
        notes: str,
        seller_id: int,
        location_id: int,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Vender producto que fue recibido por transferencia
        """
        from app.modules.sales_new.service import SalesService
        from app.modules.sales_new.schemas import SaleCreateRequest, SaleItem, PaymentMethod
        from decimal import Decimal
        
        try:
            logger.info(f"🛍️ Iniciando venta desde transferencia #{request_id}")
            
            # 1. Obtener y validar transferencia
            transfer_validation = self.repository.validate_transfer_for_sale(
                request_id, 
                seller_id, 
                company_id
            )
            
            if not transfer_validation["valid"]:
                raise HTTPException(400, detail=transfer_validation["error"])
            
            transfer = transfer_validation["transfer"]
            
            # 2. Calcular precio unitario (total_amount / cantidad)
            quantity = transfer.received_quantity or transfer.quantity
            unit_price = Decimal(str(total_amount)) / Decimal(str(quantity))
            
            # 3. Preparar datos de venta
            sale_item = SaleItem(
                sneaker_reference_code=transfer.sneaker_reference_code,
                size=transfer.size,
                quantity=quantity,
                unit_price=unit_price
            )
            
            payment_methods_objs = [
                PaymentMethod(**pm) for pm in payment_methods
            ]
            
            sale_request = SaleCreateRequest(
                items=[sale_item],
                total_amount=Decimal(str(total_amount)),
                payment_methods=payment_methods_objs,
                notes=notes or f"Venta desde transferencia #{request_id}",
                requires_confirmation=False
            )
            
            # 4. Crear venta usando el servicio de sales
            sales_service = SalesService(self.db)
            sale_result = await sales_service.create_sale_complete(
                sale_data=sale_request,
                receipt_image=None,
                seller_id=seller_id,
                location_id=location_id,
                company_id=company_id
            )
            
            # 5. Actualizar status de transferencia a 'selled'
            self.repository.mark_transfer_as_selled(
                request_id,
                sale_result.sale_id,
                company_id
            )
            
            logger.info(f"✅ Venta #{sale_result.sale_id} creada - Transferencia #{request_id} marcada como 'selled'")
            
            return {
                "success": True,
                "message": "Venta registrada exitosamente",
                "transfer_id": request_id,
                "transfer_status": "selled",
                "sale_id": sale_result.sale_id,
                "total_amount": float(total_amount),
                "product_info": {
                    "reference_code": transfer.sneaker_reference_code,
                    "brand": transfer.brand,
                    "model": transfer.model,
                    "size": transfer.size,
                    "quantity": quantity
                },
                "inventory_updated": True
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error vendiendo producto desde transferencia")
            raise HTTPException(500, detail=f"Error procesando venta: {str(e)}")