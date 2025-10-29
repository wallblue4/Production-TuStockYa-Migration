# app/modules/video_processing/service.py

"""
Servicio de procesamiento de video con IA
"""

import logging
import os
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime

from .repository import VideoProcessingRepository
from .ai_client import VideoAIClient
from .schemas import VideoJobResponse, AIDetectionResult
from app.config.settings import settings

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Servicio para procesamiento de videos con IA"""
    
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = VideoProcessingRepository(db)
        self.ai_client = VideoAIClient()
        
        # Directorio temporal para videos
        self.temp_dir = Path("temp/videos")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
    
    async def create_and_process_job(
        self,
        video_file: UploadFile,
        user_id: int,
        warehouse_location_id: int,
        estimated_quantity: int,
        product_brand: Optional[str] = None,
        product_model: Optional[str] = None,
        expected_sizes: Optional[str] = None,
        notes: Optional[str] = None,
        priority: str = "normal",
        save_locally: bool = False  # 🆕 NUEVO PARÁMETRO
    ) -> VideoJobResponse:
        """
        Crear job y procesar video con IA
        
        Pasos:
        1. Validar video
        2. Guardar video temporalmente (OPCIONAL - según save_locally)
        3. Crear job en BD
        4. Enviar a microservicio de IA
        5. Actualizar estado
        
        Args:
            video_file: Archivo de video
            user_id: ID del usuario que procesa
            warehouse_location_id: ID de bodega destino
            estimated_quantity: Cantidad estimada
            product_brand: Marca (opcional)
            product_model: Modelo (opcional)
            expected_sizes: Tallas esperadas
            notes: Notas adicionales
            priority: Prioridad del procesamiento
            save_locally: Si True, guarda video localmente. Si False, solo envía al microservicio
        
        Returns:
            VideoJobResponse con detalles del job creado
        """

        
        start_time = datetime.now()
        logger.info(f"🎬 Iniciando procesamiento de video")
        logger.info(f"   Usuario: {user_id}")
        logger.info(f"   Archivo: {video_file.filename}")
        logger.info(f"   Tamaño: {video_file.size} bytes")
        logger.info(f"   Bodega: {warehouse_location_id}")
        logger.info(f"   💾 Guardar localmente: {save_locally}")  # 🆕
        
        temp_video_path = None
        
        try:
            # Paso 1: Validar video
            self._validate_video(video_file)
            
            # Paso 2: Guardar video temporalmente (CONDICIONAL)
            if save_locally:  # 🆕 CONDICIÓN
                logger.info("💾 Guardando video temporalmente...")
                temp_video_path = await self._save_video_temp(video_file)
                logger.info(f"   ✅ Video guardado en: {temp_video_path}")
            else:
                logger.info("⚡ Modo directo: NO se guardará el video localmente")
                temp_video_path = "Video is no located"  # No hay path local
            
            # Paso 3: Crear job en BD
            logger.info("📝 Creando job en base de datos...")
            
            job = self.repository.create_job(
                company_id=self.company_id,
                user_id=user_id,
                video_filename=video_file.filename,
                video_path=str(temp_video_path) if temp_video_path else None,  # 🆕 NULL si no se guardó
                file_size=video_file.size,
                warehouse_location_id=warehouse_location_id,
                estimated_quantity=estimated_quantity,
                product_brand=product_brand,
                product_model=product_model,
                expected_sizes=expected_sizes,
                notes=notes
            )
            
            self.db.commit()
            logger.info(f"✅ Job creado: ID={job.id}")
            
            # Paso 4: Enviar a microservicio de IA
            logger.info("📤 Enviando a microservicio de IA...")
            
            try:
                # Actualizar estado a processing
                self.repository.update_status(job.id, "processing")
                self.db.commit()
                
                # 🆕 Si no guardamos localmente, resetear el seek del archivo
                if not save_locally:
                    await video_file.seek(0)
                
                # Preparar metadata
                metadata = {
                    "job_db_id": job.id,
                    "warehouse_id": warehouse_location_id,
                    "admin_id": user_id,
                    "estimated_quantity": estimated_quantity,
                    "product_brand": product_brand,
                    "product_model": product_model,
                    "expected_sizes": expected_sizes,
                    "notes": notes,
                    "processing_mode": "direct_without_storage" if not save_locally else "direct_with_training"  # 🆕
                }
                
                # Callback URL
                callback_url = f"{settings.BASE_URL}/api/v1/video-processing/callback/{job.id}"
                
                # Enviar al microservicio
                ai_response = await self.ai_client.process_video(
                    video_file=video_file,
                    job_id=job.id,
                    metadata=metadata,
                    callback_url=callback_url
                )
                
                # Guardar microservice_job_id si viene en la respuesta
                microservice_job_id = ai_response.get('job_id') or ai_response.get('id')
                if microservice_job_id:
                    self.repository.update_status(
                        job.id,
                        "processing",
                        microservice_job_id=str(microservice_job_id)
                    )
                    self.db.commit()
                
                logger.info(f"✅ Video enviado al microservicio")
                logger.info(f"   Microservice Job ID: {microservice_job_id}")
                
            except Exception as e:
                logger.error(f"❌ Error al enviar al microservicio: {str(e)}")
                
                # Actualizar job con error
                self.repository.update_status(
                    job.id,
                    "failed",
                    error_message=str(e)
                )
                self.db.commit()
                
                raise HTTPException(
                    status_code=500,
                    detail=f"Error procesando video: {str(e)}"
                )
            
            # Construir y retornar respuesta
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return self._build_job_response(
                job,
                processed_by_name=None,
                warehouse_name=None
            )
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error general: {str(e)}")
            
            # Limpiar video temporal si existe
            if temp_video_path and temp_video_path.exists():
                try:
                    temp_video_path.unlink()
                    logger.info(f"🗑️  Video temporal eliminado: {temp_video_path}")
                except Exception as cleanup_error:
                    logger.warning(f"⚠️  No se pudo eliminar video temporal: {cleanup_error}")
            
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando video: {str(e)}"
            )
    
    async def handle_callback(
        self,
        job_id: int,
        status: str,
        ai_results: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Manejar callback del microservicio de IA
        
        Args:
            job_id: ID del job
            status: Estado final (completed, failed)
            ai_results: Resultados de IA
            error_message: Mensaje de error si falló
        
        Returns:
            Dict con confirmación
        """
        
        logger.info(f"📥 Callback recibido para job {job_id}")
        logger.info(f"   Status: {status}")
        
        try:
            # Obtener job
            job = self.repository.get_job(job_id, self.company_id)
            
            if not job:
                logger.warning(f"⚠️ Job {job_id} no encontrado")
                raise ValueError(f"Job {job_id} no encontrado")
            
            # Actualizar estado
            final_status = "completed" if status == "completed" else "failed"
            
            self.repository.update_status(
                job_id=job_id,
                status=final_status,
                error_message=error_message
            )
            
            # Actualizar resultados de IA si existen
            if ai_results and status == "completed":
                parsed = self.ai_client.parse_ai_results(ai_results)
                
                self.repository.update_ai_results(
                    job_id=job_id,
                    ai_results=ai_results,
                    confidence_score=parsed['confidence_score'],
                    detected_brand=parsed['detected_brand'],
                    detected_model=parsed['detected_model'],
                    detected_colors=parsed['detected_colors'],
                    detected_sizes=parsed['detected_sizes'],
                    frames_extracted=parsed['frames_extracted']
                )
            
            self.db.commit()
            
            logger.info(f"✅ Job {job_id} actualizado: {final_status}")
            
            return {
                "success": True,
                "job_id": job_id,
                "status": final_status
            }
        
        except Exception as e:
            logger.error(f"❌ Error en callback: {str(e)}")
            self.db.rollback()
            raise
    
    def get_job(self, job_id: int) -> VideoJobResponse:
        """Obtener job por ID con todos los detalles"""
        
        job_data = self.repository.get_job_with_details(job_id, self.company_id)
        
        if not job_data:
            raise HTTPException(404, f"Job {job_id} no encontrado")
        
        return self._build_job_response(
            job_data['job'],
            processed_by_name=job_data.get('processed_by_name'),
            warehouse_name=job_data.get('warehouse_name')
        )
    
    def list_jobs(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        warehouse_location_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Listar jobs con filtros"""
        
        jobs, total = self.repository.list_jobs(
            company_id=self.company_id,
            user_id=user_id,
            status=status,
            warehouse_location_id=warehouse_location_id,
            limit=limit,
            offset=offset
        )
        
        job_responses = [
            self._build_job_response(job)
            for job in jobs
        ]
        
        return {
            "total": total,
            "jobs": job_responses
        }
    
    async def _save_video_temp(self, video_file: UploadFile) -> Path:
        """Guardar video en directorio temporal"""
        
        # Generar nombre único
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{video_file.filename}"
        temp_path = self.temp_dir / safe_filename
        
        # Guardar archivo
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
        
        return temp_path
    
    def _validate_video(self, video_file: UploadFile):
        """Validar archivo de video"""
        
        # Validar tipo de contenido
        if not video_file.content_type.startswith('video/'):
            raise HTTPException(400, "El archivo debe ser un video válido")
        
        # Validar tamaño (100MB máximo)
        max_size = 100 * 1024 * 1024
        if video_file.size > max_size:
            raise HTTPException(400, f"El video no debe superar 100MB (tamaño: {video_file.size / 1024 / 1024:.2f}MB)")
        
        # Validar tamaño mínimo (1KB)
        if video_file.size < 1024:
            raise HTTPException(400, "El archivo de video es demasiado pequeño")
    
    def _build_job_response(
        self,
        job,
        processed_by_name: Optional[str] = None,
        warehouse_name: Optional[str] = None
    ) -> VideoJobResponse:
        """Construir respuesta de job con todos los detalles"""
        
        # Parsear AI results si existen
        ai_detection = None
        if job.ai_results_json:
            try:
                import json
                ai_json = json.loads(job.ai_results_json)
                
                ai_detection = AIDetectionResult(
                    detected_brand=job.detected_brand,
                    detected_model=job.detected_model,
                    detected_colors=job.detected_colors.split(',') if job.detected_colors else None,
                    detected_sizes=job.detected_sizes.split(',') if job.detected_sizes else None,
                    confidence_score=float(job.confidence_score or 0),
                    frames_extracted=job.frames_extracted or 0,
                    additional_features=ai_json.get('features', {})
                )
            except Exception as e:
                logger.warning(f"Error parseando AI results: {str(e)}")
        
        return VideoJobResponse(
            id=job.id,
            company_id=job.company_id,
            processed_by_user_id=job.processed_by_user_id,
            processed_by_name=processed_by_name,
            original_filename=job.original_filename,
            file_size_bytes=job.file_size_bytes,
            video_file_path=job.video_file_path,
            warehouse_location_id=job.warehouse_location_id,
            warehouse_name=warehouse_name,
            estimated_quantity=job.estimated_quantity,
            product_brand=job.product_brand,
            product_model=job.product_model,
            expected_sizes=job.expected_sizes,
            notes=job.notes,
            processing_status=job.processing_status,
            microservice_job_id=job.microservice_job_id,
            retry_count=job.retry_count,
            ai_detection=ai_detection,
            created_at=job.created_at,
            processing_started_at=job.processing_started_at,
            processing_completed_at=job.processing_completed_at,
            processing_time_seconds=job.processing_time_seconds,
            error_message=job.error_message,
            created_product_id=job.created_product_id,
            created_inventory_change_id=job.created_inventory_change_id
        )