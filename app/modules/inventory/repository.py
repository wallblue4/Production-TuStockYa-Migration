from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional

from app.shared.database.models import Product, ProductSize, UserLocationAssignment, Location
from .schemas import InventorySearchParams, InventoryByRoleParams

class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_products(self, search_params: InventorySearchParams, company_id: int) -> List[Product]:
        """Buscar productos según criterios - FILTRADO POR COMPANY_ID"""
        query = self.db.query(Product).filter(Product.company_id == company_id)
        
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

    def get_product_sizes(self, product_id: int, company_id: int) -> List[ProductSize]:
        """Obtener todas las tallas de un producto - FILTRADO POR COMPANY_ID"""
        return self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.company_id == company_id
            )
        ).all()

    def get_user_assigned_locations(self, user_id: int, company_id: int) -> List[int]:
        """Obtener IDs de ubicaciones asignadas a un usuario - FILTRADO POR COMPANY_ID"""
        assignments = self.db.query(UserLocationAssignment).filter(
            and_(
                UserLocationAssignment.user_id == user_id,
                UserLocationAssignment.company_id == company_id,
                UserLocationAssignment.is_active == True
            )
        ).all()
        return [assignment.location_id for assignment in assignments]

    def get_user_assigned_location_names(self, user_id: int, company_id: int) -> List[str]:
        """Obtener nombres de ubicaciones asignadas a un usuario - FILTRADO POR COMPANY_ID"""
        assignments = self.db.query(UserLocationAssignment, Location).join(
            Location, UserLocationAssignment.location_id == Location.id
        ).filter(
            and_(
                UserLocationAssignment.user_id == user_id,
                UserLocationAssignment.company_id == company_id,
                UserLocationAssignment.is_active == True,
                Location.company_id == company_id
            )
        ).all()
        return [assignment[1].name for assignment in assignments]

    def search_products_by_warehouse_keeper(self, user_id: int, search_params: InventoryByRoleParams, company_id: int) -> List[Product]:
        """Buscar productos para bodeguero - solo bodegas asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al bodeguero
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar solo bodegas (type = 'bodega')
        warehouse_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type == 'bodega'
            )
        ).all()
        
        warehouse_names = [loc.name for loc in warehouse_locations]
        
        if not warehouse_names:
            return []
        
        query = self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                Product.location_name.in_(warehouse_names)
            )
        )
        
        # Aplicar filtros adicionales
        if search_params.reference_code:
            query = query.filter(Product.reference_code.ilike(f"%{search_params.reference_code}%"))
        if search_params.brand:
            query = query.filter(Product.brand.ilike(f"%{search_params.brand}%"))
        if search_params.model:
            query = query.filter(Product.model.ilike(f"%{search_params.model}%"))
        if search_params.is_active is not None:
            query = query.filter(Product.is_active == search_params.is_active)
            
        return query.all()

    def search_products_by_admin(self, user_id: int, search_params: InventoryByRoleParams, company_id: int) -> List[Product]:
        """Buscar productos para administrador - locales y bodegas asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al administrador
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar locales y bodegas asignadas
        assigned_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type.in_(['local', 'bodega'])
            )
        ).all()
        
        location_names = [loc.name for loc in assigned_locations]
        
        if not location_names:
            return []
        
        query = self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                Product.location_name.in_(location_names)
            )
        )
        
        # Aplicar filtros adicionales
        if search_params.reference_code:
            query = query.filter(Product.reference_code.ilike(f"%{search_params.reference_code}%"))
        if search_params.brand:
            query = query.filter(Product.brand.ilike(f"%{search_params.brand}%"))
        if search_params.model:
            query = query.filter(Product.model.ilike(f"%{search_params.model}%"))
        if search_params.is_active is not None:
            query = query.filter(Product.is_active == search_params.is_active)
            
        return query.all()

    def get_all_products_by_warehouse_keeper(self, user_id: int, company_id: int) -> List[Product]:
        """Obtener TODOS los productos para bodeguero - solo bodegas asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al bodeguero
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar solo bodegas (type = 'bodega')
        warehouse_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type == 'bodega'
            )
        ).all()
        
        warehouse_names = [loc.name for loc in warehouse_locations]
        
        if not warehouse_names:
            return []
        
        # Obtener TODOS los productos de las bodegas asignadas
        return self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                Product.location_name.in_(warehouse_names)
            )
        ).all()

    def get_all_products_by_admin(self, user_id: int, company_id: int) -> List[Product]:
        """Obtener TODOS los productos para administrador - locales y bodegas asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al administrador
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar locales y bodegas asignadas
        assigned_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type.in_(['local', 'bodega'])
            )
        ).all()
        
        location_names = [loc.name for loc in assigned_locations]
        
        if not location_names:
            return []
        
        # Obtener TODOS los productos de las ubicaciones asignadas
        return self.db.query(Product).filter(
            and_(
                Product.company_id == company_id,
                Product.location_name.in_(location_names)
            )
        ).all()

    def get_user_assigned_locations_info(self, user_id: int, company_id: int) -> List[Location]:
        """Obtener información completa de ubicaciones asignadas a un usuario - FILTRADO POR COMPANY_ID"""
        assignments = self.db.query(UserLocationAssignment, Location).join(
            Location, UserLocationAssignment.location_id == Location.id
        ).filter(
            and_(
                UserLocationAssignment.user_id == user_id,
                UserLocationAssignment.company_id == company_id,
                UserLocationAssignment.is_active == True,
                Location.company_id == company_id
            )
        ).all()
        return [assignment[1] for assignment in assignments]

    def get_warehouse_locations_info(self, user_id: int, company_id: int) -> List[Location]:
        """Obtener información de bodegas asignadas a un usuario - FILTRADO POR COMPANY_ID"""
        assigned_locations = self.get_user_assigned_locations_info(user_id, company_id)
        return [loc for loc in assigned_locations if loc.type == 'bodega']

    def get_admin_locations_info(self, user_id: int, company_id: int) -> List[Location]:
        """Obtener información de locales y bodegas asignadas a un administrador - FILTRADO POR COMPANY_ID"""
        assigned_locations = self.get_user_assigned_locations_info(user_id, company_id)
        return [loc for loc in assigned_locations if loc.type in ['local', 'bodega']]

    def get_products_by_location(self, location_name: str, company_id: int) -> List[Product]:
        """Obtener todos los productos de una ubicación específica - FILTRADO POR COMPANY_ID"""
        return self.db.query(Product).filter(
            and_(
                Product.location_name == location_name,
                Product.company_id == company_id
            )
        ).all()

    def get_products_with_sizes_by_location(self, location_name: str, company_id: int) -> List[Dict]:
        """Obtener productos con sus tallas agrupadas para una ubicación específica - FILTRADO POR COMPANY_ID"""
        # Obtener productos que tienen tallas en esta ubicación
        # Usar JOIN para obtener productos que tienen ProductSize en esta ubicación
        products_with_sizes = self.db.query(Product, ProductSize).join(
            ProductSize, Product.id == ProductSize.product_id
        ).filter(
            and_(
                ProductSize.location_name == location_name,
                Product.company_id == company_id,
                ProductSize.company_id == company_id
            )
        ).all()
        
        # Agrupar por producto
        products_dict = {}
        for product, size in products_with_sizes:
            if product.id not in products_dict:
                products_dict[product.id] = {
                    'product_id': product.id,
                    'reference_code': product.reference_code,
                    'description': product.description,
                    'brand': product.brand,
                    'model': product.model,
                    'color_info': product.color_info,
                    'video_url': product.video_url,
                    'image_url': product.image_url,
                    'unit_price': product.unit_price,
                    'box_price': product.box_price,
                    'is_active': product.is_active,
                    'created_at': product.created_at,
                    'updated_at': product.updated_at,
                    'location_name': location_name,
                    'sizes': [],
                    'total_quantity': 0
                }
            
            # Agregar talla a la lista
            products_dict[product.id]['sizes'].append({
                'size': size.size,
                'quantity': size.quantity,
                'quantity_exhibition': size.quantity_exhibition
            })
            products_dict[product.id]['total_quantity'] += size.quantity
        
        # Convertir a lista
        result = list(products_dict.values())
        
        # Ordenar por marca, modelo, referencia
        result.sort(key=lambda x: (x['brand'] or '', x['model'] or '', x['reference_code'] or ''))
        
        return result
