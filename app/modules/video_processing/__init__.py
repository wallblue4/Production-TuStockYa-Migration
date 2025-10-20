# app/modules/video_processing/__init__.py

"""
Módulo de Procesamiento de Video con IA

Este módulo maneja todo el procesamiento de videos para:
- Registro de inventario con IA
- Extracción automática de información del producto
- Comunicación con microservicio de IA
- Tracking de jobs de procesamiento

Funcionalidades:
- Subir y procesar videos
- Detección de marca, modelo, colores, tallas
- Callbacks asíncronos
- Historial de procesamiento
- Integración con registro de inventario
"""

from .router import router
from .service import VideoProcessingService
from .repository import VideoProcessingRepository
from .ai_client import VideoAIClient

__all__ = [
    "router",
    "VideoProcessingService",
    "VideoProcessingRepository",
    "VideoAIClient"
]