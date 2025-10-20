
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from enum import Enum


class VideoProcessingStatus(str, Enum):
    """Estados del procesamiento"""
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIDetectionResult(BaseModel):
    """Resultado de detección de IA (parseado de ai_results_json)"""
    detected_brand: Optional[str] = None
    detected_model: Optional[str] = None
    detected_colors: Optional[List[str]] = None
    detected_sizes: Optional[List[str]] = None
    confidence_score: float = 0.0
    frames_extracted: int = 0
    
    # Información adicional del JSON
    additional_features: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        schema_extra = {
            "example": {
                "detected_brand": "Nike",
                "detected_model": "Air Max 90",
                "detected_colors": ["White", "Black"],
                "detected_sizes": ["39", "40", "41", "42"],
                "confidence_score": 0.92,
                "frames_extracted": 45,
                "additional_features": {
                    "material": "Leather/Mesh",
                    "style": "Running"
                }
            }
        }


class VideoJobResponse(BaseModel):
    """Respuesta de un job de video"""
    id: int
    company_id: int
    
    # Usuario
    processed_by_user_id: int
    processed_by_name: Optional[str] = None
    
    # Archivo
    original_filename: str
    file_size_bytes: int
    video_file_path: Optional[str] = None
    
    # Destino
    warehouse_location_id: int
    warehouse_name: Optional[str] = None
    
    # Input del usuario
    estimated_quantity: int
    product_brand: Optional[str] = None
    product_model: Optional[str] = None
    expected_sizes: Optional[str] = None
    notes: Optional[str] = None
    
    # Estado
    processing_status: str
    microservice_job_id: Optional[str] = None
    retry_count: int = 0
    
    # Resultados IA
    ai_detection: Optional[AIDetectionResult] = None
    
    # Timestamps
    created_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[int] = None
    
    # Error
    error_message: Optional[str] = None
    
    # Producto creado
    created_product_id: Optional[int] = None
    created_inventory_change_id: Optional[int] = None
    
    @property
    def is_completed(self) -> bool:
        return self.processing_status == "completed"
    
    @property
    def is_failed(self) -> bool:
        return self.processing_status == "failed"
    
    @property
    def is_processing(self) -> bool:
        return self.processing_status == "processing"
    
    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "id": 123,
                "company_id": 1,
                "processed_by_user_id": 10,
                "processed_by_name": "Juan Pérez",
                "original_filename": "producto_20250120.mp4",
                "file_size_bytes": 52428800,
                "warehouse_location_id": 1,
                "warehouse_name": "Bodega Central",
                "estimated_quantity": 20,
                "product_brand": "Nike",
                "product_model": "Air Max 90",
                "processing_status": "completed",
                "ai_detection": {
                    "detected_brand": "Nike",
                    "detected_model": "Air Max 90",
                    "confidence_score": 0.92
                },
                "created_at": "2025-01-20T10:30:00"
            }
        }


class CreateVideoJobRequest(BaseModel):
    """Request para crear un job de video"""
    warehouse_location_id: int = Field(..., gt=0)
    estimated_quantity: int = Field(..., gt=0)
    product_brand: Optional[str] = Field(None, max_length=255)
    product_model: Optional[str] = Field(None, max_length=255)
    expected_sizes: Optional[str] = Field(None, description="Tallas separadas por coma: 39,40,41")
    notes: Optional[str] = Field(None, max_length=1000)
    
    class Config:
        schema_extra = {
            "example": {
                "warehouse_location_id": 1,
                "estimated_quantity": 20,
                "product_brand": "Nike",
                "product_model": "Air Max 90",
                "expected_sizes": "39,40,41,42",
                "notes": "Lanzamiento nueva colección"
            }
        }


class VideoJobListResponse(BaseModel):
    """Respuesta de lista de jobs"""
    total: int
    jobs: List[VideoJobResponse]
    
    class Config:
        schema_extra = {
            "example": {
                "total": 45,
                "jobs": []
            }
        }