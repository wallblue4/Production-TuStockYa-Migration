from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .repository import InventoryRepository
from .schemas import ProductResponse, InventorySearchParams

class InventoryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = InventoryRepository(db)

    async def search_inventory(self, search_params: InventorySearchParams) -> List[ProductResponse]:
        """Buscar productos en inventario según criterios"""
        try:
            products = self.repository.search_products(search_params)
            
            result = []
            for product in products:
                sizes = self.repository.get_product_sizes(product.id)
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
