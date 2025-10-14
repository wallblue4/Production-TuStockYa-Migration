# app/modules/boss/router.py
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, timedelta

from app.config.database import get_db
from app.core.auth.dependencies import require_roles, get_current_company_id
from app.shared.database.models import User
from .service import BossService
from .schemas import (
    LocationCreate, LocationResponse, ExecutiveDashboard,
    SalesConsolidatedReport, ReportFilters, ConsolidatedInventory,
    FinancialAnalysis
)

router = APIRouter(prefix="/boss", tags=["Boss - Director Ejecutivo"])

# ==================== BS008 & BS009: CREAR UBICACIONES ====================

@router.post("/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    location_data: LocationCreate,
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS008: Crear nuevos locales de venta**
    **BS009: Crear nuevas bodegas**
    
    Permite al Boss crear nuevas ubicaciones para expansión del negocio.
    
    **Funcionalidad:**
    - Crear locales de venta (type='local')
    - Crear bodegas de almacenamiento (type='bodega')
    - Validar unicidad de nombre por empresa
    - Registrar información completa de la ubicación
    
    **Proceso:**
    1. Valida que el usuario sea Boss
    2. Verifica que no exista una ubicación con el mismo nombre
    3. Crea la ubicación y la activa automáticamente
    4. La ubicación queda disponible para asignar administradores
    
    **Siguiente paso:**
    - Asignar administrador a la ubicación (BS011 - heredado de Admin)
    - Crear usuarios para operar en la ubicación
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.create_location(location_data, current_user)

@router.get("/locations", response_model=List[LocationResponse])
async def get_all_locations(
    include_inactive: bool = Query(False, description="Incluir ubicaciones inactivas"),
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **Listar todas las ubicaciones de la empresa**
    
    Obtiene todas las ubicaciones (locales y bodegas) de la empresa,
    con métricas básicas de cada una.
    
    **Información incluida:**
    - Datos básicos de la ubicación
    - Número de usuarios asignados
    - Número de productos en inventario
    - Valor total del inventario
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.get_all_locations(current_user, include_inactive)

# ==================== BS001: DASHBOARD EJECUTIVO ====================

@router.get("/dashboard", response_model=ExecutiveDashboard)
async def get_executive_dashboard(
    target_date: Optional[date] = Query(None, description="Fecha del dashboard (default: hoy)"),
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS001: Visualizar dashboard ejecutivo con KPIs principales**
    
    Dashboard ejecutivo con vista panorámica del negocio.
    
    **KPIs Principales:**
    - Ventas del día (comparado con ayer)
    - Ventas del mes (comparado con mes anterior)
    - Valor total del inventario
    - Transacciones realizadas
    - Usuarios activos
    - Ubicaciones activas
    
    **Performance por Ubicación:**
    - Ventas diarias y mensuales
    - Valor del inventario
    - Usuarios activos
    - Transferencias pendientes
    - Score de eficiencia
    
    **Resumen Financiero:**
    - Ingresos totales
    - Costos totales
    - Utilidad neta
    - Margen de ganancia
    
    **Alertas:**
    - Stock bajo y agotado
    - Transferencias demoradas
    - Problemas operativos
    
    **Métricas de Crecimiento:**
    - Comparativas período anterior
    - Proyecciones del mes
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.get_executive_dashboard(current_user, target_date)

# ==================== BS002: REPORTES CONSOLIDADOS ====================

@router.post("/reports/sales/consolidated", response_model=SalesConsolidatedReport)
async def get_consolidated_sales_report(
    filters: ReportFilters,
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS002: Acceder a reportes de ventas consolidados**
    
    Genera reportes consolidados de ventas para cualquier período.
    
    **Información incluida:**
    - Totales generales (ventas, transacciones, ticket promedio)
    - Ventas por ubicación
    - Top vendedores (mejores 10)
    - Top productos más vendidos
    - Desglose por métodos de pago
    
    **Filtros disponibles:**
    - Rango de fechas (obligatorio)
    - Ubicaciones específicas (opcional)
    - Incluir/excluir ubicaciones inactivas
    
    **Casos de uso:**
    - Reporte diario de ventas
    - Reporte mensual para contabilidad
    - Análisis de performance por período
    - Comparativas entre ubicaciones
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.get_consolidated_sales_report(current_user, filters)

@router.get("/reports/sales/daily", response_model=SalesConsolidatedReport)
async def get_daily_sales_report(
    report_date: date = Query(default_factory=date.today, description="Fecha del reporte"),
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS002: Reporte diario de ventas (atajo)**
    
    Genera reporte de ventas para un día específico.
    Atajo conveniente para el reporte diario más común.
    
    **Permisos:** Solo Boss
    """
    filters = ReportFilters(
        start_date=report_date,
        end_date=report_date
    )
    service = BossService(db, current_company_id)
    return await service.get_consolidated_sales_report(current_user, filters)

@router.get("/reports/sales/monthly", response_model=SalesConsolidatedReport)
async def get_monthly_sales_report(
    year: int = Query(..., description="Año del reporte"),
    month: int = Query(..., ge=1, le=12, description="Mes del reporte"),
    current_user: User =Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS002: Reporte mensual de ventas (atajo)**
    
    Genera reporte de ventas para un mes completo.
    
    **Ejemplo:** year=2025, month=10 → Octubre 2025
    
    **Permisos:** Solo Boss
    """
    import calendar
    
    # Primer día del mes
    start_date = date(year, month, 1)
    
    # Último día del mes
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    filters = ReportFilters(
        start_date=start_date,
        end_date=end_date
    )
    service = BossService(db, current_company_id)
    return await service.get_consolidated_sales_report(current_user, filters)

# ==================== BS003: INVENTARIO CONSOLIDADO ====================

@router.get("/inventory/consolidated", response_model=ConsolidatedInventory)
async def get_consolidated_inventory(
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS003: Consultar inventario total por categorías**
    
    Vista consolidada del inventario de toda la empresa.
    
    **Totales Generales:**
    - Productos únicos
    - Unidades totales
    - Valor total del inventario
    
    **Por Categoría (Marca):**
    - Unidades por marca
    - Valor por marca
    - Número de ubicaciones con cada marca
    - Porcentaje del inventario total
    
    **Por Ubicación:**
    - Productos por ubicación
    - Unidades por ubicación
    - Valor del inventario por ubicación
    - Alertas de stock bajo por ubicación
    
    **Alertas:**
    - Productos con stock bajo (< 5 unidades)
    - Productos agotados
    - Productos con sobrestock (> 100 unidades)
    
    **Casos de uso:**
    - Planificación de compras
    - Redistribución de inventario
    - Identificación de productos críticos
    - Análisis de rotación
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.get_consolidated_inventory(current_user)

# ==================== BS004: ANÁLISIS FINANCIERO ====================

@router.get("/financial/analysis", response_model=FinancialAnalysis)
async def get_financial_analysis(
    start_date: date = Query(..., description="Fecha inicio del análisis"),
    end_date: date = Query(..., description="Fecha fin del análisis"),
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS004: Revisar costos operativos y márgenes de ganancia**
    
    Análisis financiero completo con ingresos, costos y márgenes.
    
    **Totales Consolidados:**
    - Ingresos totales del período
    - Costos totales (fijos + variables)
    - Utilidad neta
    - Margen de ganancia general
    
    **Por Ubicación:**
    - Ingresos por ubicación
    - Costos operativos por ubicación
    - Desglose de costos por tipo
    - Utilidad bruta y margen
    - ROI (si aplica)
    
    **Costos por Tipo:**
    - Arriendo
    - Servicios públicos
    - Nómina
    - Comisiones
    - Otros
    
    **Comparativas:**
    - Mejor ubicación por margen
    - Peor ubicación por margen
    - Tendencias (si hay datos históricos)
    
    **Casos de uso:**
    - Análisis mensual de rentabilidad
    - Evaluación de performance por ubicación
    - Identificación de costos excesivos
    - Toma de decisiones de expansión/cierre
    
    **Nota:** Los costos se calculan proporcionalmente según
    la frecuencia configurada (diario, semanal, mensual, etc.)
    
    **Permisos:** Solo Boss
    """
    service = BossService(db, current_company_id)
    return await service.get_financial_analysis(current_user, start_date, end_date)

@router.get("/financial/monthly", response_model=FinancialAnalysis)
async def get_monthly_financial_analysis(
    year: int = Query(..., description="Año del análisis"),
    month: int = Query(..., ge=1, le=12, description="Mes del análisis"),
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    **BS004: Análisis financiero mensual (atajo)**
    
    Análisis financiero para un mes completo.
    Atajo conveniente para el análisis mensual más común.
    
    **Permisos:** Solo Boss
    """
    import calendar
    
    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    
    service = BossService(db, current_company_id)
    return await service.get_financial_analysis(current_user, start_date, end_date)

# ==================== UTILIDADES ====================

@router.get("/health")
async def boss_module_health():
    """
    Health check del módulo Boss
    """
    return {
        "module": "boss",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "BS001 - Dashboard ejecutivo con KPIs ✅",
            "BS002 - Reportes de ventas consolidados ✅",
            "BS003 - Inventario total por categorías ✅",
            "BS004 - Costos operativos y márgenes ✅",
            "BS005 - Gestión organizacional (heredado de Admin) ✅",
            "BS008 - Crear locales de venta ✅",
            "BS009 - Crear bodegas ✅",
            "BS011 - Asignar administradores (heredado de Admin) ✅"
        ],
        "inherited_from_admin": [
            "BS005 - Gestionar estructura organizacional",
            "BS011 - Asignar administradores a ubicaciones",
            "Todas las funcionalidades AD001-AD016"
        ]
    }

@router.get("/summary")
async def get_boss_summary(
    current_user: User = Depends(require_roles(["boss"])),
    current_company_id: int = Depends(get_current_company_id),
    db: Session = Depends(get_db)
):
    """
    Resumen ejecutivo rápido del negocio
    
    Vista ultra simplificada con los números más importantes.
    """
    from app.shared.database.models import Location, User as UserModel, Product, ProductSize, Sale
    from sqlalchemy import func
    from datetime import datetime
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    
    # Totales rápidos
    total_locations = db.query(func.count(Location.id)).filter(
        Location.company_id == current_company_id,
        Location.is_active == True
    ).scalar() or 0
    
    total_users = db.query(func.count(UserModel.id)).filter(
        UserModel.company_id == current_company_id,
        UserModel.is_active == True
    ).scalar() or 0
    
    total_products = db.query(func.count(Product.id)).filter(
        Product.company_id == current_company_id,
        Product.is_active == 1
    ).scalar() or 0
    
    inventory_value = db.query(
        func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0)
    ).join(Product).filter(
        Product.company_id == current_company_id,
        ProductSize.company_id == current_company_id,
        Product.is_active == 1
    ).scalar() or 0
    
    today_sales = db.query(
        func.coalesce(func.sum(Sale.total_amount), 0)
    ).filter(
        Sale.company_id == current_company_id,
        Sale.sale_date >= today_start,
        Sale.status == 'completed'
    ).scalar() or 0
    
    return {
        "company_name": current_user.company.name if current_user.company else "Mi Empresa",
        "boss_name": current_user.full_name,
        "quick_stats": {
            "ubicaciones_activas": total_locations,
            "usuarios_activos": total_users,
            "productos_totales": total_products,
            "valor_inventario": float(inventory_value),
            "ventas_hoy": float(today_sales)
        },
        "timestamp": datetime.now()
    }