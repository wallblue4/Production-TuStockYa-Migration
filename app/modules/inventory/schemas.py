from pydantic import BaseModel , Field
from typing import Optional, Dict, Any, List ,Literal
from decimal import Decimal
from datetime import datetime
from app.shared.schemas.common import BaseResponse
from app.shared.schemas.inventory_distribution import InventoryTypeEnum ,PairFormationResult




class SizeDetail(BaseModel):
    """Detalle de talla con inventory_type"""
    size: str
    quantity: int
    quantity_exhibition: int = 0
    
    # 🆕 NUEVO CAMPO
    inventory_type: InventoryTypeEnum = InventoryTypeEnum.PAIR
    
    class Config:
        schema_extra = {
            "example": {
                "size": "42",
                "quantity": 10,
                "quantity_exhibition": 2,
                "inventory_type": "pair"
            }
        }

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
    sizes: List[SizeDetail]
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

class FootAvailability(BaseModel):
    """Disponibilidad de un tipo de pie"""
    quantity: int = Field(..., ge=0, description="Cantidad disponible")
    available: bool = Field(..., description="¿Hay stock disponible?")
    
    class Config:
        schema_extra = {
            "example": {
                "quantity": 3,
                "available": True
            }
        }


class IndividualFeetInfo(BaseModel):
    """Información de pies individuales en una ubicación"""
    left: FootAvailability
    right: FootAvailability
    can_form_pair: bool = Field(..., description="¿Se puede formar un par con los disponibles?")
    missing: Optional[Literal['left', 'right', 'none']] = Field(
        None,
        description="Qué pie falta para formar par"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "left": {"quantity": 1, "available": True},
                "right": {"quantity": 0, "available": False},
                "can_form_pair": False,
                "missing": "right"
            }
        }


class PairAvailability(BaseModel):
    """Disponibilidad de pares completos"""
    quantity: int = Field(..., ge=0, description="Cantidad de pares completos")
    quantity_exhibition: int = Field(0, ge=0, description="Pares en exhibición")
    quantity_available_sale: int = Field(..., ge=0, description="Pares disponibles para venta")
    can_sell: bool = Field(..., description="¿Se puede vender ahora?")
    
    @property
    def total_pairs(self) -> int:
        return self.quantity
    
    class Config:
        schema_extra = {
            "example": {
                "quantity": 10,
                "quantity_exhibition": 2,
                "quantity_available_sale": 8,
                "can_sell": True
            }
        }


class LocalAvailability(BaseModel):
    """Disponibilidad en ubicación actual del vendedor"""
    location_id: int
    location_name: str
    location_type: Literal['local', 'bodega']
    
    pairs: PairAvailability
    individual_feet: IndividualFeetInfo
    
    summary: dict = Field(
        ...,
        description="Resumen de estado"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "location_id": 2,
                "location_name": "Local Plaza Norte",
                "location_type": "local",
                "pairs": {
                    "quantity": 0,
                    "quantity_exhibition": 0,
                    "quantity_available_sale": 0,
                    "can_sell": False
                },
                "individual_feet": {
                    "left": {"quantity": 1, "available": True},
                    "right": {"quantity": 0, "available": False},
                    "can_form_pair": False,
                    "missing": "right"
                },
                "summary": {
                    "can_sell_now": False,
                    "reason": "No hay pares completos. Falta pie derecho para formar par.",
                    "action_required": "Solicitar transferencia o formar par"
                }
            }
        }


class LocationInventoryDetail(BaseModel):
    """Detalle de inventario en una ubicación específica"""
    location_id: int
    location_name: str
    location_type: Literal['local', 'bodega']
    distance_km: Optional[float] = Field(None, description="Distancia desde ubicación actual")
    
    pairs: int = Field(0, ge=0)
    left_feet: int = Field(0, ge=0)
    right_feet: int = Field(0, ge=0)
    
    can_form_pairs: int = Field(0, ge=0, description="Pares que se pueden formar en esta ubicación")
    
    status: str = Field(..., description="Estado del inventario en esta ubicación")
    
    class Config:
        schema_extra = {
            "example": {
                "location_id": 1,
                "location_name": "Bodega Central",
                "location_type": "bodega",
                "distance_km": 10.5,
                "pairs": 15,
                "left_feet": 0,
                "right_feet": 0,
                "can_form_pairs": 0,
                "status": "Stock completo disponible"
            }
        }


class FormationOpportunity(BaseModel):
    """Oportunidad de formar pares entre ubicaciones"""
    formable_pairs: int = Field(..., gt=0, description="Cantidad de pares que se pueden formar")
    
    from_locations: List[dict] = Field(
        ...,
        description="Ubicaciones de origen para los pies"
    )
    
    optimal_destination: dict = Field(
        ...,
        description="Ubicación óptima para formar los pares"
    )
    
    estimated_time_hours: float = Field(..., description="Tiempo estimado en horas")
    priority: Literal['low', 'medium', 'high', 'urgent'] = Field(
        ...,
        description="Prioridad de la oportunidad"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "formable_pairs": 3,
                "from_locations": [
                    {
                        "location_id": 2,
                        "location_name": "Local Norte",
                        "type": "left",
                        "quantity": 3
                    },
                    {
                        "location_id": 3,
                        "location_name": "Local Centro",
                        "type": "right",
                        "quantity": 3
                    }
                ],
                "optimal_destination": {
                    "location_id": 2,
                    "location_name": "Local Norte",
                    "reason": "Mayor cantidad de izquierdos disponibles"
                },
                "estimated_time_hours": 1.5,
                "priority": "medium"
            }
        }


class GlobalDistributionResponse(BaseModel):
    """Respuesta completa de distribución global"""
    product_id: int
    reference_code: str
    brand: str
    model: str
    size: str
    
    totals: dict = Field(
        ...,
        description="Totales globales del producto"
    )
    
    by_location: List[LocationInventoryDetail] = Field(
        ...,
        description="Distribución por ubicación"
    )
    
    formation_opportunities: List[FormationOpportunity] = Field(
        default_factory=list,
        description="Oportunidades de formar pares"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "product_id": 123,
                "reference_code": "NIKE-AM90-1234",
                "brand": "Nike",
                "model": "Air Max 90",
                "size": "42",
                "totals": {
                    "pairs": 15,
                    "left_feet": 8,
                    "right_feet": 8,
                    "formable_pairs": 8,
                    "total_potential_pairs": 23,
                    "efficiency_percentage": 65.2
                },
                "by_location": [],
                "formation_opportunities": []
            }
        }


class ActionSuggestion(BaseModel):
    """Sugerencia de acción para el vendedor"""
    priority: Literal['low', 'medium', 'high', 'urgent']
    type: Literal['transfer_pair', 'form_pair', 'wait', 'restock']
    action: str = Field(..., description="Descripción de la acción sugerida")
    estimated_time_minutes: int = Field(..., description="Tiempo estimado en minutos")
    cost_estimate: Optional[Decimal] = Field(None, description="Costo estimado de la operación")
    
    steps: List[str] = Field(
        default_factory=list,
        description="Pasos para ejecutar la acción"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "priority": "high",
                "type": "transfer_pair",
                "action": "Solicitar par completo desde Bodega Central",
                "estimated_time_minutes": 15,
                "cost_estimate": 5000,
                "steps": [
                    "Crear solicitud de transferencia",
                    "Bodeguero prepara el par",
                    "Corredor transporta",
                    "Recibes en tu local"
                ]
            }
        }


class ScanResponseEnhanced(BaseModel):
    """Respuesta mejorada del scanner con información de pies separados"""
    success: bool
    scan_timestamp: str
    scanned_by: dict
    
    # Información del producto
    product: dict
    
    # Disponibilidad local
    local_availability: LocalAvailability
    
    # Distribución global
    global_distribution: dict
    
    # Sugerencias
    suggestions: List[ActionSuggestion]
    
    # Metadata
    processing_time_ms: float
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "scan_timestamp": "2025-01-20T10:30:00",
                "scanned_by": {
                    "user_id": 5,
                    "name": "Carlos Mendoza",
                    "role": "seller",
                    "location_id": 2
                },
                "product": {
                    "product_id": 123,
                    "reference_code": "NIKE-AM90-1234",
                    "brand": "Nike",
                    "model": "Air Max 90",
                    "size": "42"
                },
                "local_availability": {},
                "global_distribution": {},
                "suggestions": [],
                "processing_time_ms": 245.5
            }
        }

class ManualPairFormationRequest(BaseModel):
    """
    Request para formar pares manualmente
    
    Usado cuando:
    - Ambos pies están en la misma ubicación
    - No se formó par automáticamente
    - Admin/vendedor decide formar manualmente
    """
    reference_code: str = Field(..., description="Código de referencia del producto")
    size: str = Field(..., description="Talla")
    location_id: int = Field(..., description="ID de ubicación donde formar el par")
    quantity: int = Field(1, ge=1, description="Cantidad de pares a formar")
    notes: Optional[str] = Field(None, max_length=500, description="Notas adicionales")
    
    class Config:
        json_schema_extra = {
            "example": {
                "reference_code": "NK-AM90-BLK-001",
                "size": "42",
                "location_id": 2,
                "quantity": 1,
                "notes": "Formación manual solicitada por vendedor"
            }
        }


class ManualPairFormationResponse(BaseResponse):
    """
    Respuesta de formación manual de pares
    """
    pairs_formed: int
    location_name: str
    product_info: dict
    inventory_updated: dict
    pair_formation_result: PairFormationResult
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Par formado exitosamente",
                "pairs_formed": 1,
                "location_name": "Local Centro",
                "product_info": {
                    "reference_code": "NK-AM90-BLK-001",
                    "brand": "Nike",
                    "model": "Air Max 90",
                    "size": "42"
                },
                "inventory_updated": {
                    "left_feet_remaining": 0,
                    "right_feet_remaining": 0,
                    "pairs_total": 5
                },
                "pair_formation_result": {
                    "formed": True,
                    "quantity_formed": 1,
                    "location_name": "Local Centro"
                }
            }
        }


class FormableOpportunitiesRequest(BaseModel):
    """
    Request para consultar oportunidades de formación
    """
    location_id: Optional[int] = Field(None, description="Filtrar por ubicación específica")
    min_pairs: int = Field(1, ge=1, description="Mínimo de pares formables para incluir")


class FormableOpportunitiesResponse(BaseResponse):
    """
    Lista de oportunidades de formar pares
    """
    opportunities: List[dict]
    total_opportunities: int
    total_formable_pairs: int
    estimated_value: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Oportunidades encontradas",
                "opportunities": [
                    {
                        "reference_code": "NK-AM90-001",
                        "brand": "Nike",
                        "model": "Air Max 90",
                        "size": "42",
                        "location": "Local Centro",
                        "location_id": 2,
                        "left_feet": 2,
                        "right_feet": 2,
                        "can_form_pairs": 2,
                        "unit_price": 150000,
                        "total_value": 300000,
                        "priority": "high"
                    }
                ],
                "total_opportunities": 5,
                "total_formable_pairs": 12,
                "estimated_value": 1800000
            }
        }