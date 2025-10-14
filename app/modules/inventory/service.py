from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .repository import InventoryRepository
from .schemas import ProductResponse, InventorySearchParams, InventoryByRoleParams, GroupedInventoryResponse, LocationInventoryResponse, LocationInfo, ProductInfo, SimpleInventoryResponse, SimpleLocationInventory

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
