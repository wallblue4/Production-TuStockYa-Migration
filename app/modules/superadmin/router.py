# app/modules/superadmin/router.py
from fastapi import APIRouter, Depends, Query, Path, Body, status , HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.config.database import get_db
from app.core.auth.dependencies import get_superadmin_user, get_current_user
from app.shared.database.models import User
from .service import SuperadminService
from .schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyListItem,
    SubscriptionChangeCreate, InvoiceMarkPaid,
    PlanTemplateCreate, PlanTemplateResponse,
    GlobalMetrics, CompanyMetrics,
    FirstSuperadminCreate, BossCreate, BossResponse, CompanyWithBossResponse
)

router = APIRouter()


# =====================================================
# SETUP - CREAR PRIMER SUPERADMIN
# =====================================================

@router.post("/setup/first-superadmin", status_code=status.HTTP_201_CREATED)
async def create_first_superadmin(
    admin_data: FirstSuperadminCreate,
    db: Session = Depends(get_db)
):
    """
    **SU000: Crear el primer superadmin del sistema (solo una vez)**
    
    Este endpoint solo funciona si NO existe ningún superadmin.
    Requiere una clave secreta definida en variables de entorno.
    
    **Uso:**
    - Solo se ejecuta una vez durante la instalación inicial
    - Requiere `INSTALL_SECRET_KEY` configurada en `.env`
    - Después de crear el primer superadmin, este endpoint se bloquea
    
    **Seguridad:**
    - Validación de clave secreta
    - Password con requisitos de seguridad
    - Registro en logs de auditoría
    """
    service = SuperadminService(db)
    return await service.create_first_superadmin(admin_data)


# =====================================================
# COMPANIES - GESTIÓN DE EMPRESAS
# =====================================================

@router.get("/companies", response_model=List[CompanyListItem])
async def get_all_companies(
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Máximo de registros"),
    status: Optional[str] = Query(None, description="Filtrar por estado: active, suspended, trial"),
    plan: Optional[str] = Query(None, description="Filtrar por plan"),
    search: Optional[str] = Query(None, description="Buscar por nombre, subdominio o email"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Listar todas las empresas**
    
    Obtiene el listado de todas las empresas registradas con filtros opcionales.
    
    **Filtros disponibles:**
    - `status`: active, suspended, trial, cancelled
    - `plan`: basic, professional, enterprise, custom
    - `search`: Buscar en nombre, subdominio o email
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_all_companies(skip, limit, status, plan, search)


@router.get("/companies/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Obtener detalles de una empresa**
    
    Obtiene información completa de una empresa específica.
    
    **Incluye:**
    - Información básica y de contacto
    - Configuración de suscripción
    - Límites y uso actual
    - Facturación
    - Métricas calculadas
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_company(company_id)


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_data: CompanyCreate,
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Crear nueva empresa (tenant)**
    
    Crea una nueva empresa en el sistema con su configuración inicial.
    
    **Proceso:**
    1. Valida que el subdominio sea único
    2. Crea la empresa con estado 'trial'
    3. Configura límites según el plan
    4. Calcula fecha de próxima facturación
    
    **Siguiente paso:** Crear usuario 'boss' para la empresa
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.create_company(company_data, current_user.id)


@router.put("/companies/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: int = Path(..., description="ID de la empresa"),
    company_data: CompanyUpdate = Body(...),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Actualizar configuración de empresa**
    
    Actualiza la configuración de una empresa existente.
    
    **Campos actualizables:**
    - Información de contacto
    - Configuración de suscripción
    - Límites de recursos
    - Estado de activación
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.update_company(company_id, company_data)


@router.post("/companies/{company_id}/suspend", response_model=CompanyResponse)
async def suspend_company(
    company_id: int = Path(..., description="ID de la empresa"),
    reason: str = Body(..., embed=True, description="Razón de la suspensión"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU005: Suspender empresa por incumplimiento de pago**
    
    Suspende el acceso de una empresa al sistema.
    
    **Efectos:**
    - Cambia estado a 'suspended'
    - Desactiva la empresa (is_active = False)
    - Registra razón de suspensión
    - Los usuarios no podrán iniciar sesión
    
    **Razones comunes:**
    - Impago de facturas
    - Violación de términos de servicio
    - Solicitud del cliente
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.suspend_company(company_id, reason)


@router.post("/companies/{company_id}/activate", response_model=CompanyResponse)
async def activate_company(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU005: Activar empresa suspendida**
    
    Reactiva el acceso de una empresa previamente suspendida.
    
    **Efectos:**
    - Cambia estado a 'active'
    - Activa la empresa (is_active = True)
    - Limpia razón de suspensión
    - Los usuarios pueden volver a iniciar sesión
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.activate_company(company_id)


@router.delete("/companies/{company_id}")
async def delete_company(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Eliminar empresa (soft delete)**
    
    Elimina lógicamente una empresa del sistema.
    
    **Nota:** Es un soft delete - los datos se mantienen pero la empresa
    queda inactiva y con estado 'cancelled'.
    
    **Efectos:**
    - Cambia estado a 'cancelled'
    - Desactiva la empresa
    - Mantiene datos históricos
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.delete_company(company_id)


# =====================================================
# SUBSCRIPTIONS - GESTIÓN DE SUSCRIPCIONES
# =====================================================

@router.post("/subscriptions/change")
async def change_subscription(
    change_data: SubscriptionChangeCreate,
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Cambiar plan de suscripción**
    
    Cambia el plan de suscripción de una empresa.
    
    **Proceso:**
    1. Registra el cambio en historial
    2. Actualiza límites y precios
    3. Mantiene auditoría completa
    
    **Casos de uso:**
    - Upgrade de plan (más recursos)
    - Downgrade de plan (menos recursos)
    - Cambio de precio por promoción
    - Personalización para clientes enterprise
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.change_subscription(change_data, current_user.id)


@router.get("/subscriptions/{company_id}/history")
async def get_subscription_history(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Historial de cambios de suscripción**
    
    Obtiene el historial completo de cambios de plan de una empresa.
    
    **Información incluida:**
    - Plan anterior y nuevo
    - Cambios en límites
    - Cambios en precios
    - Razón del cambio
    - Fecha efectiva
    - Usuario que realizó el cambio
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_subscription_history(company_id)


# =====================================================
# INVOICES - FACTURACIÓN
# =====================================================

@router.get("/invoices")
async def get_all_invoices(
    status: Optional[str] = Query(None, description="Filtrar por estado: pending, paid, overdue"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Listar todas las facturas**
    
    Obtiene el listado de todas las facturas del sistema.
    
    **Filtros:**
    - `status`: pending, paid, overdue, cancelled
    
    **Útil para:**
    - Monitoreo de pagos pendientes
    - Seguimiento de ingresos
    - Identificar clientes con pagos vencidos
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_all_invoices(status, skip, limit)


@router.get("/invoices/company/{company_id}")
async def get_company_invoices(
    company_id: int = Path(..., description="ID de la empresa"),
    status: Optional[str] = Query(None, description="Filtrar por estado"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Facturas de una empresa**
    
    Obtiene todas las facturas de una empresa específica.
    
    **Información incluida:**
    - Número de factura
    - Período de facturación
    - Desglose de costos
    - Estado de pago
    - Fechas relevantes
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_company_invoices(company_id, status)


@router.post("/invoices/generate/{company_id}")
async def generate_invoice(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Generar factura mensual**
    
    Genera una nueva factura para una empresa.
    
    **Cálculos automáticos:**
    - Período de facturación según billing_day
    - Cantidad de ubicaciones activas
    - Subtotal = ubicaciones × precio_por_ubicación
    - IVA (19% en Colombia)
    - Total con impuestos
    
    **Proceso:**
    1. Calcula período y montos
    2. Genera número de factura único
    3. Establece fecha de vencimiento (15 días)
    4. Actualiza fechas de facturación de la empresa
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.generate_invoice(company_id)


@router.post("/invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(
    invoice_id: int = Path(..., description="ID de la factura"),
    payment_data: InvoiceMarkPaid = Body(...),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU002: Marcar factura como pagada**
    
    Registra el pago de una factura.
    
    **Información requerida:**
    - Método de pago (transferencia, tarjeta, etc.)
    - Referencia del pago (opcional)
    - Fecha de pago
    
    **Efectos:**
    - Cambia estado a 'paid'
    - Registra detalles del pago
    - Actualiza métricas financieras
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.mark_invoice_paid(invoice_id, payment_data)


# =====================================================
# METRICS & ANALYTICS - MONITOREO Y REPORTES
# =====================================================

@router.get("/metrics/global", response_model=GlobalMetrics)
async def get_global_metrics(
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU003: Métricas globales del sistema**
    
    Dashboard ejecutivo con métricas consolidadas de todas las empresas.
    
    **Métricas incluidas:**
    
    **Empresas:**
    - Total de empresas
    - Empresas activas
    - Empresas suspendidas
    - Empresas en trial
    
    **Recursos:**
    - Total de ubicaciones
    - Total de empleados
    
    **Financiero:**
    - MRR (Monthly Recurring Revenue)
    - Facturas pendientes
    - Facturas vencidas
    
    **Alertas:**
    - Empresas cerca del límite de recursos
    - Suscripciones por vencer
    - Pagos vencidos
    
    **Crecimiento:**
    - Nuevas empresas este mes
    - Empresas canceladas este mes
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_global_metrics()


@router.get("/metrics/company/{company_id}", response_model=CompanyMetrics)
async def get_company_metrics(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU003: Métricas detalladas de una empresa**
    
    Análisis profundo del uso y rendimiento de una empresa.
    
    **Métricas de uso:**
    - Ubicaciones utilizadas vs límite
    - Empleados activos vs límite
    - Porcentajes de uso
    
    **Métricas financieras:**
    - Costo mensual actual
    - Total pagado históricamente
    - Total pendiente de pago
    
    **Métricas de actividad:**
    - Último login de usuarios
    - Usuarios activos
    - Ventas del mes actual
    
    **Estado:**
    - Estado de suscripción
    - Días hasta renovación
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_company_metrics(company_id)


@router.get("/reports/financial")
async def generate_financial_report(
    start_date: str = Query(..., description="Fecha inicio (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Fecha fin (YYYY-MM-DD)"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU006: Reporte financiero consolidado**
    
    Genera reporte financiero para un período específico.
    
    **Información incluida:**
    - Ingresos totales por período
    - Ingresos por empresa
    - Desglose por plan de suscripción
    - Facturas pagadas vs pendientes
    - Tasa de conversión trial → paid
    - Churn rate (empresas canceladas)
    
    **Formatos disponibles:** JSON (futuros: PDF, Excel)
    
    **Permisos:** Solo superadmin
    """
    # TODO: Implementar generación de reporte
    return {
        "message": "Reporte financiero en desarrollo",
        "period": {
            "start": start_date,
            "end": end_date
        }
    }


# =====================================================
# PLAN TEMPLATES - PLANTILLAS DE PLANES
# =====================================================

@router.get("/plans", response_model=List[PlanTemplateResponse])
async def get_all_plan_templates(
    active_only: bool = Query(True, description="Solo planes activos"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **Listar plantillas de planes disponibles**
    
    Obtiene todas las plantillas de planes de suscripción.
    
    **Uso:**
    - Referencia al crear nuevas empresas
    - Configuración de upgrades/downgrades
    - Gestión de catálogo de productos
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    plans = service.repository.get_all_plan_templates(active_only)
    
    return [
        PlanTemplateResponse(
            id=p.id,
            plan_code=p.plan_code,
            display_name=p.display_name,
            description=p.description,
            max_locations=p.max_locations,
            max_employees=p.max_employees,
            price_per_location=p.price_per_location,
            features=p.features,
            is_active=p.is_active,
            sort_order=p.sort_order,
            created_at=p.created_at,
            updated_at=p.updated_at
        )
        for p in plans
    ]


@router.post("/plans", response_model=PlanTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_plan_template(
    plan_data: PlanTemplateCreate,
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **Crear nueva plantilla de plan**
    
    Crea un nuevo plan de suscripción disponible para las empresas.
    
    **Configuración incluida:**
    - Límites de recursos
    - Precios
    - Características incluidas
    - Orden de visualización
    
    **Permisos:** Solo superadmin
    """
    from app.shared.database.models import PlanTemplate
    
    plan = PlanTemplate(
        plan_code=plan_data.plan_code,
        display_name=plan_data.display_name,
        description=plan_data.description,
        max_locations=plan_data.max_locations,
        max_employees=plan_data.max_employees,
        price_per_location=plan_data.price_per_location,
        features=plan_data.features,
        sort_order=plan_data.sort_order,
        is_active=True
    )
    
    service = SuperadminService(db)
    plan = service.repository.create_plan_template(plan)
    
    return PlanTemplateResponse(
        id=plan.id,
        plan_code=plan.plan_code,
        display_name=plan.display_name,
        description=plan.description,
        max_locations=plan.max_locations,
        max_employees=plan.max_employees,
        price_per_location=plan.price_per_location,
        features=plan.features,
        is_active=plan.is_active,
        sort_order=plan.sort_order,
        created_at=plan.created_at,
        updated_at=plan.updated_at
    )


# =====================================================
# HEALTH & INFO
# =====================================================

@router.get("/health")
async def superadmin_health():
    """
    Health check del módulo de superadmin
    """
    return {
        "service": "superadmin",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "SU001 - Gestión de empresas",
            "SU002 - Gestión de suscripciones y facturación",
            "SU003 - Métricas globales",
            "SU004 - Notificaciones (en desarrollo)",
            "SU005 - Suspender/activar servicios",
            "SU006 - Reportes financieros (en desarrollo)"
        ]
    }

@router.post("/companies/{company_id}/boss", response_model=BossResponse, status_code=status.HTTP_201_CREATED)
async def create_company_boss(
    company_id: int = Path(..., description="ID de la empresa"),
    boss_data: BossCreate = Body(...),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Crear usuario Boss para una empresa**
    
    Crea el usuario Boss (dueño/director ejecutivo) de una empresa.
    Solo puede existir UN Boss por empresa.
    
    **Proceso:**
    1. Valida que la empresa existe y está activa
    2. Verifica que NO exista ya un Boss para esta empresa
    3. Valida que el email no esté registrado
    4. Crea el usuario con rol 'boss'
    5. Asocia el usuario a la empresa
    
    **Siguiente paso en el flujo:**
    - El Boss podrá iniciar sesión
    - El Boss podrá crear locales (BS008)
    - El Boss podrá crear bodegas (BS009)
    - El Boss podrá crear y asignar administradores (BS011)
    
    **Validaciones:**
    - Solo un Boss por empresa
    - Email único en todo el sistema
    - Password con requisitos de seguridad
    - Empresa activa
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.create_company_boss(company_id, boss_data, current_user.id)


@router.get("/companies/{company_id}/with-boss", response_model=CompanyWithBossResponse)
async def get_company_with_boss(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Obtener empresa con su usuario Boss**
    
    Obtiene la información completa de una empresa incluyendo
    su usuario Boss (si ya fue creado).
    
    **Útil para:**
    - Verificar si una empresa ya tiene Boss
    - Obtener información del Boss existente
    - Validar el flujo de configuración inicial
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    return await service.get_company_with_boss(company_id)


@router.get("/companies/{company_id}/boss", response_model=BossResponse)
async def get_company_boss(
    company_id: int = Path(..., description="ID de la empresa"),
    current_user: User = Depends(get_superadmin_user),
    db: Session = Depends(get_db)
):
    """
    **SU001: Obtener solo el usuario Boss de una empresa**
    
    Retorna únicamente la información del Boss.
    
    **Error 404 si:** No existe Boss para la empresa
    
    **Permisos:** Solo superadmin
    """
    service = SuperadminService(db)
    company = service.repository.get_company(company_id)
    
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empresa con ID {company_id} no encontrada"
        )
    
    boss = service.repository.get_company_boss(company_id)
    
    if not boss:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe Boss para la empresa '{company.name}'. Créalo primero."
        )
    
    return BossResponse(
        id=boss.id,
        email=boss.email,
        first_name=boss.first_name,
        last_name=boss.last_name,
        full_name=boss.full_name,
        role=boss.role,
        company_id=boss.company_id,
        company_name=company.name,
        is_active=boss.is_active,
        created_at=boss.created_at,
        created_by_superadmin_id=boss.created_by
    )