from pydantic import BaseModel, Field, validator
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from app.shared.schemas.common import BaseResponse

# ===== MAYOREO SCHEMAS =====

class MayoreoCreate(BaseModel):
    """Schema para crear un producto de mayoreo"""
    modelo: str = Field(..., min_length=1, max_length=255, description="Modelo del producto")
    foto: Optional[str] = Field(None, description="URL o ruta de la imagen")
    tallas: Optional[str] = Field(None, max_length=255, description="Tallas disponibles")
    cantidad_cajas_disponibles: int = Field(0, ge=0, description="Cantidad de cajas disponibles")
    pares_por_caja: int = Field(..., gt=0, description="Pares por caja")
    precio: Decimal = Field(..., gt=0, description="Precio por par")
    
    @validator('modelo')
    def validate_modelo(cls, v):
        if not v or not v.strip():
            raise ValueError('El modelo no puede estar vacío')
        return v.strip()

class MayoreoUpdate(BaseModel):
    """Schema para actualizar un producto de mayoreo"""
    modelo: Optional[str] = Field(None, min_length=1, max_length=255)
    foto: Optional[str] = None
    tallas: Optional[str] = Field(None, max_length=255)
    cantidad_cajas_disponibles: Optional[int] = Field(None, ge=0)
    pares_por_caja: Optional[int] = Field(None, gt=0)
    precio: Optional[Decimal] = Field(None, gt=0)
    is_active: Optional[bool] = None
    
    @validator('modelo')
    def validate_modelo(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('El modelo no puede estar vacío')
        return v.strip() if v else v

class MayoreoResponse(BaseResponse):
    """Schema de respuesta para productos de mayoreo"""
    id: int
    user_id: int
    company_id: int
    modelo: str
    foto: Optional[str]
    tallas: Optional[str]
    cantidad_cajas_disponibles: int
    pares_por_caja: int
    precio: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

class MayoreoSearchParams(BaseModel):
    """Schema para parámetros de búsqueda de mayoreo"""
    modelo: Optional[str] = None
    tallas: Optional[str] = None
    is_active: Optional[bool] = None

# ===== VENTA MAYOREO SCHEMAS =====

class VentaMayoreoCreate(BaseModel):
    """Schema para crear una venta de mayoreo"""
    mayoreo_id: int = Field(..., gt=0, description="ID del producto de mayoreo")
    cantidad_cajas_vendidas: int = Field(..., gt=0, description="Cantidad de cajas vendidas")
    precio_unitario_venta: Decimal = Field(..., gt=0, description="Precio unitario de venta")
    notas: Optional[str] = Field(None, description="Notas adicionales de la venta")
    
    @validator('cantidad_cajas_vendidas')
    def validate_cantidad_cajas_vendidas(cls, v):
        if v <= 0:
            raise ValueError('La cantidad de cajas vendidas debe ser mayor a 0')
        return v
    
    @validator('precio_unitario_venta')
    def validate_precio_unitario_venta(cls, v):
        if v <= 0:
            raise ValueError('El precio unitario de venta debe ser mayor a 0')
        return v

class VentaMayoreoResponse(BaseResponse):
    """Schema de respuesta para ventas de mayoreo"""
    id: int
    mayoreo_id: int
    user_id: int
    company_id: int
    cantidad_cajas_vendidas: int
    precio_unitario_venta: Decimal
    total_venta: Decimal
    fecha_venta: datetime
    notas: Optional[str]
    created_at: datetime

class VentaMayoreoWithProduct(VentaMayoreoResponse):
    """Schema de respuesta para ventas de mayoreo con información del producto"""
    mayoreo_producto: MayoreoResponse

class VentaMayoreoSearchParams(BaseModel):
    """Schema para parámetros de búsqueda de ventas de mayoreo"""
    mayoreo_id: Optional[int] = None
    fecha_desde: Optional[datetime] = None
    fecha_hasta: Optional[datetime] = None
    cantidad_minima: Optional[int] = None
    cantidad_maxima: Optional[int] = None

# ===== RESPONSE SCHEMAS =====

class MayoreoListResponse(BaseModel):
    """Schema de respuesta para listado de productos de mayoreo"""
    success: bool
    message: str
    data: List[MayoreoResponse]
    total: int

class VentaMayoreoListResponse(BaseModel):
    """Schema de respuesta para listado de ventas de mayoreo"""
    success: bool
    message: str
    data: List[VentaMayoreoWithProduct]
    total: int

class MayoreoStatsResponse(BaseModel):
    """Schema de respuesta para estadísticas de mayoreo"""
    success: bool
    message: str
    total_productos: int
    total_cajas_disponibles: int
    valor_total_inventario: Decimal
    total_ventas: int
    valor_total_ventas: Decimal
