from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, select
from datetime import datetime
from fastapi import HTTPException

from app.shared.database.models import Product, ProductSize, InventoryChange

class InventoryService:
    """Servicio optimizado para operaciones de inventario"""
    
    @staticmethod
    def validate_and_reserve_stock(
        db: Session, 
        items: List[Dict[str, Any]], 
        location_name: str,
        company_id: int
    ) -> List[Tuple[ProductSize, Product]]:
        """
        Validar y reservar stock atómicamente con bloqueo pesimista.
        
        Optimizaciones:
        - SELECT FOR UPDATE previene race conditions
        - JOIN único para obtener Product y ProductSize juntos
        - Validación completa antes de modificar datos
        - MULTI-TENANT: Filtra por company_id
        
        Args:
            db: Sesión de base de datos
            items: Items a validar [{sneaker_reference_code, size, quantity}]
            location_name: Nombre de la ubicación
            company_id: ID de la compañía (MULTI-TENANT)
            
        Returns:
            List[(ProductSize, Product)]: Productos reservados con sus datos
            
        Raises:
            HTTPException: Si hay stock insuficiente o producto no existe
        """
        reserved = []
        unavailable = []
        
        for item in items:
            # Query optimizado: JOIN + SELECT FOR UPDATE en una sola consulta + MULTI-TENANT
            result = db.query(ProductSize, Product).join(
                Product, ProductSize.product_id == Product.id
            ).filter(
                and_(
                    Product.reference_code == item['sneaker_reference_code'],
                    ProductSize.size == item['size'],
                    ProductSize.location_name == location_name,
                    Product.company_id == company_id,
                    ProductSize.company_id == company_id
                )
            ).with_for_update().first()
            
            if not result:
                unavailable.append(
                    f"{item['sneaker_reference_code']} talla {item['size']} (no existe en {location_name})"
                )
                continue
            
            product_size, product = result
            
            if product_size.quantity < item['quantity']:
                unavailable.append(
                    f"{item['sneaker_reference_code']} talla {item['size']} "
                    f"(stock: {product_size.quantity}, necesario: {item['quantity']})"
                )
                continue
            
            reserved.append((product_size, product))
        
        if unavailable:
            raise HTTPException(
                status_code=400,
                detail="Stock insuficiente:\n" + "\n".join(f"• {x}" for x in unavailable)
            )
        
        return reserved
    
    @staticmethod
    def update_reserved_stock(
        db: Session,
        reserved_products: List[Tuple[ProductSize, Product]],
        items: List[Dict[str, Any]],
        user_id: int,
        sale_id: int,
        company_id: int
    ) -> None:
        """
        Actualizar stock de productos YA RESERVADOS.
        
        Optimización: Bulk insert de inventory_changes si es posible
        
        Args:
            db: Sesión de base de datos
            reserved_products: Productos bloqueados [(ProductSize, Product)]
            items: Items de la venta
            user_id: ID del usuario
            sale_id: ID de la venta
        """
        inventory_changes = []
        
        for (product_size, product), item in zip(reserved_products, items):
            quantity_before = product_size.quantity
            product_size.quantity -= item['quantity']
            
            # Preparar cambio de inventario
            inventory_change = InventoryChange(
                product_id=product.id,
                change_type='sale',
                size=item['size'],
                quantity_before=quantity_before,
                quantity_after=product_size.quantity,
                user_id=user_id,
                reference_id=sale_id,
                notes=f"Venta #{sale_id}",
                created_at=datetime.now(),
                company_id=company_id
            )
            inventory_changes.append(inventory_change)
        
        # Bulk insert para mejor performance
        db.bulk_save_objects(inventory_changes)
    
    @staticmethod
    def check_product_availability(
        db: Session, 
        reference_code: str, 
        size: str, 
        location_name: str,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Verificar disponibilidad SIN bloquear (solo lectura).
        
        Optimización: Query simple sin JOIN innecesario
        MULTI-TENANT: Filtra por company_id
        """
        product_size = db.query(ProductSize).join(Product).filter(
            and_(
                Product.reference_code == reference_code,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                Product.company_id == company_id,
                ProductSize.company_id == company_id
            )
        ).first()
        
        if not product_size:
            return {"available": False, "quantity": 0, "can_sell": False}
        
        return {
            "available": product_size.quantity > 0,
            "quantity": product_size.quantity,
            "can_sell": product_size.quantity > 0
        }
    
    @staticmethod
    def get_products_stock_batch(
        db: Session,
        reference_codes: List[str],
        location_name: str,
        company_id: int
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Obtener stock de múltiples productos en una sola query.
        
        Optimización: Query único en vez de N queries
        MULTI-TENANT: Filtra por company_id
        
        Returns:
            Dict[reference_code, List[{size, quantity, quantity_exhibition}]]
        """
        results = db.query(
            Product.reference_code,
            ProductSize.size,
            ProductSize.quantity,
            ProductSize.quantity_exhibition
        ).join(
            ProductSize, Product.id == ProductSize.product_id
        ).filter(
            and_(
                Product.reference_code.in_(reference_codes),
                ProductSize.location_name == location_name,
                Product.company_id == company_id,
                ProductSize.company_id == company_id
            )
        ).all()
        
        # Agrupar por reference_code
        stock_by_product = {}
        for ref_code, size, qty, qty_exhibition in results:
            if ref_code not in stock_by_product:
                stock_by_product[ref_code] = []
            
            stock_by_product[ref_code].append({
                'size': size,
                'quantity': qty,
                'quantity_exhibition': qty_exhibition
            })
        
        return stock_by_product