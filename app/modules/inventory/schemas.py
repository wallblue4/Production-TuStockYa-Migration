from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from decimal import Decimal
from datetime import datetime
from app.shared.schemas.common import BaseResponse

class ProductResponse(BaseResponse):
    product_id: int
    reference_code: str
    description: str
    brand: Optional[str]
    model: Optional[str]
    color_info: Optional[str]
    video_url: Optional[str]
    image_url: Optional[str]
    total_quantity: int
    location_name: str
    unit_price: Decimal
    box_price: Optional[Decimal]
    is_active: int
    sizes: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class InventorySearchParams(BaseModel):
    reference_code: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    location_name: Optional[str] = None
    size: Optional[str] = None
    is_active: Optional[int] = None

class InventoryByRoleParams(BaseModel):
    reference_code: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    is_active: Optional[int] = None

class LocationInfo(BaseModel):
    location_id: int
    location_name: str
    location_type: str

class ProductInfo(BaseModel):
    product_id: int
    reference_code: str
    description: str
    brand: Optional[str]
    model: Optional[str]
    color_info: Optional[str]
    video_url: Optional[str]
    image_url: Optional[str]
    total_quantity: int
    unit_price: Decimal
    box_price: Optional[Decimal]
    is_active: int
    sizes: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

class LocationInventoryResponse(BaseModel):
    location: LocationInfo
    products: List[ProductInfo]
    total_products: int
    total_quantity: int

class GroupedInventoryResponse(BaseModel):
    success: bool
    message: str
    locations: List[LocationInventoryResponse]
    total_locations: int
    total_products: int

class SimpleLocationInventory(BaseModel):
    location_name: str
    location_id: int
    products: List[ProductResponse]

class SimpleInventoryResponse(BaseModel):
    success: bool
    message: str
    locations: List[SimpleLocationInventory]