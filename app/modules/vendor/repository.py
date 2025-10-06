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
                func.date(TransferRequest.delivered_at) == today
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