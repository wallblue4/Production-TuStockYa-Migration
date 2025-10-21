# app/shared/schemas/inventory_distribution.py

"""
Schemas para manejo de distribución de inventario con pies separados
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Literal
from enum import Enum


class InventoryTypeEnum(str, Enum):
    """Tipos de inventario soportados"""
    PAIR = "pair"
    LEFT_ONLY = "left_only"
    RIGHT_ONLY = "right_only"

class FootSide(str, Enum):
    """Lado del pie"""
    left = "left"
    right = "right"



class LocationQuantity(BaseModel):
    """
    Cantidad de inventario en una ubicación específica
    
    Usado para especificar distribución al registrar inventario
    """
    location_id: int = Field(..., gt=0, description="ID de la ubicación (local o bodega)")
    quantity: int = Field(..., gt=0, description="Cantidad en esta ubicación")
    notes: Optional[str] = Field(None, max_length=200, description="Notas opcionales")
    
    class Config:
        schema_extra = {
            "example": {
                "location_id": 1,
                "quantity": 10,
                "notes": "Para exhibición principal"
            }
        }


class SizeDistributionEntry(BaseModel):
    """
    Distribución de una talla específica entre ubicaciones
    
    Permite especificar:
    - Pares completos en diferentes ubicaciones
    - Pies izquierdos individuales en ubicaciones específicas
    - Pies derechos individuales en ubicaciones específicas
    """
    size: str = Field(..., max_length=10, description="Talla del producto (ej: '42', '9.5')")
    
    # Distribución de pares completos
    pairs: List[LocationQuantity] = Field(
        default_factory=list,
        description="Pares completos por ubicación"
    )
    
    # Distribución de pies individuales
    left_feet: List[LocationQuantity] = Field(
        default_factory=list,
        description="Pies izquierdos por ubicación (generalmente para exhibición)"
    )
    
    right_feet: List[LocationQuantity] = Field(
        default_factory=list,
        description="Pies derechos por ubicación (generalmente para exhibición)"
    )
    
    @validator('size')
    def validate_size(cls, v):
        """Validar formato de talla"""
        if not v or not v.strip():
            raise ValueError("La talla no puede estar vacía")
        return v.strip()
    
    @validator('left_feet', 'right_feet')
    def validate_balance(cls, v, values):
        """
        Validar que el total de izquierdos = total de derechos
        
        Regla de negocio: Por cada izquierdo debe existir un derecho en alguna ubicación
        """
        # Esta validación se hará a nivel global en el endpoint
        # Aquí solo validamos que cada lista sea válida
        return v
    
    @property
    def total_pairs(self) -> int:
        """Total de pares completos"""
        return sum(item.quantity for item in self.pairs)
    
    @property
    def total_left_feet(self) -> int:
        """Total de pies izquierdos"""
        return sum(item.quantity for item in self.left_feet)
    
    @property
    def total_right_feet(self) -> int:
        """Total de pies derechos"""
        return sum(item.quantity for item in self.right_feet)
    
    @property
    def total_shoes(self) -> int:
        """Total de zapatos (pares * 2 + individuales)"""
        return (self.total_pairs * 2) + self.total_left_feet + self.total_right_feet
    
    def validate_global_balance(self) -> bool:
        """
        Validar que izquierdos = derechos globalmente
        
        Returns:
            True si está balanceado, False si no
        """
        return self.total_left_feet == self.total_right_feet
    
    class Config:
        schema_extra = {
            "example": {
                "size": "42",
                "pairs": [
                    {"location_id": 1, "quantity": 10},
                    {"location_id": 5, "quantity": 3}
                ],
                "left_feet": [
                    {"location_id": 2, "quantity": 2},
                    {"location_id": 3, "quantity": 1}
                ],
                "right_feet": [
                    {"location_id": 4, "quantity": 2},
                    {"location_id": 6, "quantity": 1}
                ]
            }
        }


class ProductSizeDetail(BaseModel):
    """
    Detalle de una talla de producto incluyendo tipo de inventario
    
    Respuesta enriquecida que muestra la distribución actual
    """
    size: str
    inventory_type: InventoryTypeEnum
    quantity: int
    quantity_exhibition: int = 0
    location_name: str
    location_id: Optional[int] = None
    
    class Config:
        schema_extra = {
            "example": {
                "size": "42",
                "inventory_type": "pair",
                "quantity": 10,
                "quantity_exhibition": 2,
                "location_name": "Bodega Central",
                "location_id": 1
            }
        }


class InventoryDistributionSummary(BaseModel):
    """
    Resumen de distribución de inventario para un producto-talla
    
    Muestra el estado actual de distribución entre ubicaciones
    """
    product_id: int
    reference_code: str
    brand: str
    model: str
    size: str
    
    # Totales globales
    total_pairs: int
    total_left_feet: int
    total_right_feet: int
    formable_pairs: int  # min(left_feet, right_feet)
    
    # Detalle por ubicación
    distribution: List[ProductSizeDetail]
    
    @property
    def total_potential_pairs(self) -> int:
        """Total de pares que se pueden vender (actuales + formables)"""
        return self.total_pairs + self.formable_pairs
    
    @property
    def is_balanced(self) -> bool:
        """Verifica si hay balance entre izquierdos y derechos"""
        return self.total_left_feet == self.total_right_feet
    
    @property
    def efficiency_percentage(self) -> float:
        """
        Porcentaje de eficiencia de inventario
        
        Eficiencia = (pares / pares_potenciales) * 100
        100% = Todo está en pares completos
        """
        if self.total_potential_pairs == 0:
            return 0.0
        return round((self.total_pairs / self.total_potential_pairs) * 100, 2)
    
    class Config:
        schema_extra = {
            "example": {
                "product_id": 100,
                "reference_code": "AIR-MAX-90-WHT",
                "brand": "Nike",
                "model": "Air Max 90",
                "size": "42",
                "total_pairs": 15,
                "total_left_feet": 3,
                "total_right_feet": 3,
                "formable_pairs": 3,
                "distribution": [
                    {
                        "size": "42",
                        "inventory_type": "pair",
                        "quantity": 15,
                        "location_name": "Bodega Central",
                        "location_id": 1
                    },
                    {
                        "size": "42",
                        "inventory_type": "left_only",
                        "quantity": 3,
                        "location_name": "Local Plaza",
                        "location_id": 2
                    },
                    {
                        "size": "42",
                        "inventory_type": "right_only",
                        "quantity": 3,
                        "location_name": "Local Centro",
                        "location_id": 3
                    }
                ]
            }
        }
class SingleFootTransferRequest(BaseModel):
    """
    Request especializado para transferir pies individuales
    
    Casos de uso:
    - Mover pie para exhibición
    - Enviar pie para formar par en otro local
    - Rebalancear inventario entre ubicaciones
    """
    source_location_id: int = Field(..., description="Ubicación origen")
    destination_location_id: int = Field(..., description="Ubicación destino")
    sneaker_reference_code: str = Field(..., description="Código de producto")
    size: str = Field(..., description="Talla")
    foot_side: FootSide = Field(..., description="Pie izquierdo o derecho")
    quantity: int = Field(1, ge=1, description="Cantidad de pies a transferir")
    purpose: Literal['exhibition', 'pair_formation', 'rebalancing'] = Field(
        ...,
        description="Propósito de la transferencia"
    )
    pickup_type: str = Field(..., description="Tipo de recogida: vendedor, corredor")
    notes: Optional[str] = Field(None, max_length=500)
    
    @property
    def inventory_type(self) -> str:
        """Convertir foot_side a inventory_type"""
        return 'left_only' if self.foot_side == FootSide.left else 'right_only'
    
    @property
    def brand(self) -> str:
        """Extraer marca del código de referencia"""
        # Asumiendo formato: BRAND-MODEL-COLOR-NUMBER
        parts = self.sneaker_reference_code.split('-')
        return parts[0] if parts else ""
    
    @property
    def model(self) -> str:
        """Extraer modelo del código de referencia"""
        parts = self.sneaker_reference_code.split('-')
        return '-'.join(parts[1:-2]) if len(parts) > 2 else ""


class PairFormationResult(BaseModel):
    """
    Resultado de la formación automática de pares
    """
    formed: bool = Field(..., description="Si se formó un par")
    pair_product_size_id: Optional[int] = Field(None, description="ID del ProductSize pair creado")
    left_transfer_id: Optional[int] = Field(None, description="ID del transfer izquierdo")
    right_transfer_id: Optional[int] = Field(None, description="ID del transfer derecho")
    location_name: str = Field(..., description="Ubicación donde se formó")
    quantity_formed: int = Field(..., description="Cantidad de pares formados")
    remaining_left: int = Field(0, description="Pies izquierdos restantes")
    remaining_right: int = Field(0, description="Pies derechos restantes")
    
    class Config:
        json_schema_extra = {
            "example": {
                "formed": True,
                "pair_product_size_id": 456,
                "left_transfer_id": 123,
                "right_transfer_id": 124,
                "location_name": "Local Centro",
                "quantity_formed": 1,
                "remaining_left": 0,
                "remaining_right": 0
            }
        }


class TransferSuggestion(BaseModel):
    """
    Sugerencia inteligente para completar pares
    """
    from_location: str
    from_location_id: int
    to_location: str
    to_location_id: int
    foot_needed: FootSide
    quantity_available: int
    priority: Literal['high', 'medium', 'low']
    reason: str
    estimated_time: Optional[str] = None


class OppositeFootInfo(BaseModel):
    """
    Información sobre el pie opuesto disponible
    """
    exists: bool
    product_size_id: Optional[int] = None
    inventory_type: Optional[InventoryTypeEnum] = None
    quantity: int = 0
    location_name: Optional[str] = None
    can_form_pairs: bool = False