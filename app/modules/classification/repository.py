# app/modules/classification/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional
from app.shared.database.models import Product, ProductSize, ProductMapping, Location

class ClassificationRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def search_products_by_reference(self, reference_code: str, company_id: int) -> List[Dict[str, Any]]:
        """Buscar productos por código de referencia - FILTRADO POR COMPANY_ID"""
        products = self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                Product.reference_code.ilike(f"%{reference_code}%")
            )
        ).limit(10).all()
        
        return [
            {
                "id": p.id,
                "reference_code": p.reference_code,
                "brand": p.brand,
                "model": p.model,
                "color_info": p.color_info,
                "description": p.description,
                "unit_price": float(p.unit_price),
                "box_price": float(p.box_price),
                "image_url": p.image_url
            }
            for p in products
        ]
    
    def get_product_availability(self, product_id: int, user_location: str, company_id: int) -> Dict[str, Any]:
        """Obtener disponibilidad de producto por ubicaciones - FILTRADO POR COMPANY_ID"""
        # Stock en ubicación actual con JOIN para obtener location_id
        current_stock = self.db.query(ProductSize, Location.id.label('location_id')).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.company_id == company_id,
                ProductSize.location_name == user_location,
                Location.company_id == company_id
            )
        ).all()
        
        # Stock en otras ubicaciones con JOIN para obtener location_id
        other_stock = self.db.query(ProductSize, Location.id.label('location_id')).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.company_id == company_id,
                ProductSize.location_name != user_location,
                ProductSize.quantity > 0,
                Location.company_id == company_id
            )
        ).all()
        
        return {
            "current_location": [
                {
                    "size": ps.size,
                    "quantity": ps.quantity,
                    "quantity_exhibition": ps.quantity_exhibition,
                    "location_id": location_id
                }
                for ps, location_id in current_stock
            ],
            "other_locations": [
                {
                    "location": ps.location_name,
                    "size": ps.size,
                    "quantity": ps.quantity,
                    "location_id": location_id
                }
                for ps, location_id in other_stock
            ]
        }
    
    def search_similar_products(self, brand: str, model: str, company_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Buscar productos similares por marca y modelo - FILTRADO POR COMPANY_ID"""
        similar = self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                or_(
                    and_(Product.brand.ilike(f"%{brand}%"), Product.model.ilike(f"%{model}%")),
                    Product.brand.ilike(f"%{brand}%")
                )
            )
        ).limit(limit).all()
        
        return [
            {
                "reference_code": p.reference_code,
                "brand": p.brand,
                "model": p.model,
                "similarity_reason": "Misma marca" if p.brand.lower() == brand.lower() else "Marca similar"
            }
            for p in similar
        ]
    
    def search_products_by_description(self, model_name: str, brand: str = None, company_id: int = None) -> List[Dict[str, Any]]:
        """Buscar productos por descripción y marca - FILTRADO POR COMPANY_ID"""
        query = self.db.query(Product).filter(Product.company_id == company_id)
        
        # ✅ BÚSQUEDA FLEXIBLE
        conditions = or_(
            Product.description.ilike(f"%{model_name}%"),
            Product.model.ilike(f"%{model_name}%")
        )
        
        # ✅ SOLO FILTRAR POR MARCA SI NO ES "Unknown"
        if brand and brand != 'Unknown':
            conditions = and_(
                Product.brand.ilike(f"%{brand}%"),
                conditions
            )
        
        products = query.filter(conditions).limit(10).all()
        
        return [
            {
                "id": p.id,
                "reference_code": p.reference_code,
                "brand": p.brand,
                "model": p.model,
                "color_info": p.color_info,
                "description": p.description,
                "unit_price": float(p.unit_price),
                "box_price": float(p.box_price),
                "image_url": p.image_url
            }
            for p in products
        ]