# app/modules/transfers_new/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List ,Literal
from decimal import Decimal
from datetime import datetime
from enum import Enum
from app.shared.schemas.common import BaseResponse
from app.shared.schemas.inventory_distribution import OppositeFootInfo , InventoryTypeEnum

class TransferRequestCreate(BaseModel):
    source_location_id: int = Field(..., description="ID de ubicación origen")
    destination_location_id: int = Field(..., description="ID de ubicación destino")
    sneaker_reference_code: str = Field(..., description="Código de referencia del producto")
    brand: str = Field(..., description="Marca del producto")
    model: str = Field(..., description="Modelo del producto")
    size: str = Field(..., description="Talla del producto")
    quantity: int = Field(..., gt=0, description="Cantidad a transferir")
    purpose: str = Field(..., description="Propósito: cliente, restock, exhibition")
    pickup_type: str = Field(..., description="Tipo de recogida: vendedor, corredor")
    destination_type: str = Field(default="bodega", description="Tipo destino: bodega, exhibicion")
    notes: Optional[str] = Field(None, max_length=500, description="Notas adicionales")
    inventory_type: InventoryTypeEnum = Field(
        default=InventoryTypeEnum.PAIR,
        description="Tipo de inventario a transferir: pair, left_only, right_only"
    )
    @validator('inventory_type')
    def validate_inventory_type(cls, v, values):
        """Validar que el tipo tenga sentido según el propósito"""
        purpose = values.get('purpose')
        
        # Si es para venta, debe ser 'pair'
        if purpose == 'sale' and v != 'pair':
            raise ValueError("Las ventas requieren un par completo")
        
        # Si es para exhibición, puede ser left o right
        if purpose == 'exhibition' and v == 'pair':
            raise ValueError("La exhibición debe especificar left_only o right_only")
        
        return v

class TransferRequestResponse(BaseResponse):
    transfer_request_id: int
    status: str
    estimated_time: str
    priority: str
    next_steps: List[str]
    reservation_expires_at: Optional[str] = None
    inventory_type: str = Field(default="pair")
    opposite_foot_info: Optional[OppositeFootInfo] = Field(
        None,
        description="Información sobre pie opuesto en destino (si aplica)"
    )
    pair_formation_potential: Optional[Dict[str, Any]] = Field(
        None,
        description="Potencial de formar pares automáticamente"
    )

class MyTransferRequestsResponse(BaseResponse):
    my_requests: List[Dict[str, Any]]
    summary: Dict[str, Any]
    vendor_info: Dict[str, Any]
    workflow_info: Dict[str, Any]

class ReceptionConfirmation(BaseModel):
    received_quantity: int = Field(..., gt=0, description="Cantidad recibida")
    condition_ok: bool = Field(..., description="Condición del producto OK")
    notes: str = Field("", description="Notas de recepción")

class ReturnRequestCreate(BaseModel):
    """Schema para crear solicitud de devolución"""
    original_transfer_id: int = Field(..., description="ID de la transferencia original")
    reason: str = Field(..., description="Motivo: no_sale, defect, wrong_product, customer_rejection")
    quantity_to_return: int = Field(..., gt=0, description="Cantidad a devolver")
    pickup_type: str = Field(
        "corredor",
        description="Método de devolución: 'corredor' (corredor recoge) o 'vendedor' (llevas tú mismo)"
    )
    product_condition: str = Field("good", description="Estado: good, damaged, unusable")
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('reason')
    def validate_reason(cls, v):
        allowed = ['no_sale', 'defect', 'wrong_product', 'customer_rejection', 'overstock']
        if v not in allowed:
            raise ValueError(f'Razón debe ser una de: {allowed}')
        return v
    
    @validator('product_condition')
    def validate_condition(cls, v):
        allowed = ['good', 'damaged', 'unusable']
        if v not in allowed:
            raise ValueError(f'Condición debe ser una de: {allowed}')
        return v

    @validator('pickup_type')
    def validate_pickup_type(cls, v):
        allowed_types = ['corredor', 'vendedor']
        if v not in allowed_types:
            raise ValueError(f'pickup_type debe ser: {allowed_types}')
        return v

        class Config:
            json_schema_extra = {
                "example": {
                    "original_transfer_id": 123,
                    "reason": "no_sale",
                    "quantity_to_return": 1,
                    "product_condition": "good",
                    "pickup_type": "vendedor",
                    "notes": "Cliente no lo compró, lo llevaré yo mismo a bodega"
                }
            }


class ReturnRequestResponse(BaseResponse):
    """Respuesta al crear devolución"""
    return_id: int
    original_transfer_id: int
    status: str
    pickup_type: str
    estimated_return_time: str
    workflow_steps: List[str]
    priority: str = "normal"

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Devolución creada - Llevarás el producto tú mismo",
                "return_id": 456,
                "original_transfer_id": 123,
                "status": "pending",
                "pickup_type": "vendedor",
                "estimated_return_time": "1-2 horas",
                "workflow_steps": [
                    "Bodeguero aceptará la solicitud",
                    "Llevarás el producto a bodega personalmente",
                    "Bodeguero confirmará recepción",
                    "Inventario se restaurará"
                ],
                "return_type": "return",
                "priority": "normal",
                "next_action": "Esperar aceptación de bodeguero"
            }
        }

class ReturnReceptionConfirmation(BaseModel):
    """Confirmación de recepción por bodeguero"""
    received_quantity: int = Field(..., gt=0)
    product_condition: str = Field(...)
    return_to_inventory: bool = Field(True)
    quality_check_passed: bool = Field(True)
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('product_condition')
    def validate_condition(cls, v):
        allowed = ['good', 'damaged', 'unusable']
        if v not in allowed:
            raise ValueError(f'Condición debe ser: {allowed}')
        return v

class ReturnReceptionResponse(BaseResponse):
    """Respuesta al confirmar recepción de return"""
    return_id: int
    original_transfer_id: int
    received_quantity: int
    product_condition: str
    inventory_restored: bool
    warehouse_location: str
    inventory_change: Dict[str, Any]

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
    reference_code: str = Field(..., description="Código de producto")
    size: str = Field(..., description="Talla")
    foot_side: Literal['left', 'right'] = Field(..., description="Pie izquierdo o derecho")
    quantity: int = Field(1, ge=1, description="Cantidad de pies a transferir")
    purpose: Literal['exhibition', 'pair_formation', 'rebalancing'] = Field(
        ...,
        description="Propósito de la transferencia"
    )
    notes: Optional[str] = Field(None, max_length=500)
    
    @property
    def inventory_type(self) -> str:
        """Convertir foot_side a inventory_type"""
        return 'left_only' if self.foot_side == 'left' else 'right_only'


# ========== NUEVO SCHEMA: RESPUESTA DE AUTO-FORMACIÓN ==========
class PairFormationResult(BaseModel):
    """
    Resultado de la formación automática de pares
    """
    formed: bool = Field(..., description="Si se formó un par")
    pair_id: Optional[int] = Field(None, description="ID del ProductSize pair creado")
    left_transfer_id: int = Field(..., description="ID del transfer izquierdo")
    right_transfer_id: int = Field(..., description="ID del transfer derecho")
    location_name: str = Field(..., description="Ubicación donde se formó")
    quantity_formed: int = Field(..., description="Cantidad de pares formados")
    
    class Config:
        schema_extra = {
            "example": {
                "formed": True,
                "pair_id": 456,
                "left_transfer_id": 123,
                "right_transfer_id": 124,
                "location_name": "Local Centro",
                "quantity_formed": 1
            }
        }


# ========== SCHEMA: SUGERENCIA DE TRANSFERENCIA ==========
class TransferSuggestion(BaseModel):
    """
    Sugerencia inteligente para completar pares
    """
    from_location: str
    to_location: str
    foot_needed: Literal['left', 'right']
    quantity_available: int
    priority: Literal['high', 'medium', 'low']
    reason: str
    estimated_time: Optional[str] = None

class SingleFootTransferResponse(BaseResponse):
    """Respuesta al crear transferencia de pie individual"""
    transfer_request_id: int
    inventory_type: str
    foot_side: str
    opposite_foot_available: bool
    can_auto_form_pair: bool
    quantity_formable: int
    status: str
    next_steps: List[str]
