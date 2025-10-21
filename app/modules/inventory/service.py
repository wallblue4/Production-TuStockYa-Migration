from typing import List ,Dict ,Optional ,Literal
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime


from app.shared.database.models import Location ,Product,ProductSize
from app.shared.schemas.inventory_distribution import PairFormationResult


from .repository import InventoryRepository
from .schemas import ProductResponse, InventorySearchParams, InventoryByRoleParams, GroupedInventoryResponse, LocationInventoryResponse, LocationInfo, ProductInfo, SimpleInventoryResponse, SimpleLocationInventory

from .schemas import (
    ManualPairFormationRequest,
    ManualPairFormationResponse,
    FormableOpportunitiesRequest,
    FormableOpportunitiesResponse
)

import logging

logger = logging.getLogger(__name__)


class InventoryService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = InventoryRepository(db)

    async def search_inventory(self, search_params: InventorySearchParams) -> List[ProductResponse]:
        """Buscar productos en inventario según criterios"""
        try:
            products = self.repository.search_products(search_params, self.company_id)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id, self.company_id)
                sizes_data = [
                    {
                        "size": size.size,
                        "quantity": size.quantity,
                        "quantity_exhibition": size.quantity_exhibition
                    }
                    for size in sizes
                ]
                
                result.append(ProductResponse(
                    success=True,
                    message="Producto encontrado",
                    product_id=product.id,
                    reference_code=product.reference_code,
                    description=product.description,
                    brand=product.brand,
                    model=product.model,
                    color_info=product.color_info,
                    video_url=product.video_url,
                    image_url=product.image_url,
                    total_quantity=product.total_quantity,
                    location_name=product.location_name,
                    unit_price=product.unit_price,
                    box_price=product.box_price,
                    is_active=product.is_active,
                    sizes=sizes_data,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
                
            return result

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error buscando productos: {str(e)}"
            )

    async def get_warehouse_keeper_inventory(self, user_id: int, search_params: InventoryByRoleParams) -> List[ProductResponse]:
        """Obtener inventario para bodeguero - solo bodegas asignadas"""
        try:
            products = self.repository.search_products_by_warehouse_keeper(user_id, search_params, self.company_id)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id, self.company_id)
                sizes_data = [
                    {
                        "size": size.size,
                        "quantity": size.quantity,
                        "quantity_exhibition": size.quantity_exhibition
                    }
                    for size in sizes
                ]
                
                result.append(ProductResponse(
                    success=True,
                    message="Producto encontrado",
                    product_id=product.id,
                    reference_code=product.reference_code,
                    description=product.description,
                    brand=product.brand,
                    model=product.model,
                    color_info=product.color_info,
                    video_url=product.video_url,
                    image_url=product.image_url,
                    total_quantity=product.total_quantity,
                    location_name=product.location_name,
                    unit_price=product.unit_price,
                    box_price=product.box_price,
                    is_active=product.is_active,
                    sizes=sizes_data,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
                
            return result

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario del bodeguero: {str(e)}"
            )

    async def get_admin_inventory(self, user_id: int, search_params: InventoryByRoleParams) -> List[ProductResponse]:
        """Obtener inventario para administrador - locales y bodegas asignadas"""
        try:
            products = self.repository.search_products_by_admin(user_id, search_params, self.company_id)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id, self.company_id)
                sizes_data = [
                    {
                        "size": size.size,
                        "quantity": size.quantity,
                        "quantity_exhibition": size.quantity_exhibition
                    }
                    for size in sizes
                ]
                
                result.append(ProductResponse(
                    success=True,
                    message="Producto encontrado",
                    product_id=product.id,
                    reference_code=product.reference_code,
                    description=product.description,
                    brand=product.brand,
                    model=product.model,
                    color_info=product.color_info,
                    video_url=product.video_url,
                    image_url=product.image_url,
                    total_quantity=product.total_quantity,
                    location_name=product.location_name,
                    unit_price=product.unit_price,
                    box_price=product.box_price,
                    is_active=product.is_active,
                    sizes=sizes_data,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
                
            return result

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario del administrador: {str(e)}"
            )

    async def get_all_warehouse_keeper_inventory(self, user_id: int) -> List[ProductResponse]:
        """Obtener TODOS los productos para bodeguero - solo bodegas asignadas"""
        try:
            products = self.repository.get_all_products_by_warehouse_keeper(user_id, self.company_id)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id, self.company_id)
                sizes_data = [
                    {
                        "size": size.size,
                        "quantity": size.quantity,
                        "quantity_exhibition": size.quantity_exhibition
                    }
                    for size in sizes
                ]
                
                result.append(ProductResponse(
                    success=True,
                    message="Producto encontrado",
                    product_id=product.id,
                    reference_code=product.reference_code,
                    description=product.description,
                    brand=product.brand,
                    model=product.model,
                    color_info=product.color_info,
                    video_url=product.video_url,
                    image_url=product.image_url,
                    total_quantity=product.total_quantity,
                    location_name=product.location_name,
                    unit_price=product.unit_price,
                    box_price=product.box_price,
                    is_active=product.is_active,
                    sizes=sizes_data,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
                
            return result

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario completo del bodeguero: {str(e)}"
            )

    async def get_all_admin_inventory(self, user_id: int) -> List[ProductResponse]:
        """Obtener TODOS los productos para administrador - locales y bodegas asignadas"""
        try:
            products = self.repository.get_all_products_by_admin(user_id, self.company_id)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id, self.company_id)
                sizes_data = [
                    {
                        "size": size.size,
                        "quantity": size.quantity,
                        "quantity_exhibition": size.quantity_exhibition
                    }
                    for size in sizes
                ]
                
                result.append(ProductResponse(
                    success=True,
                    message="Producto encontrado",
                    product_id=product.id,
                    reference_code=product.reference_code,
                    description=product.description,
                    brand=product.brand,
                    model=product.model,
                    color_info=product.color_info,
                    video_url=product.video_url,
                    image_url=product.image_url,
                    total_quantity=product.total_quantity,
                    location_name=product.location_name,
                    unit_price=product.unit_price,
                    box_price=product.box_price,
                    is_active=product.is_active,
                    sizes=sizes_data,
                    created_at=product.created_at,
                    updated_at=product.updated_at
                ))
                
            return result

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario completo del administrador: {str(e)}"
            )

    def _create_product_info(self, product) -> ProductInfo:
        """Crear ProductInfo desde un producto"""
        sizes = self.repository.get_product_sizes(product.id, self.company_id)
        sizes_data = [
            {
                "size": size.size,
                "quantity": size.quantity,
                "quantity_exhibition": size.quantity_exhibition
            }
            for size in sizes
        ]
        
        return ProductInfo(
            product_id=product.id,
            reference_code=product.reference_code,
            description=product.description,
            brand=product.brand,
            model=product.model,
            color_info=product.color_info,
            video_url=product.video_url,
            image_url=product.image_url,
            total_quantity=product.total_quantity,
            unit_price=product.unit_price,
            box_price=product.box_price,
            is_active=product.is_active,
            sizes=sizes_data,
            created_at=product.created_at,
            updated_at=product.updated_at
        )

    async def get_grouped_warehouse_keeper_inventory(self, user_id: int) -> GroupedInventoryResponse:
        """Obtener inventario agrupado por ubicación para bodeguero"""
        try:
            # Obtener ubicaciones asignadas (solo bodegas)
            locations = self.repository.get_warehouse_locations_info(user_id, self.company_id)
            
            if not locations:
                return GroupedInventoryResponse(
                    success=True,
                    message="No hay bodegas asignadas",
                    locations=[],
                    total_locations=0,
                    total_products=0
                )
            
            location_inventories = []
            total_products = 0
            
            for location in locations:
                # Obtener productos de esta ubicación
                products = self.repository.get_products_by_location(location.name, self.company_id)
                
                # Convertir productos a ProductInfo
                product_infos = [self._create_product_info(product) for product in products]
                
                # Calcular totales
                total_quantity = sum(product.total_quantity for product in products)
                
                # Crear LocationInfo
                location_info = LocationInfo(
                    location_id=location.id,
                    location_name=location.name,
                    location_type=location.type
                )
                
                # Crear LocationInventoryResponse
                location_inventory = LocationInventoryResponse(
                    location=location_info,
                    products=product_infos,
                    total_products=len(products),
                    total_quantity=total_quantity
                )
                
                location_inventories.append(location_inventory)
                total_products += len(products)
            
            return GroupedInventoryResponse(
                success=True,
                message="Inventario obtenido exitosamente",
                locations=location_inventories,
                total_locations=len(locations),
                total_products=total_products
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario agrupado del bodeguero: {str(e)}"
            )

    async def get_grouped_admin_inventory(self, user_id: int) -> GroupedInventoryResponse:
        """Obtener inventario agrupado por ubicación para administrador"""
        try:
            # Obtener ubicaciones asignadas (locales y bodegas)
            locations = self.repository.get_admin_locations_info(user_id, self.company_id)
            
            if not locations:
                return GroupedInventoryResponse(
                    success=True,
                    message="No hay ubicaciones asignadas",
                    locations=[],
                    total_locations=0,
                    total_products=0
                )
            
            location_inventories = []
            total_products = 0
            
            for location in locations:
                # Obtener productos de esta ubicación
                products = self.repository.get_products_by_location(location.name, self.company_id)
                
                # Convertir productos a ProductInfo
                product_infos = [self._create_product_info(product) for product in products]
                
                # Calcular totales
                total_quantity = sum(product.total_quantity for product in products)
                
                # Crear LocationInfo
                location_info = LocationInfo(
                    location_id=location.id,
                    location_name=location.name,
                    location_type=location.type
                )
                
                # Crear LocationInventoryResponse
                location_inventory = LocationInventoryResponse(
                    location=location_info,
                    products=product_infos,
                    total_products=len(products),
                    total_quantity=total_quantity
                )
                
                location_inventories.append(location_inventory)
                total_products += len(products)
            
            return GroupedInventoryResponse(
                success=True,
                message="Inventario obtenido exitosamente",
                locations=location_inventories,
                total_locations=len(locations),
                total_products=total_products
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario agrupado del administrador: {str(e)}"
            )

    def _create_product_response_from_grouped_data(self, product_data: dict) -> ProductResponse:
        """Crear ProductResponse desde datos de producto agrupado con todas las tallas"""
        return ProductResponse(
            success=True,
            message="Producto encontrado",
            product_id=product_data['product_id'],
            reference_code=product_data['reference_code'],
            description=product_data['description'],
            brand=product_data['brand'],
            model=product_data['model'],
            color_info=product_data['color_info'],
            video_url=product_data['video_url'],
            image_url=product_data['image_url'],
            total_quantity=product_data['total_quantity'],
            location_name=product_data['location_name'],
            unit_price=product_data['unit_price'],
            box_price=product_data['box_price'],
            is_active=product_data['is_active'],
            sizes=product_data['sizes'],
            created_at=product_data['created_at'],
            updated_at=product_data['updated_at']
        )

    async def get_simple_warehouse_keeper_inventory(self, user_id: int) -> SimpleInventoryResponse:
        """Obtener inventario simplificado para bodeguero - estructura por ubicación"""
        try:
            # Obtener ubicaciones asignadas (solo bodegas)
            locations = self.repository.get_warehouse_locations_info(user_id, self.company_id)
            
            if not locations:
                return SimpleInventoryResponse(
                    success=True,
                    message="No hay bodegas asignadas",
                    locations=[]
                )
            
            location_inventories = []
            
            for location in locations:
                # Obtener productos con tallas agrupadas
                products_with_sizes = self.repository.get_products_with_sizes_by_location(location.name, self.company_id)
                
                # Convertir a ProductResponse
                product_responses = [
                    self._create_product_response_from_grouped_data(product_data) 
                    for product_data in products_with_sizes
                ]
                
                # Crear SimpleLocationInventory
                location_inventory = SimpleLocationInventory(
                    location_name=location.name,
                    location_id=location.id,
                    products=product_responses
                )
                
                location_inventories.append(location_inventory)
            
            return SimpleInventoryResponse(
                success=True,
                message="Inventario obtenido exitosamente",
                locations=location_inventories
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario simplificado del bodeguero: {str(e)}"
            )

    async def get_simple_admin_inventory(self, user_id: int) -> SimpleInventoryResponse:
        """Obtener inventario simplificado para administrador - estructura por ubicación"""
        try:
            # Obtener ubicaciones asignadas (locales y bodegas)
            locations = self.repository.get_admin_locations_info(user_id, self.company_id)
            
            if not locations:
                return SimpleInventoryResponse(
                    success=True,
                    message="No hay ubicaciones asignadas",
                    locations=[]
                )
            
            location_inventories = []
            
            for location in locations:
                # Obtener productos con tallas agrupadas
                products_with_sizes = self.repository.get_products_with_sizes_by_location(location.name, self.company_id)
                
                # Convertir a ProductResponse
                product_responses = [
                    self._create_product_response_from_grouped_data(product_data) 
                    for product_data in products_with_sizes
                ]
                
                # Crear SimpleLocationInventory
                location_inventory = SimpleLocationInventory(
                    location_name=location.name,
                    location_id=location.id,
                    products=product_responses
                )
                
                location_inventories.append(location_inventory)
            
            return SimpleInventoryResponse(
                success=True,
                message="Inventario obtenido exitosamente",
                locations=location_inventories
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo inventario simplificado del administrador: {str(e)}"
            )

    
    async def get_enhanced_availability(
        self,
        reference_code: str,
        size: str,
        user_location_id: int,
        user_id: int
    ) -> Dict[str, any]:
        """
        Obtener disponibilidad mejorada con información de pies separados
        
        Este método es usado por el scanner para mostrar información completa
        """
        
        start_time = datetime.now()
        
        # Obtener producto
        product = self.repository.get_product_by_reference(reference_code, self.company_id)
        
        if not product:
            return {
                "success": False,
                "message": "Producto no encontrado"
            }
        
        # Obtener ubicación actual
        user_location = self.db.query(Location).filter(
            and_(
                Location.id == user_location_id,
                Location.company_id == self.company_id
            )
        ).first()
        
        if not user_location:
            raise HTTPException(404, "Ubicación no encontrada")
        
        # 1. Disponibilidad local
        local_avail = self.repository.get_local_availability(
            product_id=product.id,
            size=size,
            location_name=user_location.name,
            company_id=self.company_id
        )
        
        # 2. Distribución global
        global_dist = self.repository.get_global_distribution(
            product_id=product.id,
            size=size,
            company_id=self.company_id,
            current_location_id=user_location_id
        )
        
        # 3. Oportunidades de formación
        opportunities = self.repository.find_formation_opportunities(
            product_id=product.id,
            size=size,
            company_id=self.company_id
        )
        
        # 4. Construir disponibilidad local
        local_availability = self._build_local_availability(
            local_avail,
            user_location
        )
        
        # 5. Generar sugerencias
        suggestions = self._generate_suggestions(
            local_avail,
            global_dist,
            opportunities,
            user_location
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return {
            "success": True,
            "scan_timestamp": datetime.now().isoformat(),
            "product": {
                "product_id": product.id,
                "reference_code": product.reference_code,
                "brand": product.brand,
                "model": product.model,
                "size": size,
                "unit_price": float(product.unit_price),
                "image_url": product.image_url
            },
            "local_availability": local_availability,
            "global_distribution": global_dist,
            "formation_opportunities": self._format_opportunities(opportunities),
            "suggestions": suggestions,
            "processing_time_ms": round(processing_time, 2)
        }
    
    def _build_local_availability(
        self,
        local_avail: Dict,
        location: Location
    ) -> Dict:
        """Construir objeto de disponibilidad local"""
        
        pairs_available = local_avail['pairs'] - local_avail['pairs_exhibition']
        can_sell = pairs_available > 0
        
        left_available = local_avail['left_feet'] > 0
        right_available = local_avail['right_feet'] > 0
        can_form_pair = left_available and right_available
        
        # Determinar qué falta
        missing = None
        if not can_form_pair and not can_sell:
            if not left_available and not right_available:
                missing = 'both'
            elif not left_available:
                missing = 'left'
            elif not right_available:
                missing = 'right'
        
        # Construir resumen
        if can_sell:
            summary = {
                "can_sell_now": True,
                "reason": f"Tienes {pairs_available} par(es) disponible(s) para venta",
                "action_required": None
            }
        elif can_form_pair:
            summary = {
                "can_sell_now": False,
                "reason": f"Puedes formar {min(local_avail['left_feet'], local_avail['right_feet'])} par(es) con pies disponibles",
                "action_required": "Formar par localmente"
            }
        elif missing == 'both':
            summary = {
                "can_sell_now": False,
                "reason": "No hay inventario disponible en tu ubicación",
                "action_required": "Solicitar transferencia"
            }
        else:
            missing_name = "izquierdo" if missing == 'left' else "derecho"
            summary = {
                "can_sell_now": False,
                "reason": f"Tienes pie {missing_name} pero falta el opuesto",
                "action_required": f"Solicitar pie {missing_name} faltante"
            }
        
        return {
            "location_id": location.id,
            "location_name": location.name,
            "location_type": location.type,
            "pairs": {
                "quantity": local_avail['pairs'],
                "quantity_exhibition": local_avail['pairs_exhibition'],
                "quantity_available_sale": pairs_available,
                "can_sell": can_sell
            },
            "individual_feet": {
                "left": {
                    "quantity": local_avail['left_feet'],
                    "available": left_available
                },
                "right": {
                    "quantity": local_avail['right_feet'],
                    "available": right_available
                },
                "can_form_pair": can_form_pair,
                "missing": missing
            },
            "summary": summary
        }
    
    def _generate_suggestions(
        self,
        local_avail: Dict,
        global_dist: Dict,
        opportunities: List[Dict],
        current_location: Location
    ) -> List[Dict]:
        """
        Generar sugerencias accionables para el vendedor
        
        Prioriza:
        1. Formar par localmente (si tiene ambos pies)
        2. Solicitar par completo desde bodega más cercana
        3. Solicitar pie faltante para formar par
        4. Restock general
        """
        
        suggestions = []
        
        # Sugerencia 1: Formar par localmente
        if local_avail['left_feet'] > 0 and local_avail['right_feet'] > 0:
            formable = min(local_avail['left_feet'], local_avail['right_feet'])
            suggestions.append({
                "priority": "urgent",
                "type": "form_pair",
                "action": f"Formar {formable} par(es) con pies disponibles en tu ubicación",
                "estimated_time_minutes": 1,
                "cost_estimate": 0,
                "steps": [
                    "Ir a sección de formación de pares",
                    "Seleccionar cantidad a formar",
                    "Confirmar formación",
                    "Pares listos para venta"
                ]
            })
        
        # Sugerencia 2: Solicitar par completo desde bodega
        for loc in global_dist['by_location']:
            if loc['pairs'] > 0 and loc['location_type'] == 'bodega':
                suggestions.append({
                    "priority": "high",
                    "type": "transfer_pair",
                    "action": f"Solicitar par completo desde {loc['location_name']}",
                    "estimated_time_minutes": 15,
                    "cost_estimate": 5000,
                    "steps": [
                        "Crear solicitud de transferencia",
                        f"Bodeguero en {loc['location_name']} prepara el par",
                        "Corredor transporta",
                        "Recibes en tu local"
                    ],
                    "metadata": {
                        "from_location_id": loc['location_id'],
                        "from_location_name": loc['location_name'],
                        "available_quantity": loc['pairs']
                    }
                })
                break  # Solo sugerir la primera bodega
        
        # Sugerencia 3: Solicitar pie faltante
        if (local_avail['left_feet'] > 0 and local_avail['right_feet'] == 0) or \
           (local_avail['right_feet'] > 0 and local_avail['left_feet'] == 0):
            
            missing_side = 'right' if local_avail['right_feet'] == 0 else 'left'
            missing_name = 'derecho' if missing_side == 'right' else 'izquierdo'
            
            # Buscar pie opuesto
            opposite_locations = self.repository.find_opposite_foot(
                product_id=global_dist.get('product_id') if 'product_id' in global_dist else None,
                size=None,  # Necesitamos pasar el size
                foot_side=missing_side,
                current_location_id=current_location.id,
                company_id=self.company_id
            )
            
            if opposite_locations:
                closest = opposite_locations[0]
                suggestions.append({
                    "priority": "medium",
                    "type": "form_pair",
                    "action": f"Traer pie {missing_name} desde {closest['location_name']} para formar par",
                    "estimated_time_minutes": 45,
                    "cost_estimate": 3000,
                    "steps": [
                        f"Solicitar transferencia de pie {missing_name}",
                        "Corredor transporta",
                        "Formar par al recibir",
                        "Par listo para venta"
                    ],
                    "metadata": {
                        "from_location_id": closest['location_id'],
                        "from_location_name": closest['location_name'],
                        "foot_side": missing_side,
                        "available_quantity": closest['quantity']
                    }
                })
        
        # Sugerencia 4: Restock si no hay nada disponible cerca
        if not suggestions and global_dist['totals']['total_potential_pairs'] == 0:
            suggestions.append({
                "priority": "low",
                "type": "restock",
                "action": "No hay inventario disponible. Solicitar restock al administrador",
                "estimated_time_minutes": 1440,  # 24 horas
                "cost_estimate": None,
                "steps": [
                    "Crear solicitud de restock",
                    "Administrador procesa pedido",
                    "Proveedor envía mercancía",
                    "Inventario disponible"
                ]
            })
        
        return suggestions
    
    def _format_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """Formatear oportunidades de formación para la respuesta"""
        
        formatted = []
        
        for opp in opportunities:
            if opp.get('same_location'):
                # Oportunidad en misma ubicación
                formatted.append({
                    "formable_pairs": opp['formable_pairs'],
                    "type": "same_location",
                    "location_id": opp['location_id'],
                    "location_name": opp['location_name'],
                    "left_quantity": opp['left_quantity'],
                    "right_quantity": opp['right_quantity'],
                    "priority": "high",
                    "estimated_time_hours": 0,
                    "action": f"Formar {opp['formable_pairs']} par(es) en {opp['location_name']} (misma ubicación)"
                })
            else:
                # Oportunidad entre ubicaciones diferentes
                formatted.append({
                    "formable_pairs": opp['formable_pairs'],
                    "type": "cross_location",
                    "from_locations": [
                        {
                            "location_id": opp['left_location_id'],
                            "location_name": opp['left_location_name'],
                            "type": "left",
                            "quantity": opp['left_quantity']
                        },
                        {
                            "location_id": opp['right_location_id'],
                            "location_name": opp['right_location_name'],
                            "type": "right",
                            "quantity": opp['right_quantity']
                        }
                    ],
                    "priority": "medium",
                    "estimated_time_hours": 2.0,
                    "action": f"Formar {opp['formable_pairs']} par(es) juntando pies de {opp['left_location_name']} y {opp['right_location_name']}"
                })
        
        return formatted

    async def form_pair_manually(
        self,
        request: ManualPairFormationRequest,
        user_id: int
    ) -> ManualPairFormationResponse:
        """
        🆕 Formar pares manualmente desde pies individuales
        
        Casos de uso:
        - Vendedor tiene ambos pies pero no se formó par automáticamente
        - Admin decide consolidar inventario
        - Pies llegaron en momentos diferentes sin transferencia
        
        Proceso:
        1. Validar que el producto existe
        2. Validar que la ubicación existe
        3. Verificar disponibilidad de ambos pies
        4. Formar pares
        5. Registrar en historial
        """
        
        try:
            logger.info(f"🔨 Formación manual de par solicitada")
            logger.info(f"   Usuario: {user_id}")
            logger.info(f"   Producto: {request.reference_code}")
            logger.info(f"   Talla: {request.size}")
            logger.info(f"   Ubicación ID: {request.location_id}")
            logger.info(f"   Cantidad: {request.quantity}")
            
            # 1. Buscar producto
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == request.reference_code,
                    Product.company_id == self.company_id
                )
            ).first()
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Producto '{request.reference_code}' no encontrado"
                )
            
            logger.info(f"   ✅ Producto encontrado: {product.brand} {product.model}")
            
            # 2. Buscar ubicación
            location = self.db.query(Location).filter(
                and_(
                    Location.id == request.location_id,
                    Location.company_id == self.company_id
                )
            ).first()
            
            if not location:
                raise HTTPException(
                    status_code=404,
                    detail=f"Ubicación con ID {request.location_id} no encontrada"
                )
            
            logger.info(f"   ✅ Ubicación encontrada: {location.name}")
            
            # 3. Buscar pies individuales
            left_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == request.size,
                    ProductSize.location_name == location.name,
                    ProductSize.inventory_type == 'left_only',
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            right_foot = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == request.size,
                    ProductSize.location_name == location.name,
                    ProductSize.inventory_type == 'right_only',
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            # Validar disponibilidad
            if not left_foot or left_foot.quantity == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay pies izquierdos disponibles en {location.name}"
                )
            
            if not right_foot or right_foot.quantity == 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"No hay pies derechos disponibles en {location.name}"
                )
            
            # Validar cantidad solicitada
            max_formable = min(left_foot.quantity, right_foot.quantity)
            
            if request.quantity > max_formable:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"No se pueden formar {request.quantity} par(es). "
                        f"Máximo formable: {max_formable} "
                        f"(Izquierdos: {left_foot.quantity}, Derechos: {right_foot.quantity})"
                    )
                )
            
            logger.info(f"   ✅ Validación exitosa:")
            logger.info(f"      Pies izquierdos: {left_foot.quantity}")
            logger.info(f"      Pies derechos: {right_foot.quantity}")
            logger.info(f"      A formar: {request.quantity} par(es)")
            
            # 4. Formar pares
            result = await self._execute_pair_formation(
                product_id=product.id,
                size=request.size,
                location_name=location.name,
                quantity=request.quantity,
                left_foot=left_foot,
                right_foot=right_foot,
                user_id=user_id,
                notes=request.notes
            )
            
            # 5. Consultar estado final del inventario
            final_left = left_foot.quantity
            final_right = right_foot.quantity
            
            pairs_record = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == request.size,
                    ProductSize.location_name == location.name,
                    ProductSize.inventory_type == 'pair',
                    ProductSize.company_id == self.company_id
                )
            ).first()
            
            total_pairs = pairs_record.quantity if pairs_record else 0
            
            logger.info(f"   🎉 PAR FORMADO EXITOSAMENTE!")
            logger.info(f"      Ubicación: {location.name}")
            logger.info(f"      Cantidad: {request.quantity} par(es)")
            logger.info(f"      Estado final:")
            logger.info(f"         - Izquierdos: {final_left}")
            logger.info(f"         - Derechos: {final_right}")
            logger.info(f"         - Pares: {total_pairs}")
            
            # 6. Construir respuesta
            return ManualPairFormationResponse(
                success=True,
                message=f"✅ {request.quantity} par(es) formado(s) exitosamente en {location.name}",
                pairs_formed=request.quantity,
                location_name=location.name,
                product_info={
                    "reference_code": product.reference_code,
                    "brand": product.brand,
                    "model": product.model,
                    "size": request.size
                },
                inventory_updated={
                    "left_feet_remaining": final_left,
                    "right_feet_remaining": final_right,
                    "pairs_total": total_pairs
                },
                pair_formation_result=result
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"❌ Error formando par manualmente: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error formando par: {str(e)}"
            )
    
    
    # ========== MÉTODO AUXILIAR: EJECUTAR FORMACIÓN ==========
    async def _execute_pair_formation(
        self,
        product_id: int,
        size: str,
        location_name: str,
        quantity: int,
        left_foot: ProductSize,
        right_foot: ProductSize,
        user_id: int,
        notes: Optional[str] = None
    ) -> PairFormationResult:
        """
        Ejecutar la formación de pares (lógica central)
        """
        
        # 1. Restar de pies individuales
        left_foot.quantity -= quantity
        right_foot.quantity -= quantity
        
        # 2. Buscar o crear ProductSize de tipo 'pair'
        pair = self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                ProductSize.inventory_type == 'pair',
                ProductSize.company_id == self.company_id
            )
        ).first()
        
        if pair:
            pair.quantity += quantity
        else:
            pair = ProductSize(
                product_id=product_id,
                size=size,
                quantity=quantity,
                inventory_type='pair',
                location_name=location_name,
                company_id=self.company_id
            )
            self.db.add(pair)
        
        # 3. Registrar en historial
        change_notes = f"Formación manual de {quantity} par(es) en {location_name}. "
        if notes:
            change_notes += f"Notas: {notes}"
        
        inventory_change = InventoryChange(
            product_id=product_id,
            change_type='manual_pair_formation',
            quantity_before=0,
            quantity_after=quantity,
            user_id=user_id,
            company_id=self.company_id,
            notes=change_notes
        )
        self.db.add(inventory_change)
        
        # 4. Commit
        self.db.commit()
        
        return PairFormationResult(
            formed=True,
            pair_product_size_id=pair.id,
            location_name=location_name,
            quantity_formed=quantity,
            remaining_left=left_foot.quantity,
            remaining_right=right_foot.quantity
        )
    
    
    # ========== NUEVO MÉTODO: CONSULTAR OPORTUNIDADES ==========
    async def get_formable_opportunities(
        self,
        request: FormableOpportunitiesRequest
    ) -> FormableOpportunitiesResponse:
        """
        🆕 Obtener lista de oportunidades de formar pares
        
        Retorna productos que tienen ambos pies en la misma ubicación
        y pueden formar pares inmediatamente
        """
        
        try:
            logger.info(f"🔍 Buscando oportunidades de formación de pares...")
            
            # Query para encontrar ubicaciones con ambos pies del mismo producto/talla
            opportunities_query = self.db.query(
                ProductSize.product_id,
                ProductSize.size,
                ProductSize.location_name,
                func.sum(
                    func.case(
                        (ProductSize.inventory_type == 'left_only', ProductSize.quantity),
                        else_=0
                    )
                ).label('left_feet'),
                func.sum(
                    func.case(
                        (ProductSize.inventory_type == 'right_only', ProductSize.quantity),
                        else_=0
                    )
                ).label('right_feet')
            ).filter(
                and_(
                    ProductSize.company_id == self.company_id,
                    ProductSize.inventory_type.in_(['left_only', 'right_only']),
                    ProductSize.quantity > 0
                )
            ).group_by(
                ProductSize.product_id,
                ProductSize.size,
                ProductSize.location_name
            ).having(
                and_(
                    func.sum(
                        func.case(
                            (ProductSize.inventory_type == 'left_only', ProductSize.quantity),
                            else_=0
                        )
                    ) > 0,
                    func.sum(
                        func.case(
                            (ProductSize.inventory_type == 'right_only', ProductSize.quantity),
                            else_=0
                        )
                    ) > 0
                )
            )
            
            # Filtrar por ubicación si se especifica
            if request.location_id:
                location = self.db.query(Location).filter(
                    Location.id == request.location_id
                ).first()
                
                if location:
                    opportunities_query = opportunities_query.filter(
                        ProductSize.location_name == location.name
                    )
            
            results = opportunities_query.all()
            
            logger.info(f"   Encontradas {len(results)} oportunidades potenciales")
            
            # Construir lista de oportunidades
            opportunities = []
            total_formable_pairs = 0
            estimated_value = 0.0
            
            for result in results:
                product_id, size, location_name, left_feet, right_feet = result
                
                # Calcular pares formables
                can_form_pairs = min(left_feet, right_feet)
                
                # Filtrar por mínimo de pares
                if can_form_pairs < request.min_pairs:
                    continue
                
                # Buscar información del producto
                product = self.db.query(Product).filter(
                    Product.id == product_id
                ).first()
                
                if not product:
                    continue
                
                # Buscar ID de ubicación
                location = self.db.query(Location).filter(
                    and_(
                        Location.name == location_name,
                        Location.company_id == self.company_id
                    )
                ).first()
                
                # Calcular valor estimado
                unit_price = float(product.unit_price) if product.unit_price else 0.0
                opportunity_value = unit_price * can_form_pairs
                
                # Determinar prioridad
                priority = "high" if can_form_pairs >= 3 else "medium" if can_form_pairs >= 2 else "low"
                
                opportunity = {
                    "reference_code": product.reference_code,
                    "brand": product.brand,
                    "model": product.model,
                    "size": size,
                    "location": location_name,
                    "location_id": location.id if location else None,
                    "left_feet": left_feet,
                    "right_feet": right_feet,
                    "can_form_pairs": can_form_pairs,
                    "unit_price": unit_price,
                    "total_value": opportunity_value,
                    "priority": priority
                }
                
                opportunities.append(opportunity)
                total_formable_pairs += can_form_pairs
                estimated_value += opportunity_value
            
            # Ordenar por prioridad y valor
            priority_order = {"high": 0, "medium": 1, "low": 2}
            opportunities.sort(
                key=lambda x: (priority_order[x["priority"]], -x["total_value"])
            )
            
            logger.info(f"   ✅ {len(opportunities)} oportunidades válidas encontradas")
            logger.info(f"   📊 Total pares formables: {total_formable_pairs}")
            logger.info(f"   💰 Valor estimado: ${estimated_value:,.0f}")
            
            return FormableOpportunitiesResponse(
                success=True,
                message=f"Se encontraron {len(opportunities)} oportunidades de formación",
                opportunities=opportunities,
                total_opportunities=len(opportunities),
                total_formable_pairs=total_formable_pairs,
                estimated_value=estimated_value
            )
            
        except Exception as e:
            logger.exception(f"❌ Error buscando oportunidades: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error buscando oportunidades: {str(e)}"
            )