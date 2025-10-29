from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Any, Optional ,Literal

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
        """Buscar productos para bodeguero - ubicaciones asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al bodeguero
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar bodegas y locales asignadas
        warehouse_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type.in_(['bodega', 'local'])
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
        """Obtener TODOS los productos para bodeguero - ubicaciones asignadas - FILTRADO POR COMPANY_ID"""
        # Obtener ubicaciones asignadas al bodeguero
        assigned_location_names = self.get_user_assigned_location_names(user_id, company_id)
        
        if not assigned_location_names:
            return []
        
        # Filtrar bodegas y locales asignadas
        warehouse_locations = self.db.query(Location).filter(
            and_(
                Location.name.in_(assigned_location_names),
                Location.company_id == company_id,
                Location.type.in_(['bodega', 'local'])
            )
        ).all()
        
        warehouse_names = [loc.name for loc in warehouse_locations]
        
        if not warehouse_names:
            return []
        
        # Obtener TODOS los productos de las ubicaciones asignadas
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
        """Obtener información de ubicaciones asignadas a un usuario - FILTRADO POR COMPANY_ID"""
        assigned_locations = self.get_user_assigned_locations_info(user_id, company_id)
        return [loc for loc in assigned_locations if loc.type in ['bodega', 'local']]

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
                'quantity_exhibition': size.quantity_exhibition,
                'inventory_type': size.inventory_type
            })
            products_dict[product.id]['total_quantity'] += size.quantity
        
        # Convertir a lista
        result = list(products_dict.values())
        
        # Ordenar por marca, modelo, referencia
        result.sort(key=lambda x: (x['brand'] or '', x['model'] or '', x['reference_code'] or ''))
        
        return result
    
    def get_local_availability(
        self,
        product_id: int,
        size: str,
        location_name: str,
        company_id: int
    ) -> Dict[str, any]:
        """
        Obtener disponibilidad detallada en una ubicación específica
        
        Returns:
            Dict con información de pares y pies individuales
        """
        
        results = self.db.query(
            ProductSize.inventory_type,
            ProductSize.quantity,
            ProductSize.quantity_exhibition
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                ProductSize.company_id == company_id,
                ProductSize.quantity > 0
            )
        ).all()
        
        availability = {
            'pairs': 0,
            'pairs_exhibition': 0,
            'left_feet': 0,
            'right_feet': 0
        }
        
        for inventory_type, quantity, quantity_exhibition in results:
            if inventory_type == 'pair':
                availability['pairs'] = quantity
                availability['pairs_exhibition'] = quantity_exhibition or 0
            elif inventory_type == 'left_only':
                availability['left_feet'] = quantity
            elif inventory_type == 'right_only':
                availability['right_feet'] = quantity
        
        return availability
    
    def get_global_distribution(
        self,
        product_id: int,
        size: str,
        company_id: int,
        current_location_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        Obtener distribución global del producto por ubicaciones
        
        Args:
            product_id: ID del producto
            size: Talla
            company_id: ID de la compañía
            current_location_id: ID de ubicación actual (para calcular distancias)
        
        Returns:
            Dict con distribución completa
        """
        
        # Query principal con información de ubicaciones
        results = self.db.query(
            ProductSize.inventory_type,
            ProductSize.quantity,
            ProductSize.location_name,
            Location.id.label('location_id'),
            Location.type.label('location_type'),
            Location.address
        ).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.company_id == company_id,
                Location.company_id == company_id,
                ProductSize.quantity > 0
            )
        ).all()
        
        # Procesar resultados por ubicación
        locations = {}
        totals = {
            'pairs': 0,
            'left_feet': 0,
            'right_feet': 0
        }
        
        for inventory_type, quantity, location_name, location_id, location_type, address in results:
            if location_name not in locations:
                locations[location_name] = {
                    'location_id': location_id,
                    'location_name': location_name,
                    'location_type': location_type,
                    'address': address,
                    'pairs': 0,
                    'left_feet': 0,
                    'right_feet': 0
                }
            
            if inventory_type == 'pair':
                locations[location_name]['pairs'] += quantity
                totals['pairs'] += quantity
            elif inventory_type == 'left_only':
                locations[location_name]['left_feet'] += quantity
                totals['left_feet'] += quantity
            elif inventory_type == 'right_only':
                locations[location_name]['right_feet'] += quantity
                totals['right_feet'] += quantity
        
        # Calcular pares formables
        formable_pairs = min(totals['left_feet'], totals['right_feet'])
        total_potential_pairs = totals['pairs'] + formable_pairs
        
        efficiency_percentage = 0
        if total_potential_pairs > 0:
            efficiency_percentage = round((totals['pairs'] / total_potential_pairs) * 100, 2)
        
        totals.update({
            'formable_pairs': formable_pairs,
            'total_potential_pairs': total_potential_pairs,
            'efficiency_percentage': efficiency_percentage
        })
        
        return {
            'totals': totals,
            'by_location': list(locations.values())
        }
    
    def find_formation_opportunities(
        self,
        product_id: int,
        size: str,
        company_id: int
    ) -> List[Dict[str, any]]:
        """
        Encontrar oportunidades de formación de pares
        
        Identifica combinaciones de ubicaciones donde se pueden formar pares
        al juntar pies izquierdos y derechos.
        """
        
        # Obtener ubicaciones con pies izquierdos
        left_locations = self.db.query(
            ProductSize.location_name,
            Location.id.label('location_id'),
            ProductSize.quantity
        ).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.inventory_type == 'left_only',
                ProductSize.company_id == company_id,
                ProductSize.quantity > 0
            )
        ).all()
        
        # Obtener ubicaciones con pies derechos
        right_locations = self.db.query(
            ProductSize.location_name,
            Location.id.label('location_id'),
            ProductSize.quantity
        ).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.inventory_type == 'right_only',
                ProductSize.company_id == company_id,
                ProductSize.quantity > 0
            )
        ).all()
        
        opportunities = []
        
        # Caso especial: misma ubicación
        for left_loc in left_locations:
            for right_loc in right_locations:
                if left_loc.location_name == right_loc.location_name:
                    formable = min(left_loc.quantity, right_loc.quantity)
                    if formable > 0:
                        opportunities.append({
                            'formable_pairs': formable,
                            'same_location': True,
                            'location_id': left_loc.location_id,
                            'location_name': left_loc.location_name,
                            'left_quantity': left_loc.quantity,
                            'right_quantity': right_loc.quantity,
                            'priority': 'high'  # Misma ubicación = alta prioridad
                        })
        
        # Combinaciones entre ubicaciones diferentes
        for left_loc in left_locations:
            for right_loc in right_locations:
                if left_loc.location_name != right_loc.location_name:
                    formable = min(left_loc.quantity, right_loc.quantity)
                    if formable > 0:
                        opportunities.append({
                            'formable_pairs': formable,
                            'same_location': False,
                            'left_location_id': left_loc.location_id,
                            'left_location_name': left_loc.location_name,
                            'left_quantity': left_loc.quantity,
                            'right_location_id': right_loc.location_id,
                            'right_location_name': right_loc.location_name,
                            'right_quantity': right_loc.quantity,
                            'priority': 'medium'
                        })
        
        # Ordenar por cantidad formable (descendente)
        opportunities.sort(key=lambda x: x['formable_pairs'], reverse=True)
        
        return opportunities
    
    def find_opposite_foot(
        self,
        product_id: int,
        size: str,
        foot_side: Literal['left', 'right'],
        current_location_id: int,
        company_id: int
    ) -> List[Dict[str, any]]:
        """
        Buscar el pie opuesto más cercano
        
        Args:
            product_id: ID del producto
            size: Talla
            foot_side: Lado del pie que se busca ('left' o 'right')
            current_location_id: Ubicación actual
            company_id: ID de la compañía
        
        Returns:
            Lista de ubicaciones con el pie opuesto, ordenadas por distancia
        """
        
        opposite_type = 'right_only' if foot_side == 'left' else 'left_only'
        
        results = self.db.query(
            ProductSize.location_name,
            Location.id.label('location_id'),
            Location.type.label('location_type'),
            ProductSize.quantity,
            Location.address
        ).join(
            Location, ProductSize.location_name == Location.name
        ).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.inventory_type == opposite_type,
                ProductSize.company_id == company_id,
                Location.company_id == company_id,
                ProductSize.quantity > 0,
                Location.id != current_location_id  # Excluir ubicación actual
            )
        ).all()
        
        opposite_locations = [
            {
                'location_id': location_id,
                'location_name': location_name,
                'location_type': location_type,
                'quantity': quantity,
                'address': address,
                'foot_side': 'right' if opposite_type == 'right_only' else 'left'
            }
            for location_name, location_id, location_type, quantity, address in results
        ]
        
        # TODO: Calcular distancias reales cuando tengamos coordenadas
        # Por ahora, priorizar bodegas primero
        opposite_locations.sort(
            key=lambda x: (0 if x['location_type'] == 'bodega' else 1, x['location_name'])
        )
        
        return opposite_locations

    def get_product_by_reference(self, reference_code: str, company_id: int) -> Optional[Product]:
        """
        Obtener producto por código de referencia
        
        Args:
            reference_code: Código de referencia del producto
            company_id: ID de la compañía
        
        Returns:
            Product o None si no existe
        """
        return self.db.query(Product).filter(
            and_(
                Product.reference_code == reference_code,
                Product.company_id == company_id
            )
        ).first()