# app/modules/mayoreo/router.py
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from .service import MayoreoService
from .schemas import (
    MayoreoCreate, MayoreoUpdate, MayoreoResponse, MayoreoSearchParams,
    VentaMayoreoCreate, VentaMayoreoResponse, VentaMayoreoSearchParams,
    MayoreoListResponse, VentaMayoreoListResponse, MayoreoStatsResponse
)

router = APIRouter()

# ===== HEALTH CHECK =====

@router.get("/health")
async def mayoreo_health():
    """
    Health check del módulo de mayoreo
    
    Verifica el estado del servicio y lista todas las funcionalidades disponibles.
    """
    return {
        "service": "mayoreo",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "CRUD de productos de mayoreo (Solo administradores)",
            "Gestión de ventas de mayoreo",
            "Búsqueda y filtros avanzados",
            "Estadísticas y reportes",
            "Validación de stock automática",
            "Control de permisos por rol"
        ],
        "endpoints": {
            "productos": [
                "POST /productos/crear - Crear producto de mayoreo (con imagen opcional)",
                "GET /productos/listar - Listar todos los productos",
                "GET /productos/buscar - Buscar productos con filtros",
                "GET /productos/{id} - Obtener producto por ID",
                "PUT /productos/{id}/actualizar - Actualizar producto (JSON, sin imagen)",
                "PUT /productos/{id}/actualizar-con-imagen - Actualizar producto con imagen (multipart)",
                "DELETE /productos/{id}/eliminar - Eliminar producto (soft delete)"
            ],
            "ventas": [
                "POST /ventas/registrar - Registrar venta de mayoreo",
                "GET /ventas/listar - Listar todas las ventas",
                "GET /ventas/buscar - Buscar ventas con filtros",
                "GET /productos/{id}/ventas - Historial de ventas por producto"
            ],
            "estadisticas": [
                "GET /estadisticas - Obtener estadísticas generales de mayoreo"
            ]
        }
    }

# ===== PRODUCTOS MAYOREO - CRUD ENDPOINTS =====

@router.post("/productos/crear", response_model=MayoreoResponse)
async def create_producto_mayoreo(
    modelo: str = Form(..., description="Modelo del producto"),
    cantidad_cajas_disponibles: int = Form(0, ge=0, description="Cantidad de cajas disponibles"),
    pares_por_caja: int = Form(..., gt=0, description="Pares por caja"),
    precio: Decimal = Form(..., gt=0, description="Precio por caja"),
    tallas: Optional[str] = Form(None, description="Distribución de tallas"),
    foto: Optional[UploadFile] = File(None, description="Imagen del producto"),
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Crear un nuevo producto de mayoreo
    
    **Permisos requeridos:** Solo administradores
    
    **Content-Type:** multipart/form-data
    
    **Campos obligatorios (Form Data):**
    - `modelo`: Modelo del producto (ej: "SS-9012")
    - `cantidad_cajas_disponibles`: Cantidad inicial de cajas (>= 0)
    - `pares_por_caja`: Número de pares por caja (> 0)
    - `precio`: Precio por caja (> 0)
    
    **Campos opcionales:**
    - `foto`: Archivo de imagen (JPG, PNG, WEBP) - Se sube a Cloudinary
    - `tallas`: Distribución de tallas (ej: "36-39/6666, 40-44/6662")
    
    **Validaciones:**
    - La cantidad de cajas debe ser >= 0
    - Los pares por caja deben ser > 0
    - El precio debe ser > 0
    - La imagen (si se envía) debe ser válida y menor a 5MB
    
    **Proceso:**
    1. Se valida la información del producto
    2. Si se envía imagen, se sube a Cloudinary automáticamente
    3. Se guarda la URL de Cloudinary en la base de datos
    4. Se crea el producto con todos los datos
    
    **Respuesta:**
    - Retorna el producto creado con su ID asignado
    - Incluye la URL de la imagen si se subió
    - El producto se crea activo por defecto (is_active = true)
    """
    service = MayoreoService(db)
    
    # Crear objeto MayoreoCreate sin la foto (se manejará por separado)
    mayoreo_data = MayoreoCreate(
        modelo=modelo,
        cantidad_cajas_disponibles=cantidad_cajas_disponibles,
        pares_por_caja=pares_por_caja,
        precio=precio,
        tallas=tallas,
        foto=None  # Se llenará después de subir a Cloudinary
    )
    
    return await service.create_mayoreo(mayoreo_data, current_user.id, company_id, foto)

@router.get("/productos/listar", response_model=MayoreoListResponse)
async def listar_productos_mayoreo(
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Listar todos los productos de mayoreo
    
    **Permisos requeridos:** Solo administradores
    
    **Filtros automáticos:**
    - Solo muestra productos del usuario/compañía actual
    - Incluye productos activos e inactivos
    
    **Respuesta:**
    - Lista de todos los productos de mayoreo
    - Ordenados por fecha de creación (más recientes primero)
    - Incluye total de productos encontrados
    """
    service = MayoreoService(db)
    return await service.get_all_mayoreo(current_user.id, company_id)

@router.get("/productos/buscar", response_model=MayoreoListResponse)
async def buscar_productos_mayoreo(
    modelo: Optional[str] = Query(None, description="Buscar por modelo (búsqueda parcial)"),
    tallas: Optional[str] = Query(None, description="Buscar por tallas (búsqueda parcial)"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado: true=activos, false=inactivos"),
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Buscar productos de mayoreo con filtros avanzados
    
    **Permisos requeridos:** Solo administradores
    
    **Filtros disponibles:**
    - `modelo`: Búsqueda parcial por modelo (case-insensitive)
    - `tallas`: Búsqueda parcial por tallas (case-insensitive)
    - `is_active`: Filtrar por estado activo/inactivo
    
    **Ejemplos de uso:**
    - `/productos/buscar?modelo=SS-9012` - Busca productos con modelo que contenga "SS-9012"
    - `/productos/buscar?tallas=36-39` - Busca productos con tallas que contengan "36-39"
    - `/productos/buscar?is_active=true` - Solo productos activos
    - `/productos/buscar?modelo=SS&is_active=true` - Combinar múltiples filtros
    
    **Respuesta:**
    - Lista de productos que coinciden con los filtros
    - Ordenados por fecha de creación (más recientes primero)
    """
    service = MayoreoService(db)
    search_params = MayoreoSearchParams(
        modelo=modelo,
        tallas=tallas,
        is_active=is_active
    )
    return await service.search_mayoreo(current_user.id, company_id, search_params)

@router.get("/productos/{mayoreo_id}", response_model=MayoreoResponse)
async def get_producto_mayoreo(
    mayoreo_id: int,
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener un producto de mayoreo por su ID
    
    **Permisos requeridos:** Solo administradores
    
    **Parámetros:**
    - `mayoreo_id`: ID del producto de mayoreo
    
    **Validaciones:**
    - El producto debe existir
    - El producto debe pertenecer al usuario/compañía actual
    
    **Respuesta:**
    - Retorna toda la información del producto
    - Incluye cantidad disponible, precio, tallas, etc.
    """
    service = MayoreoService(db)
    return await service.get_mayoreo_by_id(mayoreo_id, current_user.id, company_id)

@router.put("/productos/{mayoreo_id}/actualizar", response_model=MayoreoResponse)
async def actualizar_producto_mayoreo(
    mayoreo_id: int,
    update_data: MayoreoUpdate,
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Actualizar un producto de mayoreo existente (sin cambiar imagen)
    
    **Permisos requeridos:** Solo administradores
    
    **Content-Type:** application/json
    
    **Parámetros URL:**
    - `mayoreo_id`: ID del producto a actualizar
    
    **Campos actualizables (JSON - todos opcionales):**
    - `modelo`: Nuevo modelo del producto
    - `cantidad_cajas_disponibles`: Nueva cantidad de cajas (>= 0)
    - `pares_por_caja`: Nuevo número de pares por caja (> 0)
    - `precio`: Nuevo precio por caja (> 0)
    - `tallas`: Nueva distribución de tallas
    - `is_active`: Activar/desactivar producto (true/false)
    
    **Validaciones:**
    - El producto debe existir
    - El producto debe pertenecer al usuario/compañía actual
    - Se validan las mismas restricciones que al crear
    
    **Actualización parcial:**
    - Solo se actualizan los campos proporcionados
    - Los campos no incluidos permanecen sin cambios
    
    **Respuesta:**
    - Retorna el producto actualizado con todos sus campos
    """
    service = MayoreoService(db)
    return await service.update_mayoreo(mayoreo_id, update_data, current_user.id, company_id, None)

@router.put("/productos/{mayoreo_id}/actualizar-con-imagen", response_model=MayoreoResponse)
async def actualizar_producto_mayoreo_con_imagen(
    mayoreo_id: int,
    modelo: Optional[str] = Form(None, description="Modelo del producto"),
    cantidad_cajas_disponibles: Optional[int] = Form(None, ge=0, description="Cantidad de cajas disponibles"),
    pares_por_caja: Optional[int] = Form(None, gt=0, description="Pares por caja"),
    precio: Optional[Decimal] = Form(None, gt=0, description="Precio por caja"),
    tallas: Optional[str] = Form(None, description="Distribución de tallas"),
    is_active: Optional[bool] = Form(None, description="Estado del producto"),
    foto: Optional[UploadFile] = File(None, description="Nueva imagen del producto"),
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Actualizar un producto de mayoreo con nueva imagen
    
    **Permisos requeridos:** Solo administradores
    
    **Content-Type:** multipart/form-data
    
    **Parámetros URL:**
    - `mayoreo_id`: ID del producto a actualizar
    
    **Campos actualizables (Form Data - todos opcionales):**
    - `modelo`: Nuevo modelo del producto
    - `cantidad_cajas_disponibles`: Nueva cantidad de cajas (>= 0)
    - `pares_por_caja`: Nuevo número de pares por caja (> 0)
    - `precio`: Nuevo precio por caja (> 0)
    - `tallas`: Nueva distribución de tallas
    - `is_active`: Activar/desactivar producto (true/false)
    - `foto`: Nueva imagen del producto (se sube a Cloudinary)
    
    **Validaciones:**
    - El producto debe existir
    - El producto debe pertenecer al usuario/compañía actual
    - Se validan las mismas restricciones que al crear
    
    **Proceso automático al subir imagen:**
    1. Se sube la nueva imagen a Cloudinary
    2. Se elimina automáticamente la imagen anterior de Cloudinary
    3. Se actualiza la URL en la base de datos
    
    **Actualización parcial:**
    - Solo se actualizan los campos proporcionados
    - Los campos no incluidos permanecen sin cambios
    
    **Respuesta:**
    - Retorna el producto actualizado con todos sus campos
    - Incluye la nueva URL de imagen si se subió
    """
    service = MayoreoService(db)
    
    # Crear objeto MayoreoUpdate con los campos proporcionados
    update_data = MayoreoUpdate(
        modelo=modelo,
        cantidad_cajas_disponibles=cantidad_cajas_disponibles,
        pares_por_caja=pares_por_caja,
        precio=precio,
        tallas=tallas,
        is_active=is_active,
        foto=None  # Se manejará por separado
    )
    
    return await service.update_mayoreo(mayoreo_id, update_data, current_user.id, company_id, foto)

@router.delete("/productos/{mayoreo_id}/eliminar")
async def eliminar_producto_mayoreo(
    mayoreo_id: int,
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Eliminar un producto de mayoreo (Soft Delete)
    
    **Permisos requeridos:** Solo administradores
    
    **Parámetros:**
    - `mayoreo_id`: ID del producto a eliminar
    
    **Tipo de eliminación:**
    - **Soft Delete**: El producto se marca como inactivo (is_active = false)
    - No se elimina físicamente de la base de datos
    - Se mantiene el historial de ventas asociadas
    
    **Validaciones:**
    - El producto debe existir
    - El producto debe pertenecer al usuario/compañía actual
    
    **Respuesta:**
    - Mensaje de confirmación de eliminación exitosa
    - El producto ya no aparecerá en listados de activos
    """
    service = MayoreoService(db)
    return await service.delete_mayoreo(mayoreo_id, current_user.id, company_id)

# ===== VENTAS MAYOREO ENDPOINTS =====

@router.post("/ventas/registrar", response_model=VentaMayoreoResponse)
async def registrar_venta_mayoreo(
    venta_data: VentaMayoreoCreate,
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Registrar una nueva venta de producto mayoreo
    
    **Permisos requeridos:** Solo administradores
    
    **Campos obligatorios:**
    - `mayoreo_id`: ID del producto de mayoreo a vender
    - `cantidad_cajas_vendidas`: Número de cajas vendidas (debe ser > 0)
    - `precio_unitario_venta`: Precio de venta por caja (debe ser > 0)
    
    **Campos opcionales:**
    - `notas`: Observaciones sobre la venta (ej: "Cliente mayorista de Panamá")
    
    **Proceso automático:**
    1. Valida que el producto existe y tiene stock suficiente
    2. Calcula el total de la venta automáticamente
    3. Descuenta la cantidad vendida del stock disponible
    4. Registra la fecha de venta automáticamente
    
    **Validaciones:**
    - El producto debe existir y pertenecer al usuario/compañía
    - Debe haber stock suficiente (cajas disponibles >= cajas vendidas)
    - La cantidad y el precio deben ser mayores a 0
    
    **Respuesta:**
    - Detalles completos de la venta registrada
    - Incluye ID, total calculado, fecha de venta
    - El stock del producto se actualiza automáticamente
    """
    service = MayoreoService(db)
    return await service.create_venta_mayoreo(venta_data, current_user.id, company_id)

@router.get("/ventas/listar", response_model=VentaMayoreoListResponse)
async def listar_ventas_mayoreo(
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Listar todas las ventas de mayoreo
    
    **Permisos requeridos:** Solo administradores
    
    **Filtros automáticos:**
    - Solo muestra ventas del usuario/compañía actual
    
    **Información incluida por cada venta:**
    - Datos completos de la venta (cantidad, precio, total, fecha)
    - Información detallada del producto vendido
    - Usuario que realizó la venta
    - Notas adicionales si existen
    
    **Respuesta:**
    - Lista de todas las ventas de mayoreo
    - Ordenadas por fecha (más recientes primero)
    - Incluye total de ventas encontradas
    - Cada venta incluye el objeto del producto completo
    """
    service = MayoreoService(db)
    return await service.get_all_ventas_mayoreo(current_user.id, company_id)

@router.get("/ventas/buscar", response_model=VentaMayoreoListResponse)
async def buscar_ventas_mayoreo(
    mayoreo_id: Optional[int] = Query(None, description="Filtrar por ID del producto de mayoreo"),
    fecha_desde: Optional[datetime] = Query(None, description="Fecha inicio del rango (YYYY-MM-DDTHH:MM:SS)"),
    fecha_hasta: Optional[datetime] = Query(None, description="Fecha fin del rango (YYYY-MM-DDTHH:MM:SS)"),
    cantidad_minima: Optional[int] = Query(None, description="Cantidad mínima de cajas vendidas"),
    cantidad_maxima: Optional[int] = Query(None, description="Cantidad máxima de cajas vendidas"),
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Buscar ventas de mayoreo con filtros avanzados
    
    **Permisos requeridos:** Solo administradores
    
    **Filtros disponibles:**
    - `mayoreo_id`: Filtrar ventas de un producto específico
    - `fecha_desde` y `fecha_hasta`: Rango de fechas
    - `cantidad_minima` y `cantidad_maxima`: Rango de cantidades vendidas
    
    **Ejemplos de uso:**
    - `/ventas/buscar?mayoreo_id=5` - Ventas del producto con ID 5
    - `/ventas/buscar?fecha_desde=2024-01-01T00:00:00&fecha_hasta=2024-12-31T23:59:59` - Ventas del año 2024
    - `/ventas/buscar?cantidad_minima=10` - Ventas de 10 o más cajas
    - `/ventas/buscar?cantidad_minima=5&cantidad_maxima=20` - Ventas entre 5 y 20 cajas
    - Puedes combinar múltiples filtros
    
    **Formato de fechas:**
    - ISO 8601: `YYYY-MM-DDTHH:MM:SS`
    - Ejemplo: `2024-01-15T10:30:00`
    
    **Respuesta:**
    - Lista de ventas que coinciden con los filtros
    - Cada venta incluye información completa del producto
    - Ordenadas por fecha (más recientes primero)
    """
    service = MayoreoService(db)
    search_params = VentaMayoreoSearchParams(
        mayoreo_id=mayoreo_id,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        cantidad_minima=cantidad_minima,
        cantidad_maxima=cantidad_maxima
    )
    return await service.search_ventas_mayoreo(current_user.id, company_id, search_params)

@router.get("/productos/{mayoreo_id}/ventas", response_model=VentaMayoreoListResponse)
async def obtener_historial_ventas_producto(
    mayoreo_id: int,
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener historial completo de ventas de un producto específico
    
    **Permisos requeridos:** Solo administradores
    
    **Parámetros:**
    - `mayoreo_id`: ID del producto de mayoreo
    
    **Validaciones:**
    - El producto debe existir
    - El producto debe pertenecer al usuario/compañía actual
    
    **Información incluida:**
    - Todas las ventas realizadas del producto
    - Detalles de cada venta (cantidad, precio, total, fecha)
    - Información completa del producto vendido
    - Notas de cada venta
    
    **Utilidad:**
    - Ver histórico de ventas de un producto
    - Análisis de rendimiento de ventas
    - Seguimiento de precios de venta históricos
    - Identificar clientes recurrentes (mediante notas)
    
    **Respuesta:**
    - Lista de ventas del producto específico
    - Ordenadas por fecha (más recientes primero)
    - Incluye información completa del producto en cada venta
    """
    service = MayoreoService(db)
    return await service.get_ventas_by_mayoreo_id(mayoreo_id, current_user.id, company_id)

# ===== ESTADÍSTICAS ENDPOINTS =====

@router.get("/estadisticas", response_model=MayoreoStatsResponse)
async def obtener_estadisticas_mayoreo(
    current_user = Depends(require_roles(["administrador"])),
    company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Obtener estadísticas generales de mayoreo
    
    **Permisos requeridos:** Solo administradores
    
    **Estadísticas de productos incluidas:**
    - `total_productos`: Cantidad total de productos activos
    - `total_cajas_disponibles`: Total de cajas en inventario
    - `valor_total_inventario`: Valor total del inventario (cajas × pares × precio)
    
    **Estadísticas de ventas incluidas:**
    - `total_ventas`: Cantidad total de ventas realizadas
    - `valor_total_ventas`: Monto total vendido en todas las ventas
    
    **Utilidad:**
    - Dashboard de mayoreo
    - Reportes ejecutivos
    - Análisis de inventario vs ventas
    - Toma de decisiones de negocio
    
    **Cálculos automáticos:**
    - Solo considera productos activos para inventario
    - Incluye todas las ventas históricas
    - Los valores se calculan en tiempo real
    
    **Respuesta:**
    - Objeto con todas las métricas calculadas
    - Valores numéricos listos para mostrar
    - Datos filtrados por usuario/compañía actual
    """
    service = MayoreoService(db)
    return await service.get_mayoreo_stats(current_user.id, company_id)
