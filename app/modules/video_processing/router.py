# app/modules/video_processing/router.py

"""
Router para procesamiento de video con IA
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Body
from sqlalchemy.orm import Session
from typing import Optional

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from app.shared.database.models import User

from .service import VideoProcessingService
from .schemas import (
    VideoJobResponse,
    VideoJobListResponse,
    CreateVideoJobRequest
)

router = APIRouter()


@router.post("/process", response_model=VideoJobResponse)
async def process_video(
    # Datos del formulario
    warehouse_location_id: int = Form(..., description="ID de bodega destino", gt=0),
    estimated_quantity: int = Form(..., description="Cantidad estimada", gt=0),
    product_brand: Optional[str] = Form(None, description="Marca del producto"),
    product_model: Optional[str] = Form(None, description="Modelo del producto"),
    expected_sizes: Optional[str] = Form(None, description="Tallas esperadas (separadas por coma)"),
    notes: Optional[str] = Form(None, description="Notas adicionales"),
    
    # Archivo de video
    video_file: UploadFile = File(..., description="Video del producto"),
    
    # Auth
    current_user: User = Depends(require_roles(["administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Procesar video con IA para extracción de información del producto
    
    **Funcionalidad:**
    - Subir video del producto
    - Procesamiento automático con IA
    - Extracción de: marca, modelo, colores, tallas
    - Retorna job_id para seguimiento
    
    **Requisitos del video:**
    - Formato: MP4, MOV, AVI
    - Tamaño máximo: 100MB
    - Duración recomendada: 5 a 6 segundos
    - Mostrar producto desde múltiples ángulos
    - Etiquetas y tallas visibles
    
    **Proceso:**
    1. Video se guarda temporalmente
    2. Se crea job en BD
    3. Video se envía a microservicio de IA
    4. Procesamiento asíncrono
    5. Callback actualiza resultados
    
    **Retorna:**
    - job_id: ID para consultar estado
    - status: Estado actual (processing, completed, failed)
    - ai_detection: Resultados de IA (cuando complete)
    
    **Ejemplo de uso:**
```python
    # Subir video
    response = await process_video(
        video_file=video,
        warehouse_location_id=1,
        estimated_quantity=20,
        product_brand="Nike",
        product_model="Air Max 90"
    )
    
    job_id = response['id']
    
    # Consultar estado después
    status = await get_job_status(job_id)
```
    """
    
    service = VideoProcessingService(db, current_company_id)
    
    return await service.create_and_process_job(
        video_file=video_file,
        user_id=current_user.id,
        warehouse_location_id=warehouse_location_id,
        estimated_quantity=estimated_quantity,
        product_brand=product_brand,
        product_model=product_model,
        expected_sizes=expected_sizes,
        notes=notes,
        priority="normal"
    )


@router.get("/jobs/{job_id}", response_model=VideoJobResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(require_roles(["administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Consultar estado de un job de procesamiento
    
    **Retorna:**
    - Estado actual del procesamiento
    - Resultados de IA (si ya completó)
    - Tiempo de procesamiento
    - Errores (si falló)
    - Producto creado (si ya se usó para crear inventario)
    """
    
    service = VideoProcessingService(db, current_company_id)
    return service.get_job(job_id)


@router.get("/jobs", response_model=VideoJobListResponse)
async def list_jobs(
    status: Optional[str] = Query(None, description="Filtrar por estado: processing, completed, failed"),
    warehouse_location_id: Optional[int] = Query(None, description="Filtrar por bodega"),
    limit: int = Query(50, ge=1, le=100, description="Límite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginación"),
    
    current_user: User = Depends(require_roles(["administrador", "boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Listar jobs de procesamiento de video
    
    **Filtros disponibles:**
    - status: Estado del procesamiento
    - warehouse_location_id: Bodega específica
    - limit/offset: Paginación
    
    **Casos de uso:**
    - Ver historial de videos procesados
    - Monitorear videos en procesamiento
    - Revisar videos fallidos
    - Auditoría de procesamiento
    """
    
    service = VideoProcessingService(db, current_company_id)
    
    # Si el usuario no es boss, filtrar solo sus jobs
    user_filter = None if current_user.role == "boss" else current_user.id
    
    result = service.list_jobs(
        user_id=user_filter,
        status=status,
        warehouse_location_id=warehouse_location_id,
        limit=limit,
        offset=offset
    )
    
    return VideoJobListResponse(
        total=result['total'],
        jobs=result['jobs']
    )


@router.post("/callback/{job_id}")
async def video_processing_callback(
    job_id: int,
    callback_data: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Callback del microservicio de IA
    
    **ENDPOINT INTERNO** - Llamado por el microservicio de IA
    
    **Recibe:**
    - status: completed o failed
    - ai_results: Resultados de detección
    - error_message: Mensaje si falló
    
    **Actualiza:**
    - Estado del job
    - Resultados de IA en BD
    - Timestamps de completado
    """
    
    # TODO: Validar que la petición venga del microservicio
    # Usar API key o firma para seguridad
    
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📥 Callback recibido para job {job_id}")
    logger.info(f"   Data: {callback_data}")
    
    # Obtener company_id del job
    from app.modules.video_processing.repository import VideoProcessingRepository
    repo = VideoProcessingRepository(db)
    from app.shared.database.models import VideoProcessingJob
    
    job = db.query(
        VideoProcessingJob
    ).filter(VideoProcessingJob.id == job_id).first()
    
    if not job:
        logger.warning(f"⚠️ Job {job_id} no encontrado en callback")
        return {"success": False, "error": "Job not found"}
    
    service = VideoProcessingService(db, job.company_id)
    
    try:
        result = await service.handle_callback(
            job_id=job_id,
            status=callback_data.get('status'),
            ai_results=callback_data.get('ai_results') or callback_data.get('results'),
            error_message=callback_data.get('error_message')
        )
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Error en callback: {str(e)}")
        return {"success": False, "error": str(e)}


@router.get("/health")
async def check_health():
    """Health check del módulo de video processing"""
    
    from .ai_client import VideoAIClient
    
    ai_client = VideoAIClient()
    microservice_available = await ai_client.check_health()
    
    return {
        "service": "video_processing",
        "status": "healthy",
        "microservice_status": "available" if microservice_available else "unavailable",
        "microservice_url": ai_client.base_url,
        "features": [
            "Procesamiento de video con IA",
            "Detección automática de marca/modelo",
            "Extracción de características",
            "Callbacks asíncronos",
            "Tracking de jobs"
        ]
    }