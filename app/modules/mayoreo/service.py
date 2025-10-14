from typing import List, Dict, Any, Optional
from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session
from decimal import Decimal
import logging

from .repository import MayoreoRepository
from .schemas import (
    MayoreoCreate, MayoreoUpdate, MayoreoResponse, MayoreoSearchParams,
    VentaMayoreoCreate, VentaMayoreoResponse, VentaMayoreoWithProduct, VentaMayoreoSearchParams,
    MayoreoListResponse, VentaMayoreoListResponse, MayoreoStatsResponse
)
from app.shared.services.cloudinary_service import cloudinary_service

logger = logging.getLogger(__name__)

class MayoreoService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = MayoreoRepository(db)

    # ===== MAYOREO CRUD OPERATIONS =====

    async def create_mayoreo(
        self, 
        mayoreo_data: MayoreoCreate, 
        user_id: int, 
        company_id: int,
        foto: Optional[UploadFile] = None
    ) -> MayoreoResponse:
        """
        Crear un nuevo producto de mayoreo con imagen opcional
        
        Args:
            mayoreo_data: Datos del producto
            user_id: ID del usuario creador
            company_id: ID de la compañía
            foto: Archivo de imagen opcional (se sube a Cloudinary)
        """
        try:
            # Validar que el usuario es administrador
            if not self.repository.validate_user_is_admin(user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Solo los administradores pueden crear productos de mayoreo"
                )
            
            # Subir imagen a Cloudinary si se proporcionó
            foto_url = None
            if foto and foto.filename:
                try:
                    logger.info(f"📸 Subiendo imagen para producto mayoreo: {mayoreo_data.modelo}")
                    
                    # Usar el modelo como identificador para la imagen
                    foto_url = await cloudinary_service.upload_product_reference_image(
                        image_file=foto,
                        product_reference=f"mayoreo_{mayoreo_data.modelo}",
                        user_id=user_id
                    )
                    
                    logger.info(f"✅ Imagen subida exitosamente: {foto_url}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Error subiendo imagen a Cloudinary: {str(upload_error)}")
                    # Continuar sin imagen si falla la subida
                    logger.warning("⚠️ Continuando sin imagen...")
            
            # Actualizar datos con la URL de la imagen
            mayoreo_dict = mayoreo_data.dict()
            mayoreo_dict['foto'] = foto_url
            
            # Crear producto en la base de datos
            mayoreo = self.repository.create_mayoreo(
                mayoreo_dict,
                user_id,
                company_id
            )
            
            return MayoreoResponse(
                success=True,
                message="Producto de mayoreo creado exitosamente" + (" con imagen" if foto_url else ""),
                id=mayoreo.id,
                user_id=mayoreo.user_id,
                company_id=mayoreo.company_id,
                modelo=mayoreo.modelo,
                foto=mayoreo.foto,
                tallas=mayoreo.tallas,
                cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                pares_por_caja=mayoreo.pares_por_caja,
                precio=mayoreo.precio,
                is_active=mayoreo.is_active,
                created_at=mayoreo.created_at,
                updated_at=mayoreo.updated_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error creando producto de mayoreo: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creando producto de mayoreo: {str(e)}"
            )

    async def get_mayoreo_by_id(self, mayoreo_id: int, user_id: int, company_id: int) -> MayoreoResponse:
        """Obtener un producto de mayoreo por ID"""
        try:
            mayoreo = self.repository.get_mayoreo_by_id(mayoreo_id)
            
            if not mayoreo:
                raise HTTPException(
                    status_code=404,
                    detail="Producto de mayoreo no encontrado"
                )
            
            # Validar ownership
            if not self.repository.validate_mayoreo_ownership(mayoreo_id, user_id, company_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para acceder a este producto"
                )
            
            return MayoreoResponse(
                success=True,
                message="Producto encontrado",
                id=mayoreo.id,
                user_id=mayoreo.user_id,
                        company_id=mayoreo.company_id,
                modelo=mayoreo.modelo,
                foto=mayoreo.foto,
                tallas=mayoreo.tallas,
                cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                pares_por_caja=mayoreo.pares_por_caja,
                precio=mayoreo.precio,
                is_active=mayoreo.is_active,
                created_at=mayoreo.created_at,
                updated_at=mayoreo.updated_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo producto de mayoreo: {str(e)}"
            )

    async def get_all_mayoreo(self, user_id: int, company_id: int) -> MayoreoListResponse:
        """Obtener todos los productos de mayoreo"""
        try:
            mayoreos = self.repository.get_all_mayoreo(user_id, company_id)
            
            mayoreo_responses = []
            for mayoreo in mayoreos:
                mayoreo_responses.append(MayoreoResponse(
                    success=True,
                    message="Producto encontrado",
                    id=mayoreo.id,
                    user_id=mayoreo.user_id,
                        company_id=mayoreo.company_id,
                    modelo=mayoreo.modelo,
                    foto=mayoreo.foto,
                    tallas=mayoreo.tallas,
                    cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                    pares_por_caja=mayoreo.pares_por_caja,
                    precio=mayoreo.precio,
                    is_active=mayoreo.is_active,
                    created_at=mayoreo.created_at,
                    updated_at=mayoreo.updated_at
                ))
            
            return MayoreoListResponse(
                success=True,
                message="Productos de mayoreo obtenidos exitosamente",
                data=mayoreo_responses,
                total=len(mayoreo_responses)
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo productos de mayoreo: {str(e)}"
            )

    async def search_mayoreo(self, user_id: int, company_id: int, search_params: MayoreoSearchParams) -> MayoreoListResponse:
        """Buscar productos de mayoreo con filtros"""
        try:
            mayoreos = self.repository.search_mayoreo(user_id, company_id, search_params)
            
            mayoreo_responses = []
            for mayoreo in mayoreos:
                mayoreo_responses.append(MayoreoResponse(
                    success=True,
                    message="Producto encontrado",
                    id=mayoreo.id,
                    user_id=mayoreo.user_id,
                        company_id=mayoreo.company_id,
                    modelo=mayoreo.modelo,
                    foto=mayoreo.foto,
                    tallas=mayoreo.tallas,
                    cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                    pares_por_caja=mayoreo.pares_por_caja,
                    precio=mayoreo.precio,
                    is_active=mayoreo.is_active,
                    created_at=mayoreo.created_at,
                    updated_at=mayoreo.updated_at
                ))
            
            return MayoreoListResponse(
                success=True,
                message="Búsqueda completada",
                data=mayoreo_responses,
                total=len(mayoreo_responses)
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error buscando productos de mayoreo: {str(e)}"
            )

    async def update_mayoreo(
        self, 
        mayoreo_id: int, 
        update_data: MayoreoUpdate, 
        user_id: int, 
        company_id: int,
        foto: Optional[UploadFile] = None
    ) -> MayoreoResponse:
        """
        Actualizar un producto de mayoreo con imagen opcional
        
        Args:
            mayoreo_id: ID del producto a actualizar
            update_data: Datos a actualizar
            user_id: ID del usuario
            company_id: ID de la compañía
            foto: Nueva imagen opcional (se sube a Cloudinary)
        """
        try:
            # Validar ownership
            if not self.repository.validate_mayoreo_ownership(mayoreo_id, user_id, company_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para actualizar este producto"
                )
            
            # Obtener producto actual (para modelo si se necesita)
            mayoreo_actual = self.repository.get_mayoreo_by_id(mayoreo_id)
            if not mayoreo_actual:
                raise HTTPException(
                    status_code=404,
                    detail="Producto de mayoreo no encontrado"
                )
            
            # Subir nueva imagen a Cloudinary si se proporcionó
            foto_url = None
            if foto and foto.filename:
                try:
                    logger.info(f"📸 Subiendo nueva imagen para producto mayoreo ID: {mayoreo_id}")
                    
                    # Usar el modelo actual o el nuevo si se está actualizando
                    modelo_referencia = update_data.modelo if update_data.modelo else mayoreo_actual.modelo
                    
                    foto_url = await cloudinary_service.upload_product_reference_image(
                        image_file=foto,
                        product_reference=f"mayoreo_{modelo_referencia}",
                        user_id=user_id
                    )
                    
                    logger.info(f"✅ Nueva imagen subida exitosamente: {foto_url}")
                    
                    # Intentar eliminar imagen anterior si existe
                    if mayoreo_actual.foto:
                        try:
                            await cloudinary_service.delete_image(mayoreo_actual.foto)
                            logger.info(f"🗑️ Imagen anterior eliminada")
                        except Exception as delete_error:
                            logger.warning(f"⚠️ No se pudo eliminar imagen anterior: {str(delete_error)}")
                    
                except Exception as upload_error:
                    logger.error(f"❌ Error subiendo nueva imagen: {str(upload_error)}")
                    # Continuar sin actualizar imagen si falla
                    logger.warning("⚠️ Continuando sin actualizar imagen...")
            
            # Filtrar campos None
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            
            # Agregar URL de foto si se subió
            if foto_url:
                update_dict['foto'] = foto_url
            
            # Actualizar producto en la base de datos
            mayoreo = self.repository.update_mayoreo(mayoreo_id, user_id, company_id, update_dict)
            
            if not mayoreo:
                raise HTTPException(
                    status_code=404,
                    detail="Producto de mayoreo no encontrado"
                )
            
            return MayoreoResponse(
                success=True,
                message="Producto actualizado exitosamente" + (" con nueva imagen" if foto_url else ""),
                id=mayoreo.id,
                user_id=mayoreo.user_id,
                company_id=mayoreo.company_id,
                modelo=mayoreo.modelo,
                foto=mayoreo.foto,
                tallas=mayoreo.tallas,
                cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                pares_por_caja=mayoreo.pares_por_caja,
                precio=mayoreo.precio,
                is_active=mayoreo.is_active,
                created_at=mayoreo.created_at,
                updated_at=mayoreo.updated_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Error actualizando producto de mayoreo: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error actualizando producto de mayoreo: {str(e)}"
            )

    async def delete_mayoreo(self, mayoreo_id: int, user_id: int, company_id: int) -> Dict[str, Any]:
        """Eliminar un producto de mayoreo (soft delete)"""
        try:
            # Validar ownership
            if not self.repository.validate_mayoreo_ownership(mayoreo_id, user_id, company_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para eliminar este producto"
                )
            
            success = self.repository.delete_mayoreo(mayoreo_id, user_id, company_id)
            
            if not success:
                raise HTTPException(
                    status_code=404,
                    detail="Producto de mayoreo no encontrado"
                )
            
            return {
                "success": True,
                "message": "Producto de mayoreo eliminado exitosamente"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error eliminando producto de mayoreo: {str(e)}"
            )

    # ===== VENTA MAYOREO OPERATIONS =====

    async def create_venta_mayoreo(self, venta_data: VentaMayoreoCreate, user_id: int, company_id: int) -> VentaMayoreoResponse:
        """Crear una nueva venta de mayoreo"""
        try:
            # Validar que el usuario es administrador
            if not self.repository.validate_user_is_admin(user_id):
                raise HTTPException(
                    status_code=403,
                    detail="Solo los administradores pueden realizar ventas de mayoreo"
                )
            
            # Validar que el producto existe y pertenece al usuario
            if not self.repository.validate_mayoreo_ownership(venta_data.mayoreo_id, user_id, company_id):
                raise HTTPException(
                    status_code=404,
                    detail="Producto de mayoreo no encontrado o no tienes permisos"
                )
            
            # Validar stock suficiente
            if not self.repository.validate_sufficient_stock(venta_data.mayoreo_id, venta_data.cantidad_cajas_vendidas):
                raise HTTPException(
                    status_code=400,
                    detail="Stock insuficiente para realizar la venta"
                )
            
            venta = self.repository.create_venta_mayoreo(
                venta_data.dict(),
                user_id,
                company_id
            )
            
            return VentaMayoreoResponse(
                success=True,
                message="Venta de mayoreo registrada exitosamente",
                id=venta.id,
                mayoreo_id=venta.mayoreo_id,
                user_id=venta.user_id,
                company_id=venta.company_id,
                cantidad_cajas_vendidas=venta.cantidad_cajas_vendidas,
                precio_unitario_venta=venta.precio_unitario_venta,
                total_venta=venta.total_venta,
                fecha_venta=venta.fecha_venta,
                notas=venta.notas,
                created_at=venta.created_at
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creando venta de mayoreo: {str(e)}"
            )

    async def get_all_ventas_mayoreo(self, user_id: int, company_id: int) -> VentaMayoreoListResponse:
        """Obtener todas las ventas de mayoreo"""
        try:
            ventas = self.repository.get_all_ventas_mayoreo(user_id, company_id)
            
            venta_responses = []
            for venta in ventas:
                # Obtener información del producto
                mayoreo = self.repository.get_mayoreo_by_id(venta.mayoreo_id)
                mayoreo_response = None
                if mayoreo:
                    mayoreo_response = MayoreoResponse(
                        success=True,
                        message="Producto encontrado",
                        id=mayoreo.id,
                        user_id=mayoreo.user_id,
                        company_id=mayoreo.company_id,
                        modelo=mayoreo.modelo,
                        foto=mayoreo.foto,
                        tallas=mayoreo.tallas,
                        cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                        pares_por_caja=mayoreo.pares_por_caja,
                        precio=mayoreo.precio,
                        is_active=mayoreo.is_active,
                        created_at=mayoreo.created_at,
                        updated_at=mayoreo.updated_at
                    )
                
                venta_response = VentaMayoreoWithProduct(
                    success=True,
                    message="Venta encontrada",
                    id=venta.id,
                    mayoreo_id=venta.mayoreo_id,
                    user_id=venta.user_id,
                    company_id=venta.company_id,
                    cantidad_cajas_vendidas=venta.cantidad_cajas_vendidas,
                    precio_unitario_venta=venta.precio_unitario_venta,
                    total_venta=venta.total_venta,
                    fecha_venta=venta.fecha_venta,
                    notas=venta.notas,
                    created_at=venta.created_at,
                    mayoreo_producto=mayoreo_response
                )
                
                venta_responses.append(venta_response.dict())
            
            return VentaMayoreoListResponse(
                success=True,
                message="Ventas de mayoreo obtenidas exitosamente",
                data=venta_responses,
                total=len(venta_responses)
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo ventas de mayoreo: {str(e)}"
            )

    async def search_ventas_mayoreo(self, user_id: int, company_id: int, search_params: VentaMayoreoSearchParams) -> VentaMayoreoListResponse:
        """Buscar ventas de mayoreo con filtros"""
        try:
            ventas = self.repository.search_ventas_mayoreo(user_id, company_id, search_params)
            
            venta_responses = []
            for venta in ventas:
                # Obtener información del producto
                mayoreo = self.repository.get_mayoreo_by_id(venta.mayoreo_id)
                mayoreo_response = None
                if mayoreo:
                    mayoreo_response = MayoreoResponse(
                        success=True,
                        message="Producto encontrado",
                        id=mayoreo.id,
                        user_id=mayoreo.user_id,
                        company_id=mayoreo.company_id,
                        modelo=mayoreo.modelo,
                        foto=mayoreo.foto,
                        tallas=mayoreo.tallas,
                        cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                        pares_por_caja=mayoreo.pares_por_caja,
                        precio=mayoreo.precio,
                        is_active=mayoreo.is_active,
                        created_at=mayoreo.created_at,
                        updated_at=mayoreo.updated_at
                    )
                
                venta_response = VentaMayoreoWithProduct(
                    success=True,
                    message="Venta encontrada",
                    id=venta.id,
                    mayoreo_id=venta.mayoreo_id,
                    user_id=venta.user_id,
                    company_id=venta.company_id,
                    cantidad_cajas_vendidas=venta.cantidad_cajas_vendidas,
                    precio_unitario_venta=venta.precio_unitario_venta,
                    total_venta=venta.total_venta,
                    fecha_venta=venta.fecha_venta,
                    notas=venta.notas,
                    created_at=venta.created_at,
                    mayoreo_producto=mayoreo_response
                )
                
                venta_responses.append(venta_response.dict())
            
            return VentaMayoreoListResponse(
                success=True,
                message="Búsqueda de ventas completada",
                data=venta_responses,
                total=len(venta_responses)
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error buscando ventas de mayoreo: {str(e)}"
            )

    async def get_ventas_by_mayoreo_id(self, mayoreo_id: int, user_id: int, company_id: int) -> VentaMayoreoListResponse:
        """Obtener todas las ventas de un producto específico de mayoreo"""
        try:
            # Validar ownership del producto
            if not self.repository.validate_mayoreo_ownership(mayoreo_id, user_id, company_id):
                raise HTTPException(
                    status_code=403,
                    detail="No tienes permisos para ver las ventas de este producto"
                )
            
            ventas = self.repository.get_ventas_by_mayoreo_id(mayoreo_id, user_id, company_id)
            
            venta_responses = []
            for venta in ventas:
                # Obtener información del producto
                mayoreo = self.repository.get_mayoreo_by_id(venta.mayoreo_id)
                if not mayoreo:
                    continue
                
                # Crear respuesta del producto
                mayoreo_response = MayoreoResponse(
                    success=True,
                    message="Producto encontrado",
                    id=mayoreo.id,
                    user_id=mayoreo.user_id,
                            company_id=mayoreo.company_id,
                    modelo=mayoreo.modelo,
                    foto=mayoreo.foto,
                    tallas=mayoreo.tallas,
                    cantidad_cajas_disponibles=mayoreo.cantidad_cajas_disponibles,
                    pares_por_caja=mayoreo.pares_por_caja,
                    precio=mayoreo.precio,
                    is_active=mayoreo.is_active,
                    created_at=mayoreo.created_at,
                    updated_at=mayoreo.updated_at
                )
                
                # Crear respuesta de venta con producto
                venta_response = VentaMayoreoWithProduct(
                    success=True,
                    message="Venta encontrada",
                    id=venta.id,
                    mayoreo_id=venta.mayoreo_id,
                    user_id=venta.user_id,
                    company_id=venta.company_id,
                    cantidad_cajas_vendidas=venta.cantidad_cajas_vendidas,
                    precio_unitario_venta=venta.precio_unitario_venta,
                    total_venta=venta.total_venta,
                    fecha_venta=venta.fecha_venta,
                    notas=venta.notas,
                    created_at=venta.created_at,
                    mayoreo_producto=mayoreo_response
                )
                venta_responses.append(venta_response.dict())
            
            return VentaMayoreoListResponse(
                success=True,
                message="Ventas del producto obtenidas exitosamente",
                data=venta_responses,
                total=len(venta_responses)
            )
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo ventas del producto: {str(e)}"
            )

    # ===== STATISTICS =====

    async def get_mayoreo_stats(self, user_id: int, company_id: int) -> MayoreoStatsResponse:
        """Obtener estadísticas de mayoreo"""
        try:
            stats = self.repository.get_mayoreo_stats(user_id, company_id)
            
            return MayoreoStatsResponse(
                success=True,
                message="Estadísticas obtenidas exitosamente",
                total_productos=stats['total_productos'],
                total_cajas_disponibles=stats['total_cajas_disponibles'],
                valor_total_inventario=stats['valor_total_inventario'],
                total_ventas=stats['total_ventas'],
                valor_total_ventas=stats['valor_total_ventas']
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error obteniendo estadísticas: {str(e)}"
            )
