from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional

from app.shared.database.models import Product, ProductSize
from .schemas import InventorySearchParams

class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_products(self, search_params: InventorySearchParams) -> List[Product]:
        """Buscar productos según criterios"""
        query = self.db.query(Product)
        
        if search_params.reference_code:
            query = query.filter(Product.reference_code.ilike(f"%{search_params.reference_code}%"))
        if search_params.brand:
            query = query.filter(Product.brand.ilike(f"%{search_params.brand}%"))
        if search_params.model:
            query = query.filter(Product.model.ilike(f"%{search_params.model}%"))
        if search_params.location_name:
            query = query.filter(Product.location_name == search_params.location_name)
        if search_params.is_active is not None:
            query = query.filter(Product.is_active == search_params.is_active)
            
        return query.all()

    def get_product_sizes(self, product_id: int) -> List[ProductSize]:
        """Obtener todas las tallas de un producto"""
        return self.db.query(ProductSize).filter(
            ProductSize.product_id == product_id
        ).all()
