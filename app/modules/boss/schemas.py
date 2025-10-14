# app/modules/boss/schemas.py
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from decimal import Decimal
from datetime import datetime, date
from enum import Enum

# ==================== ENUMS ====================

class LocationType(str, Enum):
    """Tipo de ubicación"""
    LOCAL = "local"
    BODEGA = "bodega"

class ReportPeriod(str, Enum):
    """Período de reporte"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

# ==================== CREACIÓN DE UBICACIONES ====================

class LocationCreate(BaseModel):
    """Schema para crear nueva ubicación (local o bodega)"""
    name: str = Field(..., min_length=3, max_length=255, description="Nombre de la ubicación")
    type: LocationType = Field(..., description="Tipo: local o bodega")
    address: Optional[str] = Field(None, max_length=500, description="Dirección física")
    phone: Optional[str] = Field(None, max_length=20, description="Teléfono de contacto")
    manager_name: Optional[str] = Field(None, max_length=255, description="Nombre del encargado")
    capacity: Optional[int] = Field(None, gt=0, description="Capacidad de almacenamiento (bodegas)")
    notes: Optional[str] = Field(None, max_length=1000, description="Notas adicionales")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('El nombre no puede estar vacío')
        return v.strip()
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Local Centro Comercial",
                "type": "local",
                "address": "Av. Principal 123, Piso 2",
                "phone": "+57 300 1234567",
                "manager_name": "Juan Pérez"
            }
        }

class LocationResponse(BaseModel):
    """Respuesta de ubicación creada"""
    id: int
    company_id: int
    name: str
    type: str
    address: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime
    created_by_name: Optional[str]
    
    # Métricas básicas
    total_users: int = 0
    total_products: int = 0
    total_inventory_value: Decimal = Decimal('0')

# ==================== DASHBOARD EJECUTIVO ====================

class KPIMetric(BaseModel):
    """Métrica KPI individual"""
    label: str
    value: Decimal
    previous_value: Optional[Decimal] = None
    change_percentage: Optional[float] = None
    trend: Optional[str] = None  # "up", "down", "stable"
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class LocationPerformance(BaseModel):
    """Performance de una ubicación"""
    location_id: int
    location_name: str
    location_type: str
    daily_sales: Decimal
    monthly_sales: Decimal
    inventory_value: Decimal
    active_users: int
    pending_transfers: int
    efficiency_score: float  # 0-100

class ExecutiveDashboard(BaseModel):
    """Dashboard ejecutivo completo - BS001"""
    company_name: str
    boss_name: str
    dashboard_date: date
    
    # KPIs principales
    kpis: Dict[str, KPIMetric]
    
    # Performance por ubicación
    locations_performance: List[LocationPerformance]
    
    # Resumen financiero
    financial_summary: Dict[str, Decimal]
    
    # Alertas y notificaciones
    alerts: List[Dict[str, Any]]
    
    # Métricas de crecimiento
    growth_metrics: Dict[str, Any]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

# ==================== REPORTES CONSOLIDADOS ====================

class SalesConsolidatedReport(BaseModel):
    """Reporte consolidado de ventas - BS002"""
    report_period: str
    start_date: date
    end_date: date
    generated_at: datetime
    
    # Totales generales
    total_sales: Decimal
    total_transactions: int
    average_ticket: Decimal
    
    # Por ubicación
    sales_by_location: List[Dict[str, Any]]
    
    # Por vendedor (top performers)
    top_sellers: List[Dict[str, Any]]
    
    # Por producto (más vendidos)
    top_products: List[Dict[str, Any]]
    
    # Tendencias
    daily_trend: Optional[List[Dict[str, Any]]] = None
    
    # Métodos de pago
    payment_methods_breakdown: Dict[str, Decimal]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

class ReportFilters(BaseModel):
    """Filtros para generar reportes"""
    start_date: date = Field(..., description="Fecha inicio")
    end_date: date = Field(..., description="Fecha fin")
    location_ids: Optional[List[int]] = Field(None, description="Filtrar por ubicaciones específicas")
    include_inactive: bool = Field(default=False, description="Incluir ubicaciones inactivas")
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('La fecha fin debe ser posterior a la fecha inicio')
        return v

# ==================== INVENTARIO CONSOLIDADO ====================

class CategoryInventory(BaseModel):
    """Inventario por categoría"""
    category_name: str  # brand o model
    total_units: int
    total_value: Decimal
    locations_count: int
    percentage_of_total: float

class LocationInventory(BaseModel):
    """Inventario por ubicación"""
    location_id: int
    location_name: str
    location_type: str
    total_products: int
    total_units: int
    total_value: Decimal
    low_stock_items: int

class ConsolidatedInventory(BaseModel):
    """Inventario total consolidado - BS003"""
    report_date: date
    total_locations: int
    
    # Totales generales
    total_products: int
    total_units: int
    total_value: Decimal
    
    # Por categoría (brand)
    by_brand: List[CategoryInventory]
    
    # Por ubicación
    by_location: List[LocationInventory]
    
    # Alertas
    low_stock_alerts: int
    out_of_stock_alerts: int
    overstocked_alerts: int
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }

# ==================== ANÁLISIS FINANCIERO ====================

class LocationFinancials(BaseModel):
    """Financieros por ubicación"""
    location_id: int
    location_name: str
    location_type: str
    
    # Ingresos
    total_sales: Decimal
    
    # Costos
    operational_costs: Decimal
    cost_breakdown: Dict[str, Decimal]
    
    # Márgenes
    gross_profit: Decimal
    profit_margin_percentage: float
    
    # ROI
    roi_percentage: Optional[float] = None

class FinancialAnalysis(BaseModel):
    """Análisis financiero completo - BS004"""
    analysis_period: str
    start_date: date
    end_date: date
    
    # Totales consolidados
    total_revenue: Decimal
    total_costs: Decimal
    net_profit: Decimal
    overall_margin_percentage: float
    
    # Por ubicación
    locations_financials: List[LocationFinancials]
    
    # Costos por tipo
    costs_by_type: Dict[str, Decimal]
    
    # Comparativas
    best_performing_location: Optional[Dict[str, Any]]
    worst_performing_location: Optional[Dict[str, Any]]
    
    # Tendencias
    margin_trend: Optional[List[Dict[str, Any]]]
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v)
        }