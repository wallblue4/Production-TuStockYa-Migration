# app/modules/sales_new/service.py - VERSIÓN SIMPLIFICADA
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date , datetime
from decimal import Decimal
import logging

from .repository import SalesRepository
from .schemas import SaleCreateRequest, SaleResponse, DailySalesResponse
from app.shared.services.cloudinary_service import cloudinary_service
from app.shared.database.models import Location , Sale


logger = logging.getLogger(__name__)

class SalesService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = SalesRepository(db)
        self.cloudinary = cloudinary_service
    
    async def create_sale_complete(
        self,
        sale_data: SaleCreateRequest,
        receipt_image: Optional[UploadFile],
        seller_id: int,
        location_id: int
    ) -> SaleResponse:
        """
        Crear venta completa.
        
        Responsabilidades:
        - Validar ubicación
        - Subir recibo (no crítico)
        - Delegar transacción al repository
        - Construir respuesta
        """
        try:
            logger.info(f"Iniciando venta - Vendedor: {seller_id}, Location: {location_id}")
            
            # PASO 1: Obtener ubicación
            location = self.db.query(Location).filter(
                Location.id == location_id
            ).first()
            
            if not location:
                raise HTTPException(404, detail=f"Ubicación {location_id} no encontrada")
            
            logger.info(f"Ubicación: '{location.name}'")
            
            # PASO 2: Subir recibo (no crítico - no bloquea venta)
            receipt_url = await self._upload_receipt_safe(receipt_image, seller_id)
            
            # PASO 3: Crear venta (TRANSACCIÓN ATÓMICA en repository)
            try:
                sale = self.repository.create_sale_atomic(
                    sale_data=sale_data.dict(),
                    seller_id=seller_id,
                    location_id=location_id,
                    location_name=location.name,
                    receipt_url=receipt_url
                )
                
                logger.info(f"Venta {sale.id} completada exitosamente")
                
                return self._build_response(sale, sale_data, receipt_url)
                
            except Exception as e:
                # Si falla venta, limpiar imagen subida
                if receipt_url:
                    await self._delete_receipt_safe(receipt_url)
                raise
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error inesperado creando venta")
            raise HTTPException(500, detail=f"Error creando venta: {str(e)}")
    
    async def get_daily_sales(
        self, 
        seller_id: int, 
        target_date: date
    ) -> DailySalesResponse:
        """Obtener ventas del día con resumen"""
        sales = self.repository.get_sales_by_seller_and_date(seller_id, target_date)
        summary = self.repository.get_daily_sales_summary(seller_id, target_date)
        
        sales_data = [
            {
                "id": sale.id,
                "total_amount": float(sale.total_amount),
                "status": sale.status,
                "confirmed": sale.confirmed,
                "requires_confirmation": sale.requires_confirmation,
                "sale_date": sale.sale_date.isoformat(),
                "items_count": len(self.repository.get_sale_items(sale.id)),
                "notes": sale.notes,
                "receipt_image_url": sale.receipt_image
            }
            for sale in sales
        ]
        
        return DailySalesResponse(
            success=True,
            message=f"Ventas del {target_date}",
            date=target_date.isoformat(),
            sales=sales_data,
            summary=summary,
            seller_info={"seller_id": seller_id}
        )
    
    async def confirm_sale(
        self, 
        sale_id: int, 
        confirmed: bool, 
        confirmation_notes: str, 
        user_id: int
    ) -> dict:
        """Confirmar o rechazar una venta"""
        success = self.repository.confirm_sale(
            sale_id, confirmed, confirmation_notes, user_id
        )
        
        if not success:
            raise HTTPException(404, detail="Venta no encontrada")
        
        return {
            "success": True,
            "message": "Venta confirmada" if confirmed else "Venta rechazada",
            "sale_id": sale_id,
            "confirmed": confirmed,
            "confirmed_at": datetime.now().isoformat()
        }
    
    async def get_pending_confirmation_sales(self, seller_id: int) -> dict:
        """Obtener ventas pendientes de confirmación"""
        pending_sales = self.repository.get_pending_confirmation_sales(seller_id)
        
        sales_data = []
        total_pending = Decimal('0')
        
        for sale in pending_sales:
            items = self.repository.get_sale_items(sale.id)
            sales_data.append({
                "id": sale.id,
                "total_amount": float(sale.total_amount),
                "sale_date": sale.sale_date.isoformat(),
                "notes": sale.notes,
                "items_count": len(items)
            })
            total_pending += sale.total_amount
        
        return {
            "success": True,
            "pending_sales": sales_data,
            "count": len(sales_data),
            "total_pending_amount": float(total_pending)
        }
    
    # MÉTODOS PRIVADOS HELPERS
    
    async def _upload_receipt_safe(
        self, 
        receipt_image: Optional[UploadFile], 
        seller_id: int
    ) -> Optional[str]:
        """Subir recibo sin fallar la venta"""
        if not receipt_image or not receipt_image.filename:
            return None
        
        try:
            logger.info(f"Subiendo recibo: {receipt_image.filename}")
            url = await self.cloudinary.upload_receipt_image(
                receipt_image, "sale", seller_id
            )
            logger.info(f"Recibo subido: {url}")
            return url
        except Exception as e:
            logger.warning(f"Error subiendo recibo (continuando): {e}")
            return None
    
    async def _delete_receipt_safe(self, receipt_url: str) -> None:
        """Eliminar recibo sin fallar"""
        try:
            await self.cloudinary.delete_image(receipt_url)
            logger.info(f"Recibo eliminado: {receipt_url}")
        except Exception as e:
            logger.warning(f"Error eliminando recibo: {e}")
    
    def _build_response(
        self, 
        sale: Sale, 
        sale_data: SaleCreateRequest,
        receipt_url: Optional[str]
    ) -> SaleResponse:
        """Construir respuesta estandarizada"""
        return SaleResponse(
            success=True,
            message="Venta registrada exitosamente",
            sale_id=sale.id,
            total_amount=sale.total_amount,
            status=sale.status,
            requires_confirmation=sale.requires_confirmation,
            created_at=sale.sale_date,
            items_count=len(sale_data.items),
            payment_methods_count=len(sale_data.payment_methods),
            inventory_updated=True,
            receipt_image_url=receipt_url
        )