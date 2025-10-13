# app/modules/superadmin/service.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from fastapi import HTTPException, status

from app.shared.database.models import (
    Company, User, CompanyInvoice, SubscriptionChange, 
    PlanTemplate, Location
)
from app.core.auth.service import AuthService
from .repository import SuperadminRepository
from .schemas import (
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyListItem,
    SubscriptionChangeCreate, InvoiceCreate, InvoiceMarkPaid,
    PlanTemplateCreate, GlobalMetrics, CompanyMetrics,
    FirstSuperadminCreate
)


class SuperadminService:
    """Service para lógica de negocio de superadmin"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = SuperadminRepository(db)
    
    # =====================================================
    # COMPANIES
    # =====================================================
    
    async def get_all_companies(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        plan: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[CompanyListItem]:
        """Obtener listado de todas las empresas"""
        companies = self.repository.get_all_companies(skip, limit, status, plan, search)
        
        return [
            CompanyListItem(
                id=c.id,
                name=c.name,
                subdomain=c.subdomain,
                email=c.email,
                subscription_plan=c.subscription_plan,
                subscription_status=c.subscription_status,
                current_locations_count=c.current_locations_count,
                current_employees_count=c.current_employees_count,
                monthly_cost=c.monthly_cost,
                next_billing_date=c.next_billing_date,
                is_active=c.is_active,
                created_at=c.created_at
            )
            for c in companies
        ]
    
    async def get_company(self, company_id: int) -> CompanyResponse:
        """Obtener detalles de una empresa"""
        company = self.repository.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        return CompanyResponse(
            id=company.id,
            name=company.name,
            subdomain=company.subdomain,
            legal_name=company.legal_name,
            tax_id=company.tax_id,
            email=company.email,
            phone=company.phone,
            subscription_plan=company.subscription_plan,
            subscription_status=company.subscription_status,
            subscription_started_at=company.subscription_started_at,
            subscription_ends_at=company.subscription_ends_at,
            max_locations=company.max_locations,
            max_employees=company.max_employees,
            price_per_location=company.price_per_location,
            current_locations_count=company.current_locations_count,
            current_employees_count=company.current_employees_count,
            billing_day=company.billing_day,
            last_billing_date=company.last_billing_date,
            next_billing_date=company.next_billing_date,
            monthly_cost=company.monthly_cost,
            is_at_location_limit=company.is_at_location_limit,
            is_at_employee_limit=company.is_at_employee_limit,
            is_active=company.is_active,
            created_at=company.created_at,
            updated_at=company.updated_at,
            created_by_user_id=company.created_by_user_id
        )
    
    async def create_company(
        self,
        company_data: CompanyCreate,
        created_by_user_id: int
    ) -> CompanyResponse:
        """Crear nueva empresa"""
        
        # Validar que el subdominio no exista
        existing = self.repository.get_company_by_subdomain(company_data.subdomain)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El subdominio '{company_data.subdomain}' ya está en uso"
            )
        
        # Calcular fecha de próxima facturación
        today = date.today()
        if today.day <= company_data.billing_day:
            next_billing = today.replace(day=company_data.billing_day)
        else:
            # Siguiente mes
            if today.month == 12:
                next_billing = date(today.year + 1, 1, company_data.billing_day)
            else:
                next_billing = date(today.year, today.month + 1, company_data.billing_day)
        
        # Crear empresa
        company = Company(
            name=company_data.name,
            subdomain=company_data.subdomain,
            legal_name=company_data.legal_name,
            tax_id=company_data.tax_id,
            email=company_data.email,
            phone=company_data.phone,
            subscription_plan=company_data.subscription_plan,
            subscription_status="trial",  # Iniciar en trial
            subscription_started_at=datetime.utcnow(),
            subscription_ends_at=company_data.subscription_ends_at,
            max_locations=company_data.max_locations,
            max_employees=company_data.max_employees,
            price_per_location=company_data.price_per_location,
            current_locations_count=0,
            current_employees_count=0,
            billing_day=company_data.billing_day,
            next_billing_date=next_billing,
            settings=company_data.settings or {},
            is_active=True,
            created_by_user_id=created_by_user_id
        )
        
        company = self.repository.create_company(company)
        
        return await self.get_company(company.id)
    
    async def update_company(
        self,
        company_id: int,
        company_data: CompanyUpdate
    ) -> CompanyResponse:
        """Actualizar empresa"""
        company = self.repository.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        # Actualizar campos
        update_data = company_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(company, field, value)
        
        company = self.repository.update_company(company)
        
        return await self.get_company(company.id)
    
    async def suspend_company(self, company_id: int, reason: str) -> CompanyResponse:
        """Suspender empresa por impago o violación de términos"""
        company = self.repository.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        company.subscription_status = "suspended"
        company.is_active = False
        
        # Agregar nota en settings
        if not company.settings:
            company.settings = {}
        company.settings["suspension_reason"] = reason
        company.settings["suspended_at"] = datetime.utcnow().isoformat()
        
        company = self.repository.update_company(company)
        
        return await self.get_company(company.id)
    
    async def activate_company(self, company_id: int) -> CompanyResponse:
        """Activar empresa suspendida"""
        company = self.repository.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        company.subscription_status = "active"
        company.is_active = True
        
        # Limpiar razón de suspensión
        if company.settings and "suspension_reason" in company.settings:
            del company.settings["suspension_reason"]
            del company.settings["suspended_at"]
        
        company = self.repository.update_company(company)
        
        return await self.get_company(company.id)
    
    async def delete_company(self, company_id: int) -> Dict[str, Any]:
        """Eliminar empresa (soft delete)"""
        success = self.repository.delete_company(company_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        return {
            "success": True,
            "message": f"Empresa {company_id} eliminada correctamente"
        }
    
    # =====================================================
    # SUBSCRIPTION CHANGES
    # =====================================================
    
    async def change_subscription(
        self,
        change_data: SubscriptionChangeCreate,
        changed_by_user_id: int
    ) -> Dict[str, Any]:
        """Cambiar plan de suscripción de una empresa"""
        company = self.repository.get_company_by_id(change_data.company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {change_data.company_id} no encontrada"
            )
        
        # Registrar cambio de suscripción
        change = SubscriptionChange(
            company_id=change_data.company_id,
            old_plan=company.subscription_plan,
            new_plan=change_data.new_plan,
            old_max_locations=company.max_locations,
            new_max_locations=change_data.new_max_locations,
            old_max_employees=company.max_employees,
            new_max_employees=change_data.new_max_employees,
            old_price_per_location=company.price_per_location,
            new_price_per_location=change_data.new_price_per_location,
            reason=change_data.reason,
            effective_date=change_data.effective_date,
            changed_by_user_id=changed_by_user_id
        )
        
        change = self.repository.create_subscription_change(change)
        
        # Actualizar empresa
        company.subscription_plan = change_data.new_plan
        company.max_locations = change_data.new_max_locations
        company.max_employees = change_data.new_max_employees
        company.price_per_location = change_data.new_price_per_location
        
        self.repository.update_company(company)
        
        return {
            "success": True,
            "message": "Plan de suscripción actualizado correctamente",
            "change_id": change.id,
            "old_plan": change.old_plan,
            "new_plan": change.new_plan,
            "effective_date": change.effective_date
        }
    
    async def get_subscription_history(self, company_id: int) -> List[Dict[str, Any]]:
        """Obtener historial de cambios de suscripción"""
        changes = self.repository.get_subscription_history(company_id)
        
        return [
            {
                "id": c.id,
                "old_plan": c.old_plan,
                "new_plan": c.new_plan,
                "old_max_locations": c.old_max_locations,
                "new_max_locations": c.new_max_locations,
                "old_max_employees": c.old_max_employees,
                "new_max_employees": c.new_max_employees,
                "old_price_per_location": c.old_price_per_location,
                "new_price_per_location": c.new_price_per_location,
                "reason": c.reason,
                "effective_date": c.effective_date,
                "changed_by_user_id": c.changed_by_user_id,
                "created_at": c.created_at
            }
            for c in changes
        ]
    
    # =====================================================
    # INVOICES
    # =====================================================
    
    async def generate_invoice(
        self,
        company_id: int
    ) -> Dict[str, Any]:
        """Generar factura mensual para una empresa"""
        company = self.repository.get_company_by_id(company_id)
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        # Calcular período de facturación
        today = date.today()
        if today.month == 1:
            billing_start = date(today.year - 1, 12, company.billing_day)
            billing_end = date(today.year, 1, company.billing_day) - timedelta(days=1)
        else:
            billing_start = date(today.year, today.month - 1, company.billing_day)
            billing_end = date(today.year, today.month, company.billing_day) - timedelta(days=1)
        
        # Calcular montos
        locations_count = company.current_locations_count
        price_per_location = company.price_per_location
        subtotal = Decimal(locations_count) * price_per_location
        tax_percentage = Decimal("19.00")  # IVA Colombia
        tax_amount = subtotal * (tax_percentage / Decimal("100"))
        total_amount = subtotal + tax_amount
        
        # Generar número de factura
        invoice_count = self.db.query(CompanyInvoice).count() + 1
        invoice_number = f"INV-{today.year}-{invoice_count:06d}"
        
        # Fecha de vencimiento (15 días)
        due_date = today + timedelta(days=15)
        
        # Crear factura
        invoice = CompanyInvoice(
            company_id=company_id,
            invoice_number=invoice_number,
            billing_period_start=billing_start,
            billing_period_end=billing_end,
            locations_count=locations_count,
            price_per_location=price_per_location,
            subtotal=subtotal,
            tax_percentage=tax_percentage,
            tax_amount=tax_amount,
            total_amount=total_amount,
            status="pending",
            due_date=due_date,
            details={
                "plan": company.subscription_plan,
                "locations": locations_count,
                "price_per_location": float(price_per_location)
            }
        )
        
        invoice = self.repository.create_invoice(invoice)
        
        # Actualizar empresa
        company.last_billing_date = today
        company.next_billing_date = billing_end + timedelta(days=company.billing_day)
        self.repository.update_company(company)
        
        return {
            "success": True,
            "message": "Factura generada correctamente",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "total_amount": invoice.total_amount,
            "due_date": invoice.due_date
        }
    
    async def mark_invoice_paid(
        self,
        invoice_id: int,
        payment_data: InvoiceMarkPaid
    ) -> Dict[str, Any]:
        """Marcar factura como pagada"""
        invoice = self.repository.get_invoice_by_id(invoice_id)
        
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factura con ID {invoice_id} no encontrada"
            )
        
        if invoice.status == "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La factura ya está marcada como pagada"
            )
        
        invoice = self.repository.mark_invoice_paid(
            invoice,
            payment_data.payment_method,
            payment_data.payment_reference,
            payment_data.paid_at
        )
        
        return {
            "success": True,
            "message": "Factura marcada como pagada",
            "invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "paid_at": invoice.paid_at,
            "payment_method": invoice.payment_method
        }
    
    async def get_all_invoices(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Obtener todas las facturas"""
        invoices = self.repository.get_all_invoices(status, skip, limit)
        
        return [
            {
                "id": inv.id,
                "company_id": inv.company_id,
                "company_name": inv.company.name,
                "invoice_number": inv.invoice_number,
                "billing_period_start": inv.billing_period_start,
                "billing_period_end": inv.billing_period_end,
                "total_amount": inv.total_amount,
                "status": inv.status,
                "due_date": inv.due_date,
                "paid_at": inv.paid_at,
                "created_at": inv.created_at
            }
            for inv in invoices
        ]
    
    async def get_company_invoices(
        self,
        company_id: int,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtener facturas de una empresa"""
        invoices = self.repository.get_company_invoices(company_id, status)
        
        return [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "billing_period_start": inv.billing_period_start,
                "billing_period_end": inv.billing_period_end,
                "locations_count": inv.locations_count,
                "price_per_location": inv.price_per_location,
                "subtotal": inv.subtotal,
                "tax_amount": inv.tax_amount,
                "total_amount": inv.total_amount,
                "status": inv.status,
                "due_date": inv.due_date,
                "paid_at": inv.paid_at,
                "payment_method": inv.payment_method,
                "created_at": inv.created_at
            }
            for inv in invoices
        ]
    
    # =====================================================
    # METRICS & ANALYTICS
    # =====================================================
    
    async def get_global_metrics(self) -> GlobalMetrics:
        """Obtener métricas globales del sistema"""
        metrics = self.repository.get_global_metrics()
        return GlobalMetrics(**metrics)
    
    async def get_company_metrics(self, company_id: int) -> CompanyMetrics:
        """Obtener métricas detalladas de una empresa"""
        metrics = self.repository.get_company_metrics(company_id)
        
        if not metrics:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empresa con ID {company_id} no encontrada"
            )
        
        return CompanyMetrics(**metrics)
    
    # =====================================================
    # FIRST SUPERADMIN SETUP
    # =====================================================
    
    async def create_first_superadmin(
        self,
        admin_data: FirstSuperadminCreate
    ) -> Dict[str, Any]:
        """Crear el primer superadmin (solo permitido una vez)"""
        
        # Verificar que no existan superadmins
        if self.repository.superadmin_exists():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Ya existe un superadmin en el sistema"
            )
        
        # Validar clave secreta (debe estar en variables de entorno)
        from app.config.settings import settings
        if admin_data.secret_key != getattr(settings, 'install_secret_key', 'CHANGE_ME_IN_PRODUCTION'):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Clave secreta incorrecta"
            )
        
        # Crear superadmin
        password_hash = AuthService.get_password_hash(admin_data.password)
        
        superadmin = User(
            email=admin_data.email,
            password_hash=password_hash,
            first_name=admin_data.first_name,
            last_name=admin_data.last_name,
            role="superadmin",
            company_id=None,  # Superadmin no pertenece a ninguna empresa
            location_id=None,
            is_active=True
        )
        
        superadmin = self.repository.create_superadmin(superadmin)
        
        return {
            "success": True,
            "message": "Superadmin creado correctamente",
            "superadmin_id": superadmin.id,
            "email": superadmin.email
        }