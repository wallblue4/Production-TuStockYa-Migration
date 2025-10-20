
"""
Repository para VideoProcessingJob
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from typing import List, Optional, Tuple
from datetime import datetime
import json

from app.shared.database.models import VideoProcessingJob, User, Location


class VideoProcessingRepository:
    """Repository para gestión de jobs de video"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_job(
        self,
        company_id: int,
        user_id: int,
        video_filename: str,
        video_path: str,
        file_size: int,
        warehouse_location_id: int,
        estimated_quantity: int,
        product_brand: Optional[str] = None,
        product_model: Optional[str] = None,
        expected_sizes: Optional[str] = None,
        notes: Optional[str] = None
    ) -> VideoProcessingJob:
        """Crear nuevo job de procesamiento"""
        
        job = VideoProcessingJob(
            company_id=company_id,
            processed_by_user_id=user_id,
            video_file_path=video_path,
            original_filename=video_filename,
            file_size_bytes=file_size,
            warehouse_location_id=warehouse_location_id,
            estimated_quantity=estimated_quantity,
            product_brand=product_brand,
            product_model=product_model,
            expected_sizes=expected_sizes,
            notes=notes,
            processing_status="pending",
            retry_count=0,
            created_at=datetime.now()
        )
        
        self.db.add(job)
        self.db.flush()
        
        return job
    
    def get_job(self, job_id: int, company_id: int) -> Optional[VideoProcessingJob]:
        """Obtener job por ID"""
        return self.db.query(VideoProcessingJob).filter(
            and_(
                VideoProcessingJob.id == job_id,
                VideoProcessingJob.company_id == company_id
            )
        ).first()
    
    def update_status(
        self,
        job_id: int,
        status: str,
        microservice_job_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> VideoProcessingJob:
        """Actualizar estado del job"""
        
        job = self.db.query(VideoProcessingJob).filter(
            VideoProcessingJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")
        
        job.processing_status = status
        
        if microservice_job_id:
            job.microservice_job_id = microservice_job_id
        
        if status == "processing" and not job.processing_started_at:
            job.processing_started_at = datetime.now()
        
        if status in ["completed", "failed"]:
            job.processing_completed_at = datetime.now()
            
            if job.processing_started_at:
                delta = job.processing_completed_at - job.processing_started_at
                job.processing_time_seconds = int(delta.total_seconds())
        
        if error_message:
            job.error_message = error_message
        
        self.db.flush()
        return job
    
    def update_ai_results(
        self,
        job_id: int,
        ai_results: dict,
        confidence_score: float,
        detected_brand: Optional[str] = None,
        detected_model: Optional[str] = None,
        detected_colors: Optional[str] = None,
        detected_sizes: Optional[str] = None,
        frames_extracted: Optional[int] = None
    ) -> VideoProcessingJob:
        """Actualizar resultados de IA"""
        
        job = self.db.query(VideoProcessingJob).filter(
            VideoProcessingJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")
        
        job.ai_results_json = json.dumps(ai_results)
        job.confidence_score = confidence_score
        job.detected_brand = detected_brand
        job.detected_model = detected_model
        job.detected_colors = detected_colors
        job.detected_sizes = detected_sizes
        job.frames_extracted = frames_extracted or 0
        
        self.db.flush()
        return job
    
    def link_created_product(
        self,
        job_id: int,
        product_id: int,
        inventory_change_id: Optional[int] = None
    ) -> VideoProcessingJob:
        """Vincular producto creado al job"""
        
        job = self.db.query(VideoProcessingJob).filter(
            VideoProcessingJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")
        
        job.created_product_id = product_id
        
        if inventory_change_id:
            job.created_inventory_change_id = inventory_change_id
        
        self.db.flush()
        return job
    
    def increment_retry(self, job_id: int) -> VideoProcessingJob:
        """Incrementar contador de reintentos"""
        
        job = self.db.query(VideoProcessingJob).filter(
            VideoProcessingJob.id == job_id
        ).first()
        
        if not job:
            raise ValueError(f"Job {job_id} no encontrado")
        
        job.retry_count += 1
        self.db.flush()
        
        return job
    
    def list_jobs(
        self,
        company_id: int,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        warehouse_location_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[VideoProcessingJob], int]:
        """Listar jobs con filtros"""
        
        query = self.db.query(VideoProcessingJob).filter(
            VideoProcessingJob.company_id == company_id
        )
        
        if user_id:
            query = query.filter(VideoProcessingJob.processed_by_user_id == user_id)
        
        if status:
            query = query.filter(VideoProcessingJob.processing_status == status)
        
        if warehouse_location_id:
            query = query.filter(VideoProcessingJob.warehouse_location_id == warehouse_location_id)
        
        total = query.count()
        
        jobs = query.order_by(
            desc(VideoProcessingJob.created_at)
        ).limit(limit).offset(offset).all()
        
        return jobs, total
    
    def get_job_with_details(self, job_id: int, company_id: int) -> Optional[dict]:
        """Obtener job con detalles de relaciones"""
        
        result = self.db.query(
            VideoProcessingJob,
            User.first_name,
            User.last_name,
            Location.name.label('warehouse_name')
        ).outerjoin(
            User, VideoProcessingJob.processed_by_user_id == User.id
        ).outerjoin(
            Location, VideoProcessingJob.warehouse_location_id == Location.id
        ).filter(
            and_(
                VideoProcessingJob.id == job_id,
                VideoProcessingJob.company_id == company_id
            )
        ).first()
        
        if not result:
            return None
        
        job, first_name, last_name, warehouse_name = result
        
        return {
            "job": job,
            "processed_by_name": f"{first_name} {last_name}" if first_name else None,
            "warehouse_name": warehouse_name
        }