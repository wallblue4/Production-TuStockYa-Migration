# app/modules/video_processing/ai_client.py

"""
Cliente para comunicación con microservicio de IA
"""

import httpx
import logging
import json
from typing import Optional, Dict, Any
from fastapi import UploadFile
from io import BytesIO

from app.config.settings import settings

logger = logging.getLogger(__name__)


class VideoAIClient:
    """Cliente para el microservicio de procesamiento de video con IA"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'VIDEO_MICROSERVICE_URL', None)
        self.api_key = getattr(settings, 'VIDEO_MICROSERVICE_API_KEY', None)
        self.timeout = 300  # 5 minutos
    
    async def process_video(
        self,
        video_file: UploadFile,
        job_id: int,
        metadata: Dict[str, Any],
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enviar video al microservicio para procesamiento
        
        Args:
            video_file: Archivo de video
            job_id: ID del job en nuestra BD
            metadata: Metadata del procesamiento
            callback_url: URL para callback al completar
        
        Returns:
            Dict con respuesta del microservicio
        
        Raises:
            Exception si hay error en la comunicación
        """
        
        logger.info(f"🎥 Enviando video al microservicio de IA")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   URL: {self.base_url}")
        
        if not self.base_url:
            raise ValueError("VIDEO_MICROSERVICE_URL no está configurada en settings")
        
        try:
            # Leer contenido del video
            await video_file.seek(0)
            video_content = await video_file.read()
            
            if not video_content:
                raise ValueError("El archivo de video está vacío")
            
            logger.info(f"   Tamaño video: {len(video_content)} bytes")
            
            # Preparar archivos y datos
            video_stream = BytesIO(video_content)
            
            files = {
                "video": (
                    video_file.filename,
                    video_stream,
                    video_file.content_type or "video/mp4"
                )
            }
            
            data = {
                "job_id": str(job_id),
                "callback_url": callback_url or "",
                "metadata": json.dumps(metadata)
            }
            
            # Headers de autenticación
            headers = {}
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            # Realizar petición
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                logger.info("📤 Realizando petición HTTP al microservicio...")
                
                response = await client.post(
                    f"{self.base_url}/api/v1/process-video",
                    files=files,
                    data=data,
                    headers=headers
                )
                
                logger.info(f"📥 Respuesta recibida: {response.status_code}")
                
                if response.status_code not in [200, 201, 202]:
                    error_detail = response.text[:500]
                    logger.error(f"❌ Error del microservicio: {error_detail}")
                    raise Exception(
                        f"Error del microservicio (status {response.status_code}): {error_detail}"
                    )
                
                result = response.json()
                logger.info(f"✅ Video enviado exitosamente al microservicio")
                
                return result
        
        except httpx.TimeoutException:
            logger.error("❌ Timeout al comunicarse con microservicio de IA")
            raise Exception("Timeout al procesar video con IA (> 5 minutos)")
        
        except httpx.RequestError as e:
            logger.error(f"❌ Error de conexión con microservicio: {str(e)}")
            raise Exception(f"Error de conexión con microservicio de IA: {str(e)}")
        
        except Exception as e:
            logger.error(f"❌ Error inesperado en AI client: {str(e)}")
            raise
    
    async def check_health(self) -> bool:
        """Verificar que el microservicio esté disponible"""
        
        if not self.base_url:
            return False
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except:
            return False
    
    def parse_ai_results(self, raw_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parsear resultados crudos del microservicio
        
        Args:
            raw_results: Resultado crudo del microservicio
        
        Returns:
            Dict con datos estructurados para nuestra BD
        """
        
        return {
            "detected_brand": raw_results.get('brand'),
            "detected_model": raw_results.get('model'),
            "detected_colors": ','.join(raw_results.get('colors', [])) if raw_results.get('colors') else None,
            "detected_sizes": ','.join(map(str, raw_results.get('sizes', []))) if raw_results.get('sizes') else None,
            "confidence_score": float(raw_results.get('confidence', 0.0)),
            "frames_extracted": raw_results.get('frames_extracted', 0),
            "additional_features": raw_results.get('features', {})
        }