from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Dict, Any, List, Optional
from datetime import datetime, date
from decimal import Decimal
from fastapi import HTTPException
import logging

from app.shared.database.models import (
    Sale, SaleItem, SalePayment, Product, ProductSize
)
from app.shared.services.inventory_service import InventoryService

logger = logging.getLogger(__name__)

class SalesRepository:
    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = InventoryService()
    
    def create_sale_atomic(
        self,
        sale_data: Dict[str, Any],
        seller_id: int,
        location_id: int,
        location_name: str,
        receipt_url: Optional[str] = None,
        company_id: Optional[int] = None
    ) -> Sale:
        """
        Crear venta con actualización de inventario en transacción atómica.
        
        Optimizaciones:
        - SELECT FOR UPDATE previene race conditions
        - Datos reales de BD, no del frontend
        - Bulk operations donde sea posible
        - Una sola transacción para todo
        
        Proceso:
        1. Reservar stock (bloqueo pesimista)
        2. Crear Sale
        3. Crear SaleItems (bulk)
        4. Crear SalePayments (bulk)
        5. Actualizar inventario (bulk)
        6. Commit único
        
        Returns:
            Sale: Venta creada con todas las relaciones
            
        Raises:
            HTTPException: Si stock insuficiente
            Exception: Si error en transacción
        """
        try:
            # PASO 1: Preparar items para validación
            inventory_items = [
                {
                    'sneaker_reference_code': item['sneaker_reference_code'],
                    'size': item['size'],
                    'quantity': item['quantity']
                }
                for item in sale_data['items']
            ]
            
            # PASO 2: VALIDAR Y RESERVAR stock (SELECT FOR UPDATE)
            logger.info(f"Reservando stock para {len(inventory_items)} items")
            reserved_products = self.inventory_service.validate_and_reserve_stock(
                self.db, inventory_items, location_name
            )
            logger.info(f"Stock reservado exitosamente")
            
            # PASO 3: CREAR VENTA
            sale = Sale(
                seller_id=seller_id,
                location_id=location_id,
                company_id=company_id,
                total_amount=Decimal(str(sale_data['total_amount'])),
                receipt_image=receipt_url,
                notes=sale_data.get('notes'),
                requires_confirmation=sale_data.get('requires_confirmation', False),
                confirmed=not sale_data.get('requires_confirmation', False),
                status='completed' if not sale_data.get('requires_confirmation', False) else 'pending_confirmation'
            )
            
            self.db.add(sale)
            self.db.flush()  # Obtener sale.id
            self.db.refresh(sale)
            
            if not sale.id:
                raise Exception("No se pudo obtener ID de venta")
            
            logger.info(f"Venta creada con ID: {sale.id}")
            
            # PASO 4: CREAR SALE_ITEMS con datos REALES de BD
            sale_items = []
            for item_data, (product_size, product) in zip(sale_data['items'], reserved_products):
                sale_item = SaleItem(
                    sale_id=sale.id,
                    company_id=company_id,
                    sneaker_reference_code=product.reference_code,  # De BD
                    brand=product.brand,                            # De BD
                    model=product.model,                            # De BD
                    color=product.color_info or '',                 # De BD
                    size=item_data['size'],
                    quantity=item_data['quantity'],
                    unit_price=Decimal(str(item_data['unit_price'])),
                    subtotal=Decimal(str(item_data['quantity'])) * Decimal(str(item_data['unit_price']))
                )
                sale_items.append(sale_item)

            
            # Bulk insert de items
            if sale_items:
                self.db.bulk_save_objects(sale_items)
            logger.info(f"{len(sale_items)} items agregados")
            
            # PASO 5: CREAR SALE_PAYMENTS
            sale_payments = []
            for payment_data in sale_data['payment_methods']:
                sale_payment = SalePayment(
                    sale_id=sale.id,
                    company_id=company_id,
                    payment_type=payment_data['type'],
                    amount=Decimal(str(payment_data['amount'])),
                    reference=payment_data.get('reference')
                )
                sale_payments.append(sale_payment)

            
            if sale_payments:
                self.db.bulk_save_objects(sale_payments)
            logger.info(f"{len(sale_data['payment_methods'])} métodos de pago agregados")
        
            # PASO 6: ACTUALIZAR INVENTARIO
            logger.info("Actualizando inventario")
            self.inventory_service.update_reserved_stock(
                self.db, reserved_products, inventory_items, seller_id, sale.id
            )
            logger.info("Inventario actualizado")
            
            # PASO 7: COMMIT ÚNICO
            self.db.commit()
            logger.info(f"Transacción completada - Venta #{sale.id}")
            
            # Refresh para obtener relaciones cargadas
            self.db.refresh(sale)
            
            return sale
            
        except HTTPException as e:
            logger.error(f"Error de negocio: {e.detail}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.exception("Error en transacción de venta")
            self.db.rollback()
            raise Exception(f"Error creando venta: {str(e)}")
    
    def get_sales_by_seller_and_date(self, seller_id: int, target_date: date, company_id: int) -> List[Sale]:
        """
        Obtener ventas por vendedor y fecha.
        
        Optimización: Query indexado por seller_id y date
        """
        return self.db.query(Sale).filter(
            and_(
                Sale.seller_id == seller_id,
                Sale.company_id == company_id,
                func.date(Sale.sale_date) == target_date
            )
        ).order_by(Sale.sale_date.desc()).all()
    
    def get_pending_confirmation_sales(self, seller_id: int, company_id: int) -> List[Sale]:
        """Obtener ventas pendientes de confirmación"""
        return self.db.query(Sale).filter(
            and_(
                Sale.seller_id == seller_id,
                Sale.company_id == company_id,
                Sale.requires_confirmation == True,
                Sale.confirmed == False
            )
        ).order_by(Sale.sale_date.desc()).all()
    
    def confirm_sale(self, sale_id: int, confirmed: bool, notes: str, user_id: int, company_id: int) -> bool:
        """Confirmar o rechazar una venta"""
        try:
            sale = self.db.query(Sale).filter(Sale.id == sale_id, Sale.company_id == company_id).first()
            if not sale:
                return False
            
            sale.confirmed = confirmed
            sale.confirmed_at = datetime.now()
            sale.status = 'completed' if confirmed else 'cancelled'
            
            if notes:
                current_notes = sale.notes or ""
                sale.notes = f"{current_notes}\nConfirmación: {notes}".strip()
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error confirmando venta: {e}")
            self.db.rollback()
            return False
    
    def get_sale_items(self, sale_id: int, company_id: int) -> List[SaleItem]:
        """Obtener items de una venta"""
        return self.db.query(SaleItem).filter(
            and_(
                SaleItem.sale_id == sale_id,
                SaleItem.company_id == company_id
            )
        ).all()
    
    def get_daily_sales_summary(self, seller_id: int, target_date: date, company_id: int) -> Dict[str, Any]:
        """
        Resumen de ventas del día.
        
        Optimización: Aggregate queries en vez de cargar todas las ventas
        """
        # Query agregado optimizado
        summary = self.db.query(
            func.count(Sale.id).label('total_sales'),
            func.sum(
                func.case(
                    (Sale.confirmed == True, Sale.total_amount),
                    else_=0
                )
            ).label('confirmed_amount'),
            func.sum(
                func.case(
                    (and_(Sale.confirmed == False, Sale.requires_confirmation == True), Sale.total_amount),
                    else_=0
                )
            ).label('pending_amount'),
            func.count(
                func.case(
                    (and_(Sale.confirmed == False, Sale.requires_confirmation == True), 1)
                )
            ).label('pending_confirmations')
        ).filter(
            and_(
                Sale.seller_id == seller_id,
                Sale.company_id == company_id,
                func.date(Sale.sale_date) == target_date
            )
        ).first()
        
        total_sales = summary.total_sales or 0
        confirmed_amount = float(summary.confirmed_amount or 0)
        pending_amount = float(summary.pending_amount or 0)
        pending_confirmations = summary.pending_confirmations or 0
        
        # Calcular ventas confirmadas
        confirmed_sales = total_sales - pending_confirmations
        
        return {
            "total_sales": total_sales,
            "confirmed_sales": confirmed_sales,
            "pending_sales": pending_confirmations,
            "total_amount": confirmed_amount,
            "pending_amount": pending_amount,
            "confirmed_amount": confirmed_amount,
            "average_sale": confirmed_amount / confirmed_sales if confirmed_sales > 0 else 0
        }