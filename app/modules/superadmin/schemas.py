# app/modules/superadmin/schemas.py
from this import s
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from decimal import Decimal
from enum import Enum


# =====================================================
# ENUMS
# =====================================================

class SubscriptionPlan(str, Enum):
    """Planes de suscripción disponibles"""
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class SubscriptionStatus(str, Enum):
    """Estados de suscripción"""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    TRIAL = "trial"
    OVERDUE = "overdue"


class InvoiceStatus(str, Enum):
    """Estados de factura"""
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


# =====================================================
# COMPANY SCHEMAS
# =====================================================

class CompanyCreate(BaseModel):
    """Schema para crear una nueva empresa"""
    name: str = Field(..., min_length=2, max_length=255, description="Nombre comercial de la empresa")
    subdomain: str = Field(..., min_length=3, max_length=100, description="Subdominio único (ej: empresa.tustockya.com)")
    legal_name: Optional[str] = Field(None, max_length=255, description="Razón social")
    tax_id: Optional[str] = Field(None, max_length=50, description="NIT o RUT")
    email: str = Field(..., description="Email principal de la empresa")
    phone: Optional[str] = Field(None, max_length=50, description="Teléfono de contacto")
    
    # Configuración de suscripción
    subscription_plan: SubscriptionPlan = Field(default=SubscriptionPlan.BASIC, description="Plan de suscripción")
    max_locations: int = Field(default=3, ge=1, description="Máximo de ubicaciones permitidas")
    max_employees: int = Field(default=10, ge=1, description="Máximo de empleados permitidos")
    price_per_location: Decimal = Field(default=Decimal("50.00"), ge=0, description="Precio por ubicación/mes")
    
    # Facturación
    billing_day: int = Field(default=1, ge=1, le=28, description="Día del mes para facturación")
    subscription_ends_at: Optional[datetime] = Field(None, description="Fecha de fin de suscripción")
    
    # Configuración adicional
    settings: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Configuración personalizada")
    
    @field_validator('subdomain')
    @classmethod
    def validate_subdomain(cls, v: str) -> str:
        """Validar formato de subdominio"""
        if not v.isalnum() and '-' not in v:
            raise ValueError('El subdominio solo puede contener letras, números y guiones')
        if v.startswith('-') or v.endswith('-'):
            raise ValueError('El subdominio no puede iniciar o terminar con guión')
        return v.lower()
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Zapatería Deportiva ABC",
                "subdomain": "abc-sports",
                "legal_name": "Zapatería ABC S.A.S",
                "tax_id": "900123456-7",
                "email": "contacto@abc-sports.com",
                "phone": "+57 300 1234567",
                "subscription_plan": "professional",
                "max_locations": 5,
                "max_employees": 20,
                "price_per_location": 75.00,
                "billing_day": 1
            }
        }


class CompanyUpdate(BaseModel):
    """Schema para actualizar una empresa"""
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    legal_name: Optional[str] = Field(None, max_length=255)
    tax_id: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)
    
    subscription_plan: Optional[SubscriptionPlan] = None
    subscription_status: Optional[SubscriptionStatus] = None
    max_locations: Optional[int] = Field(None, ge=1)
    max_employees: Optional[int] = Field(None, ge=1)
    price_per_location: Optional[Decimal] = Field(None, ge=0)
    
    billing_day: Optional[int] = Field(None, ge=1, le=28)
    subscription_ends_at: Optional[datetime] = None
    
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "subscription_plan": "enterprise",
                "max_locations": 10,
                "subscription_status": "active"
            }
        }


class CompanyResponse(BaseModel):
    """Schema para respuesta de empresa"""
    id: int
    name: str
    subdomain: str
    legal_name: Optional[str]
    tax_id: Optional[str]
    email: str
    phone: Optional[str]
    
    # Suscripción
    subscription_plan: str
    subscription_status: str
    subscription_started_at: datetime
    subscription_ends_at: Optional[datetime]
    
    # Límites
    max_locations: int
    max_employees: int
    price_per_location: Decimal
    
    # Uso actual
    current_locations_count: int
    current_employees_count: int
    
    # Facturación
    billing_day: int
    last_billing_date: Optional[date]
    next_billing_date: Optional[date]
    
    # Métricas calculadas
    monthly_cost: Decimal
    is_at_location_limit: bool
    is_at_employee_limit: bool
    
    # Auditoría
    is_active: bool
    created_at: datetime
    updated_at: datetime
    created_by_user_id: Optional[int]
    
    class Config:
        from_attributes = True


class CompanyListItem(BaseModel):
    """Schema para listado de empresas (versión resumida)"""
    id: int
    name: str
    subdomain: str
    email: str
    subscription_plan: str
    subscription_status: str
    current_locations_count: int
    current_employees_count: int
    monthly_cost: Decimal
    next_billing_date: Optional[date]
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


# =====================================================
# SUBSCRIPTION SCHEMAS
# =====================================================

class SubscriptionChangeCreate(BaseModel):
    """Schema para registrar cambio de suscripción"""
    company_id: int
    new_plan: SubscriptionPlan
    new_max_locations: int = Field(..., ge=1)
    new_max_employees: int = Field(..., ge=1)
    new_price_per_location: Decimal = Field(..., ge=0)
    reason: Optional[str] = Field(None, max_length=500)
    effective_date: date = Field(default_factory=date.today)
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_id": 1,
                "new_plan": "enterprise",
                "new_max_locations": 15,
                "new_max_employees": 50,
                "new_price_per_location": 100.00,
                "reason": "Expansión a nuevas ciudades",
                "effective_date": "2025-11-01"
            }
        }


class SubscriptionChangeResponse(BaseModel):
    """Schema para respuesta de cambio de suscripción"""
    id: int
    company_id: int
    company_name: str
    
    old_plan: Optional[str]
    new_plan: str
    old_max_locations: Optional[int]
    new_max_locations: int
    old_max_employees: Optional[int]
    new_max_employees: int
    old_price_per_location: Optional[Decimal]
    new_price_per_location: Decimal
    
    reason: Optional[str]
    effective_date: date
    changed_by_user_id: Optional[int]
    created_at: datetime
    
    class Config:
        from_attributes = True


# =====================================================
# INVOICE SCHEMAS
# =====================================================

class InvoiceCreate(BaseModel):
    """Schema para crear factura"""
    company_id: int
    billing_period_start: date
    billing_period_end: date
    locations_count: int = Field(..., ge=0)
    price_per_location: Decimal = Field(..., ge=0)
    tax_percentage: Decimal = Field(default=Decimal("19.00"), ge=0, le=100)
    due_date: date
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    """Schema para respuesta de factura"""
    id: int
    company_id: int
    company_name: str
    
    invoice_number: str
    billing_period_start: date
    billing_period_end: date
    
    locations_count: int
    price_per_location: Decimal
    subtotal: Decimal
    tax_percentage: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    
    status: str
    due_date: date
    paid_at: Optional[datetime]
    payment_method: Optional[str]
    payment_reference: Optional[str]
    
    notes: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class InvoiceMarkPaid(BaseModel):
    """Schema para marcar factura como pagada"""
    payment_method: str = Field(..., max_length=50, description="Método de pago utilizado")
    payment_reference: Optional[str] = Field(None, max_length=100, description="Referencia del pago")
    paid_at: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Fecha de pago")
    
    class Config:
        json_schema_extra = {
            "example": {
                "payment_method": "transferencia_bancaria",
                "payment_reference": "TRX-2025-001234",
                "paid_at": "2025-10-13T10:30:00"
            }
        }


# =====================================================
# PLAN TEMPLATE SCHEMAS
# =====================================================

class PlanTemplateCreate(BaseModel):
    """Schema para crear plantilla de plan"""
    plan_code: str = Field(..., max_length=20)
    display_name: str = Field(..., max_length=100)
    description: Optional[str] = None
    max_locations: int = Field(..., ge=1)
    max_employees: int = Field(..., ge=1)
    price_per_location: Decimal = Field(..., ge=0)
    features: Optional[Dict[str, Any]] = Field(default_factory=dict)
    sort_order: int = Field(default=0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "plan_code": "PREMIUM",
                "display_name": "Plan Premium",
                "description": "Plan para empresas en crecimiento",
                "max_locations": 10,
                "max_employees": 30,
                "price_per_location": 80.00,
                "features": {
                    "advanced_reports": True,
                    "api_access": True,
                    "priority_support": True
                },
                "sort_order": 2
            }
        }


class PlanTemplateResponse(BaseModel):
    """Schema para respuesta de plantilla de plan"""
    id: int
    plan_code: str
    display_name: str
    description: Optional[str]
    max_locations: int
    max_employees: int
    price_per_location: Decimal
    features: Dict[str, Any]
    is_active: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# =====================================================
# DASHBOARD & METRICS SCHEMAS
# =====================================================

class GlobalMetrics(BaseModel):
    """Schema para métricas globales del sistema"""
    # Empresas
    total_companies: int
    active_companies: int
    suspended_companies: int
    trial_companies: int
    
    # Suscripciones
    total_locations: int
    total_employees: int
    
    # Financiero
    monthly_recurring_revenue: Decimal
    pending_invoices_amount: Decimal
    overdue_invoices_amount: Decimal
    
    # Alertas
    companies_near_limit: int
    subscriptions_expiring_soon: int
    overdue_payments: int
    
    # Crecimiento
    new_companies_this_month: int
    cancelled_companies_this_month: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_companies": 45,
                "active_companies": 42,
                "suspended_companies": 2,
                "trial_companies": 1,
                "total_locations": 180,
                "total_employees": 520,
                "monthly_recurring_revenue": 13500.00,
                "pending_invoices_amount": 4500.00,
                "overdue_invoices_amount": 800.00,
                "companies_near_limit": 5,
                "subscriptions_expiring_soon": 3,
                "overdue_payments": 2,
                "new_companies_this_month": 3,
                "cancelled_companies_this_month": 1
            }
        }


class CompanyMetrics(BaseModel):
    """Schema para métricas detalladas de una empresa"""
    company_id: int
    company_name: str
    
    # Uso de recursos
    locations_count: int
    locations_limit: int
    locations_usage_percent: float
    
    employees_count: int
    employees_limit: int
    employees_usage_percent: float
    
    # Financiero
    current_plan: str
    monthly_cost: Decimal
    total_paid: Decimal
    total_pending: Decimal
    
    # Actividad
    last_login: Optional[datetime] = None
    active_users_count: int
    total_sales_this_month: Decimal
    
    # Estado
    subscription_status: str
    days_until_renewal: Optional[int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "company_id": 1,
                "company_name": "Zapatería ABC",
                "locations_count": 4,
                "locations_limit": 5,
                "locations_usage_percent": 80.0,
                "employees_count": 15,
                "employees_limit": 20,
                "employees_usage_percent": 75.0,
                "current_plan": "professional",
                "monthly_cost": 300.00,
                "total_paid": 1800.00,
                "total_pending": 300.00,
                "last_login": "2025-10-13T09:30:00",
                "active_users_count": 12,
                "total_sales_this_month": 45000.00,
                "subscription_status": "active",
                "days_until_renewal": 18
            }
        }


# =====================================================
# FIRST SUPERADMIN CREATION
# =====================================================

class FirstSuperadminCreate(BaseModel):
    """Schema para crear el primer superadmin (solo una vez)"""
    email: str
    password: str = Field(..., min_length=8, max_length=100)
    first_name: str = Field(..., min_length=2, max_length=255)
    last_name: str = Field(..., min_length=2, max_length=255)
    secret_key: str = Field(..., description="Clave secreta de instalación")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        """Validar fortaleza de contraseña"""
        if len(v) < 8:
            raise ValueError('La contraseña debe tener al menos 8 caracteres')
        if not any(c.isupper() for c in v):
            raise ValueError('La contraseña debe contener al menos una mayúscula')
        if not any(c.islower() for c in v):
            raise ValueError('La contraseña debe contener al menos una minúscula')
        if not any(c.isdigit() for c in v):
            raise ValueError('La contraseña debe contener al menos un número')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "superadmin@tustockya.com",
                "password": "SuperAdmin123!",
                "first_name": "Super",
                "last_name": "Administrador",
                "secret_key": "INSTALL_SECRET_KEY_2025"
            }
        }