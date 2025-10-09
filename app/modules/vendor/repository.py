# app/modules/vendor/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, text ,case
from typing import List, Dict, Any
from datetime import date, datetime
from decimal import Decimal
import logging

from app.shared.database.models import (
    Sale, SalePayment, Expense, TransferRequest, DiscountRequest, 
    ReturnNotification, User , Location, Product
)

logger = logging.getLogger(__name__)

class VendorRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def get_sales_summary_today(self, user_id: int) -> Dict[str, Any]:
        """Obtener resumen de ventas del día - igual que backend antiguo"""
        today = date.today()
        
        # Query principal de ventas como en el backend antiguo
        result = self.db.query(
            func.count(Sale.id).label('total_sales'),
            func.coalesce(
                func.sum(
                    case(
                        (Sale.confirmed == True, Sale.total_amount),
                        else_=0
                    )
                ), 0
            ).label('confirmed_amount'),
            func.coalesce(
                func.sum(
                    case(
                        (and_(Sale.confirmed == False, Sale.requires_confirmation == True), Sale.total_amount),
                        else_=0
                    )
                ), 0
            ).label('pending_amount'),
            func.count(
                case(
                    (and_(Sale.confirmed == False, Sale.requires_confirmation == True), 1)
                )
            ).label('pending_confirmations')
        ).filter(
            and_(
                func.date(Sale.sale_date) == today,
                Sale.seller_id == user_id
            )
        ).first()
        
        return {
            'total_sales': result.total_sales,
            'confirmed_amount': float(result.confirmed_amount),
            'pending_amount': float(result.pending_amount),
            'pending_confirmations': result.pending_confirmations
        }
    
    def get_payment_methods_breakdown_today(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtener desglose de métodos de pago del día - igual que backend antiguo"""
        today = date.today()
        
        results = self.db.query(
            SalePayment.payment_type,
            func.sum(SalePayment.amount).label('total_amount'),
            func.count(SalePayment.id).label('count')
        ).join(Sale).filter(
            and_(
                func.date(Sale.sale_date) == today,
                Sale.seller_id == user_id,
                Sale.confirmed == True
            )
        ).group_by(SalePayment.payment_type).order_by(
            func.sum(SalePayment.amount).desc()
        ).all()
        
        return [
            {
                'payment_type': result.payment_type,
                'total_amount': float(result.total_amount),
                'count': result.count
            }
            for result in results
        ]
    
    def get_expenses_summary_today(self, user_id: int) -> Dict[str, Any]:
        """Obtener resumen de gastos del día - igual que backend antiguo"""
        today = date.today()
        
        result = self.db.query(
            func.count(Expense.id).label('count'),
            func.coalesce(func.sum(Expense.amount), 0).label('total')
        ).filter(
            and_(
                func.date(Expense.expense_date) == today,
                Expense.user_id == user_id
            )
        ).first()
        
        return {
            'count': result.count,
            'total': float(result.total)
        }
    
    def get_transfer_requests_stats(self, user_id: int) -> Dict[str, Any]:
        """Obtener estadísticas de solicitudes de transferencia - igual que backend antiguo"""
        result = self.db.query(
            func.count(
                case((TransferRequest.status == 'pending', 1))
            ).label('pending'),
            func.count(
                case((TransferRequest.status == 'in_transit', 1))
            ).label('in_transit'),
            func.count(
                case((TransferRequest.status == 'delivered', 1))
            ).label('delivered')
        ).filter(TransferRequest.requester_id == user_id).first()
        
        return {
            'pending': result.pending,
            'in_transit': result.in_transit,
            'delivered': result.delivered
        }
    
    def get_discount_requests_stats(self, user_id: int) -> Dict[str, Any]:
        """Obtener estadísticas de solicitudes de descuento - igual que backend antiguo"""
        result = self.db.query(
            func.count(
                case((DiscountRequest.status == 'pending', 1))
            ).label('pending'),
            func.count(
                case((DiscountRequest.status == 'approved', 1))
            ).label('approved'),
            func.count(
                case((DiscountRequest.status == 'rejected', 1))
            ).label('rejected')
        ).filter(DiscountRequest.seller_id == user_id).first()
        
        return {
            'pending': result.pending,
            'approved': result.approved,
            'rejected': result.rejected
        }
    
    def get_unread_return_notifications(self, user_id: int) -> int:
        """Obtener notificaciones de devolución no leídas - igual que backend antiguo"""
        count = self.db.query(func.count(ReturnNotification.id)).join(
            TransferRequest, ReturnNotification.transfer_request_id == TransferRequest.id
        ).filter(
            and_(
                TransferRequest.requester_id == user_id,
                ReturnNotification.read_by_requester == False
            )
        ).scalar()
        
        return count or 0
    
    def get_pending_transfers_for_vendor(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtener transferencias pendientes para el vendedor (recepciones por confirmar)"""
        # Transferencias en estado 'delivered' que requieren confirmación
        transfers = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.requester_id == user_id,
                TransferRequest.status != 'completed',
                TransferRequest.status != 'cancelled'
            )
        ).order_by(TransferRequest.requested_at.desc()).all()
        
        result = []
        for transfer in transfers:
            # Calcular tiempo transcurrido
            time_diff = datetime.now() - transfer.requested_at
            hours = int(time_diff.total_seconds() // 3600)
            minutes = int((time_diff.total_seconds() % 3600) // 60)
            time_elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            product_image = self._get_product_image(
            transfer.sneaker_reference_code,
            transfer.source_location_id
            )

            priority, next_action, action_required = self._get_transfer_status_info(
            transfer.status, 
            transfer.purpose,
            hours
            )

            result.append({
                'id': transfer.id,
                'status': transfer.status,
                'sneaker_reference_code': transfer.sneaker_reference_code,
                'brand': transfer.brand,
                'model': transfer.model,
                'size': transfer.size,
                'quantity': transfer.quantity,
                'purpose': transfer.purpose,
                'priority': 'high' if transfer.purpose == 'cliente' else 'normal',
                'requested_at': transfer.requested_at.isoformat(),
                'time_elapsed': time_elapsed,
                "pickup_type": transfer.pickup_type,
                'next_action': 'Confirmar recepción',
                'product_image': product_image,
                'courier_name': f"{transfer.courier.first_name} {transfer.courier.last_name}" if transfer.courier else None,
                'warehouse_keeper_name': (
                f"{transfer.warehouse_keeper.first_name} {transfer.warehouse_keeper.last_name}"
                if transfer.warehouse_keeper else None
            )
            })
        
        return result
    

    def _get_product_image(self, reference_code: str, source_location_id: int) -> str:
        """
        Obtener imagen del producto
        Busca primero en ubicación origen, luego global, finalmente placeholder
        """
        try:
            # Obtener nombre real de ubicación origen
            source_location = self.db.query(Location).filter(
                Location.id == source_location_id
            ).first()
            
            if not source_location:
                return self._get_placeholder_image(reference_code)
            
            # Buscar producto con imagen en ubicación origen
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == reference_code,
                    Product.location_name == source_location.name
                )
            ).first()
            
            # Si no existe o no tiene imagen, buscar global
            if not product or not product.image_url:
                product = self.db.query(Product).filter(
                    Product.reference_code == reference_code
                ).first()
            
            # Retornar imagen o placeholder
            if product and product.image_url:
                return product.image_url
            
            return self._get_placeholder_image(reference_code)
            
        except Exception as e:
            logger.exception(f"Error obteniendo imagen de producto {reference_code}")
            return self._get_placeholder_image(reference_code)


    def _get_placeholder_image(self, reference_code: str) -> str:
        """Generar URL de placeholder para producto sin imagen"""
        # Extraer marca del código de referencia
        brand = reference_code.split('-')[0] if '-' in reference_code else 'Product'
        return f"https://via.placeholder.com/300x200?text={brand}+{reference_code}"


    def _get_transfer_status_info(
        self, 
        status: str, 
        purpose: str, 
        hours_elapsed: int
    ) -> tuple:
        """
        Determinar prioridad y acción según estado de transferencia
        
        Returns:
            tuple: (priority, next_action, action_required)
        """
        
        # Prioridad base según propósito
        base_priority = 'high' if purpose == 'cliente' else 'normal'
        
        # Aumentar prioridad si lleva mucho tiempo
        if hours_elapsed >= 4:
            priority = 'critical'
        elif hours_elapsed >= 2 and base_priority == 'high':
            priority = 'critical'
        else:
            priority = base_priority
        
        # Siguiente acción según estado
        status_actions = {
            'pending': (
                'Esperando aceptación de bodeguero',
                'wait'  # El vendedor no puede hacer nada aquí
            ),
            'accepted': (
                'Bodeguero preparando producto',
                'wait'
            ),
            'courier_assigned': (
                'Corredor en camino a recoger',
                'wait'
            ),
            'in_transit': (
                'Producto en camino',
                'wait'
            ),
            'delivered': (
                'Confirmar recepción',
                'confirm'  # El vendedor DEBE actuar
            )
        }
        
        next_action, action_required = status_actions.get(
            status, 
            ('Estado desconocido', 'check')
        )
        
        return priority, next_action, action_required

    def get_completed_transfers_today(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtener transferencias completadas del día"""
        today = date.today()
        
        transfers = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.requester_id == user_id,
                TransferRequest.status.in_(['completed', 'cancelled']),
                func.date(TransferRequest.confirmed_reception_at) == today
            )
        ).order_by(TransferRequest.delivered_at.desc()).all()
        
        result = []
        for transfer in transfers:
            # Calcular duración total
            if transfer.delivered_at and transfer.requested_at:
                duration = transfer.delivered_at - transfer.requested_at
                hours = int(duration.total_seconds() // 3600)
                duration_str = f"{hours}h" if hours > 0 else f"{int(duration.total_seconds() // 60)}m"
            else:
                duration_str = "N/A"
            
            result.append({
                'id': transfer.id,
                'status': transfer.status,
                'sneaker_reference_code': transfer.sneaker_reference_code,
                'brand': transfer.brand,
                'model': transfer.model,
                'size': transfer.size,
                'quantity': transfer.quantity,
                'purpose': transfer.purpose,
                'priority': 'high' if transfer.purpose == 'cliente' else 'normal',
                'requested_at': transfer.requested_at.isoformat(),
                'completed_at': transfer.delivered_at.isoformat() if transfer.delivered_at else None,
                'duration': duration_str,
                'next_action': 'Completado' if transfer.status == 'completed' else 'Cancelado'
            })
        
        return result
    
    def get_vendor_pickup_assignments(self, vendor_id: int) -> List[Dict[str, Any]]:
        """
        Obtener transferencias que el vendedor debe recoger personalmente
        (pickup_type = 'vendedor')
        
        Estados válidos: 'accepted' (listo para recoger), 'in_transit' (en camino)
        """
        try:
            from app.shared.database.models import TransferRequest, Location, User
            from sqlalchemy import and_, or_
            from datetime import datetime
            
            logger.info(f"🚶 Obteniendo asignaciones de pickup para vendedor ID: {vendor_id}")
            
            # Query principal
            assignments = self.db.query(
                TransferRequest.id,
                TransferRequest.status,
                TransferRequest.sneaker_reference_code,
                TransferRequest.brand,
                TransferRequest.model,
                TransferRequest.size,
                TransferRequest.quantity,
                TransferRequest.purpose,
                TransferRequest.requested_at,
                TransferRequest.accepted_at,
                TransferRequest.notes,
                Location.name.label('source_location_name'),
                Location.address.label('source_address'),
                Location.phone.label('source_phone'),
                User.first_name.label('warehouse_keeper_first_name'),
                User.last_name.label('warehouse_keeper_last_name')
            ).join(
                Location, TransferRequest.source_location_id == Location.id
            ).outerjoin(
                User, TransferRequest.warehouse_keeper_id == User.id
            ).filter(
                and_(
                    TransferRequest.courier_id == vendor_id,
                    TransferRequest.pickup_type == 'vendedor',
                    or_(
                        TransferRequest.status == 'accepted',
                        TransferRequest.status == 'in_transit'
                    )
                )
            ).order_by(
                TransferRequest.accepted_at.asc()
            ).all()
            
            # Procesar resultados
            results = []
            for assignment in assignments:
                warehouse_keeper = f"{assignment.warehouse_keeper_first_name or ''} {assignment.warehouse_keeper_last_name or ''}".strip()
                
                # Calcular tiempo transcurrido
                time_elapsed = "Recién aceptada"
                if assignment.accepted_at:
                    delta = datetime.now() - assignment.accepted_at
                    hours = delta.total_seconds() / 3600
                    if hours < 1:
                        time_elapsed = f"{int(delta.total_seconds() / 60)} minutos"
                    elif hours < 24:
                        time_elapsed = f"{int(hours)} horas"
                    else:
                        time_elapsed = f"{int(hours / 24)} días"
                
                # Determinar acción según estado
                if assignment.status == 'accepted':
                    action_required = "ir_a_recoger"
                    action_description = f"Ve a {assignment.source_location_name} a recoger el producto"
                    urgency = "high" if assignment.purpose == 'cliente' else "medium"
                else:  # in_transit
                    action_required = "confirmar_llegada"
                    action_description = "Confirma que llegaste con el producto a tu local"
                    urgency = "medium"
                
                # Imagen del producto
                product_image = self._get_product_image_for_transfer(
                    assignment.sneaker_reference_code,
                    assignment.brand,
                    assignment.model
                )
                
                results.append({
                    'id': assignment.id,
                    'status': assignment.status,
                    'sneaker_reference_code': assignment.sneaker_reference_code,
                    'brand': assignment.brand,
                    'model': assignment.model,
                    'size': assignment.size,
                    'quantity': assignment.quantity,
                    'purpose': assignment.purpose,
                    'source_location_name': assignment.source_location_name,
                    'source_address': assignment.source_address or 'Dirección no disponible',
                    'source_phone': assignment.source_phone or 'Teléfono no disponible',
                    'warehouse_keeper_name': warehouse_keeper or 'Bodeguero',
                    'requested_at': assignment.requested_at.isoformat() if assignment.requested_at else None,
                    'accepted_at': assignment.accepted_at.isoformat() if assignment.accepted_at else None,
                    'time_elapsed': time_elapsed,
                    'action_required': action_required,
                    'action_description': action_description,
                    'contact_person': warehouse_keeper or 'Bodeguero',
                    'urgency': urgency,
                    'product_image': product_image,
                    'notes': assignment.notes
                })
            
            logger.info(f"✅ {len(results)} asignaciones de pickup encontradas")
            return results
            
        except Exception as e:
            logger.exception("❌ Error obteniendo asignaciones de pickup")
            return []

    def _get_product_image_for_transfer(self, reference_code: str, brand: str, model: str) -> str:
        """Obtener imagen del producto para transferencia"""
        try:
            from app.shared.database.models import Product
            
            # Buscar producto con imagen
            product = self.db.query(Product).filter(
                Product.reference_code == reference_code
            ).first()
            
            if product and product.image_url:
                return product.image_url
            
            # Placeholder si no hay imagen
            return f"https://via.placeholder.com/300x200?text={brand}+{model}"
            
        except Exception:
            return f"https://via.placeholder.com/300x200?text={brand}+{model}"

    # app/modules/vendor/repository.py

    def deliver_return_to_warehouse(
        self,
        return_id: int,
        delivery_notes: str,
        vendor_id: int
    ) -> Dict[str, Any]:
        """
        Vendedor confirma que entregó return personalmente en bodega
        
        IMPORTANTE: Este paso NO actualiza inventario
        Solo confirma que el vendedor llevó el producto
        El bodeguero debe validar y restaurar inventario (BG010)
        """
        
        try:
            logger.info(f"🚶 Procesando entrega de vendedor - Return #{return_id}")
            
            # ==================== VALIDACIÓN 1: OBTENER RETURN ====================
            return_transfer = self.db.query(TransferRequest).filter(
                TransferRequest.id == return_id
            ).first()
            
            if not return_transfer:
                raise ValueError(f"Return #{return_id} no encontrado")
            
            logger.info(f"✅ Return encontrado: {return_transfer.sneaker_reference_code}")
            
            # ==================== VALIDACIÓN 2: ES UN RETURN ====================
            if not return_transfer.original_transfer_id:
                raise ValueError("Esta transferencia no es una devolución")
            
            # ==================== VALIDACIÓN 3: ES EL VENDEDOR SOLICITANTE ====================
            if return_transfer.requester_id != vendor_id:
                raise ValueError("Solo el vendedor solicitante puede confirmar entrega")
            
            # ==================== VALIDACIÓN 4: PICKUP_TYPE = 'VENDEDOR' ====================
            if return_transfer.pickup_type != 'vendedor':
                raise ValueError(
                    f"Este return usa corredor (pickup_type: {return_transfer.pickup_type}). "
                    f"No puedes confirmar entrega personal."
                )
            
            logger.info(f"✅ Return con pickup_type = 'vendedor' confirmado")
            
            # ==================== VALIDACIÓN 5: ESTADO ====================
            if return_transfer.status != 'accepted':
                raise ValueError(
                    f"Return debe estar en estado 'accepted' (bodeguero ya aceptó). "
                    f"Estado actual: '{return_transfer.status}'"
                )
            
            logger.info(f"✅ Todas las validaciones pasaron")
            
            # ==================== OBTENER UBICACIÓN DESTINO ====================
            destination_location = self.db.query(Location).filter(
                Location.id == return_transfer.destination_location_id
            ).first()
            
            destination_location_name = destination_location.name if destination_location else "Bodega"
            
            # ==================== ACTUALIZAR RETURN A 'DELIVERED' ====================
            logger.info(f"📝 Actualizando return a estado 'delivered'")
            
            return_transfer.status = 'delivered'
            return_transfer.delivered_at = datetime.now()
            
            # Agregar notas de entrega del vendedor
            delivery_notes_text = (
                f"\n\n═══ ENTREGA PERSONAL VENDEDOR ═══\n"
                f"Vendedor ID: {vendor_id}\n"
                f"Fecha entrega: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Notas: {delivery_notes or 'Sin notas adicionales'}\n"
                f"Estado: Producto entregado en bodega\n"
                f"Pendiente: Validación por bodeguero\n"
                f"═══════════════════════════════════"
            )
            
            return_transfer.notes = (return_transfer.notes or '') + delivery_notes_text
            
            # ==================== COMMIT ====================
            self.db.commit()
            
            logger.info(f"✅ Entrega de vendedor confirmada - Estado: delivered")
            
            # ==================== RESPUESTA ====================
            return {
                "return_id": return_id,
                "original_transfer_id": return_transfer.original_transfer_id,
                "status": "delivered",
                "delivered_at": return_transfer.delivered_at.isoformat(),
                "pickup_type": "vendedor",
                "warehouse_location": destination_location_name,
                "product_info": {
                    "reference_code": return_transfer.sneaker_reference_code,
                    "brand": return_transfer.brand,
                    "model": return_transfer.model,
                    "size": return_transfer.size,
                    "quantity": return_transfer.quantity
                },
                "vendor_info": {
                    "vendor_id": vendor_id,
                    "delivery_notes": delivery_notes
                },
                "next_step": "Bodeguero debe confirmar recepción y restaurar inventario (BG010)",
                "pending_action": {
                    "who": "Bodeguero",
                    "what": "Verificar producto y confirmar recepción",
                    "endpoint": f"POST /warehouse/confirm-return-reception/{return_id}"
                }
            }
            
        except ValueError as e:
            logger.error(f"❌ Error validación: {e}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.exception("❌ Error confirmando entrega vendedor")
            self.db.rollback()
            raise RuntimeError(f"Error procesando entrega: {str(e)}")