# app/modules/superadmin/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, extract
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from decimal import Decimal

from app.shared.database.models import (
    Company, User, CompanyInvoice, SubscriptionChange, 
    PlanTemplate, Location, Sale
)


class SuperadminRepository:
    """Repository para operaciones de superadmin"""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =====================================================
    # COMPANIES
    # =====================================================
    
    def get_all_companies(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        plan: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Company]:
        """Obtener todas las empresas con filtros"""
        query = self.db.query(Company)
        
        if status:
            if status == "active":
                query = query.filter(
                    Company.is_active == True,
                    Company.subscription_status == "active"
                )
            elif status == "suspended":
                query = query.filter(Company.subscription_status == "suspended")
            elif status == "trial":
                query = query.filter(Company.subscription_status == "trial")
        
        if plan:
            query = query.filter(Company.subscription_plan == plan)
        
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Company.name.ilike(search_pattern),
                    Company.subdomain.ilike(search_pattern),
                    Company.email.ilike(search_pattern)
                )
            )
        
        return query.order_by(Company.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_company_by_id(self, company_id: int) -> Optional[Company]:
        """Obtener empresa por ID"""
        return self.db.query(Company).filter(Company.id == company_id).first()
    
    def get_company_by_subdomain(self, subdomain: str) -> Optional[Company]:
        """Obtener empresa por subdominio"""
        return self.db.query(Company).filter(Company.subdomain == subdomain).first()
    
    def create_company(self, company: Company) -> Company:
        """Crear nueva empresa"""
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company
    
    def update_company(self, company: Company) -> Company:
        """Actualizar empresa"""
        self.db.commit()
        self.db.refresh(company)
        return company
    
    def delete_company(self, company_id: int) -> bool:
        """Eliminar empresa (soft delete)"""
        company = self.get_company_by_id(company_id)
        if company:
            company.is_active = False
            company.subscription_status = "cancelled"
            self.db.commit()
            return True
        return False
    
    # =====================================================
    # SUBSCRIPTION CHANGES
    # =====================================================
    
    def create_subscription_change(
        self,
        change: SubscriptionChange
    ) -> SubscriptionChange:
        """Registrar cambio de suscripción"""
        self.db.add(change)
        self.db.commit()
        self.db.refresh(change)
        return change
    
    def get_subscription_history(
        self,
        company_id: int
    ) -> List[SubscriptionChange]:
        """Obtener historial de cambios de suscripción"""
        return (
            self.db.query(SubscriptionChange)
            .filter(SubscriptionChange.company_id == company_id)
            .order_by(SubscriptionChange.created_at.desc())
            .all()
        )
    
    # =====================================================
    # INVOICES
    # =====================================================
    
    def create_invoice(self, invoice: CompanyInvoice) -> CompanyInvoice:
        """Crear nueva factura"""
        self.db.add(invoice)
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
    
    def get_company_invoices(
        self,
        company_id: int,
        status: Optional[str] = None
    ) -> List[CompanyInvoice]:
        """Obtener facturas de una empresa"""
        query = self.db.query(CompanyInvoice).filter(
            CompanyInvoice.company_id == company_id
        )
        
        if status:
            query = query.filter(CompanyInvoice.status == status)
        
        return query.order_by(CompanyInvoice.created_at.desc()).all()
    
    def get_all_invoices(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[CompanyInvoice]:
        """Obtener todas las facturas"""
        query = self.db.query(CompanyInvoice)
        
        if status:
            query = query.filter(CompanyInvoice.status == status)
        
        return query.order_by(CompanyInvoice.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_invoice_by_id(self, invoice_id: int) -> Optional[CompanyInvoice]:
        """Obtener factura por ID"""
        return self.db.query(CompanyInvoice).filter(CompanyInvoice.id == invoice_id).first()
    
    def mark_invoice_paid(
        self,
        invoice: CompanyInvoice,
        payment_method: str,
        payment_reference: Optional[str],
        paid_at: datetime
    ) -> CompanyInvoice:
        """Marcar factura como pagada"""
        invoice.status = "paid"
        invoice.payment_method = payment_method
        invoice.payment_reference = payment_reference
        invoice.paid_at = paid_at
        self.db.commit()
        self.db.refresh(invoice)
        return invoice
    
    # =====================================================
    # PLAN TEMPLATES
    # =====================================================
    
    def get_all_plan_templates(self, active_only: bool = True) -> List[PlanTemplate]:
        """Obtener todas las plantillas de planes"""
        query = self.db.query(PlanTemplate)
        
        if active_only:
            query = query.filter(PlanTemplate.is_active == True)
        
        return query.order_by(PlanTemplate.sort_order).all()
    
    def get_plan_template_by_code(self, plan_code: str) -> Optional[PlanTemplate]:
        """Obtener plantilla de plan por código"""
        return self.db.query(PlanTemplate).filter(
            PlanTemplate.plan_code == plan_code
        ).first()
    
    def create_plan_template(self, plan: PlanTemplate) -> PlanTemplate:
        """Crear plantilla de plan"""
        self.db.add(plan)
        self.db.commit()
        self.db.refresh(plan)
        return plan
    
    # =====================================================
    # METRICS & ANALYTICS
    # =====================================================
    
    def get_global_metrics(self) -> Dict[str, Any]:
        """Obtener métricas globales del sistema"""
        
        # Contar empresas por estado
        total_companies = self.db.query(func.count(Company.id)).scalar()
        active_companies = self.db.query(func.count(Company.id)).filter(
            Company.is_active == True,
            Company.subscription_status == "active"
        ).scalar()
        suspended_companies = self.db.query(func.count(Company.id)).filter(
            Company.subscription_status == "suspended"
        ).scalar()
        trial_companies = self.db.query(func.count(Company.id)).filter(
            Company.subscription_status == "trial"
        ).scalar()
        
        # Totales de recursos
        total_locations = self.db.query(func.sum(Company.current_locations_count)).scalar() or 0
        total_employees = self.db.query(func.sum(Company.current_employees_count)).scalar() or 0
        
        # Financiero
        monthly_recurring_revenue = self.db.query(
            func.sum(Company.current_locations_count * Company.price_per_location)
        ).filter(Company.is_active == True).scalar() or Decimal("0")
        
        pending_invoices = self.db.query(func.sum(CompanyInvoice.total_amount)).filter(
            CompanyInvoice.status == "pending"
        ).scalar() or Decimal("0")
        
        overdue_invoices = self.db.query(func.sum(CompanyInvoice.total_amount)).filter(
            CompanyInvoice.status == "overdue"
        ).scalar() or Decimal("0")
        
        # Alertas
        companies_near_limit = self.db.query(func.count(Company.id)).filter(
            or_(
                Company.current_locations_count >= Company.max_locations,
                Company.current_employees_count >= Company.max_employees
            )
        ).scalar()
        
        # Suscripciones por expirar (próximos 30 días)
        thirty_days_from_now = datetime.utcnow() + timedelta(days=30)
        subscriptions_expiring_soon = self.db.query(func.count(Company.id)).filter(
            and_(
                Company.subscription_ends_at.isnot(None),
                Company.subscription_ends_at <= thirty_days_from_now,
                Company.subscription_ends_at > datetime.utcnow()
            )
        ).scalar()
        
        overdue_payments = self.db.query(func.count(CompanyInvoice.id)).filter(
            CompanyInvoice.status == "overdue"
        ).scalar()
        
        # Crecimiento (este mes)
        first_day_of_month = date.today().replace(day=1)
        new_companies_this_month = self.db.query(func.count(Company.id)).filter(
            Company.created_at >= first_day_of_month
        ).scalar()
        
        cancelled_companies_this_month = self.db.query(func.count(Company.id)).filter(
            and_(
                Company.subscription_status == "cancelled",
                Company.updated_at >= first_day_of_month
            )
        ).scalar()
        
        return {
            "total_companies": total_companies,
            "active_companies": active_companies,
            "suspended_companies": suspended_companies,
            "trial_companies": trial_companies,
            "total_locations": total_locations,
            "total_employees": total_employees,
            "monthly_recurring_revenue": monthly_recurring_revenue,
            "pending_invoices_amount": pending_invoices,
            "overdue_invoices_amount": overdue_invoices,
            "companies_near_limit": companies_near_limit,
            "subscriptions_expiring_soon": subscriptions_expiring_soon,
            "overdue_payments": overdue_payments,
            "new_companies_this_month": new_companies_this_month,
            "cancelled_companies_this_month": cancelled_companies_this_month
        }
    
    def get_company_metrics(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Obtener métricas detalladas de una empresa"""
        company = self.get_company_by_id(company_id)
        if not company:
            return None
        
        # Contar usuarios activos
        active_users = self.db.query(func.count(User.id)).filter(
            User.company_id == company_id,
            User.is_active == True
        ).scalar()
        
        # Total pagado
        total_paid = self.db.query(func.sum(CompanyInvoice.total_amount)).filter(
            CompanyInvoice.company_id == company_id,
            CompanyInvoice.status == "paid"
        ).scalar() or Decimal("0")
        
        # Total pendiente
        total_pending = self.db.query(func.sum(CompanyInvoice.total_amount)).filter(
            CompanyInvoice.company_id == company_id,
            CompanyInvoice.status.in_(["pending", "overdue"])
        ).scalar() or Decimal("0")
        
        
        # Ventas del mes actual
        first_day_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        total_sales_this_month = self.db.query(func.sum(Sale.total_amount)).filter(
            Sale.company_id == company_id,
            Sale.sale_date >= first_day_of_month
        ).scalar() or Decimal("0")
        
        # Días hasta renovación
        days_until_renewal = None
        if company.next_billing_date:
            days_until_renewal = (company.next_billing_date - date.today()).days
        
        return {
            "company_id": company.id,
            "company_name": company.name,
            "locations_count": company.current_locations_count,
            "locations_limit": company.max_locations,
            "locations_usage_percent": round(
                (company.current_locations_count / company.max_locations * 100), 2
            ) if company.max_locations > 0 else 0,
            "employees_count": company.current_employees_count,
            "employees_limit": company.max_employees,
            "employees_usage_percent": round(
                (company.current_employees_count / company.max_employees * 100), 2
            ) if company.max_employees > 0 else 0,
            "current_plan": company.subscription_plan,
            "monthly_cost": company.monthly_cost,
            "total_paid": total_paid,
            "total_pending": total_pending,
            "active_users_count": active_users,
            "total_sales_this_month": total_sales_this_month,
            "subscription_status": company.subscription_status,
            "days_until_renewal": days_until_renewal
        }
    
    # =====================================================
    # SUPERADMIN USER y users Boss
    # =====================================================
    
    def superadmin_exists(self) -> bool:
        """Verificar si existe al menos un superadmin"""
        return self.db.query(User).filter(User.role == "superadmin").first() is not None
    
    def create_superadmin(self, user: User) -> User:
        """Crear usuario superadmin"""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_company_boss(self, company_id: int) -> Optional[User]:
        """Obtener el usuario Boss de una empresa (si existe)"""
        return (
            self.db.query(User)
            .filter(
                User.company_id == company_id,
                User.role == "boss",
                User.is_active == True
            )
            .first()
        )
    
    def boss_exists_for_company(self, company_id: int) -> bool:
        """Verificar si ya existe un Boss para la empresa"""
        return self.db.query(
            exists().where(
                and_(
                    User.company_id == company_id,
                    User.role == "boss",
                    User.is_active == True
                )
            )
        ).scalar()
    
    def email_exists(self, email: str) -> bool:
        """Verificar si el email ya está registrado"""
        return self.db.query(
            exists().where(User.email == email)
        ).scalar()
    
    def create_boss_user(self, boss: User) -> User:
        """Crear usuario Boss en la base de datos"""
        self.db.add(boss)
        self.db.commit()
        self.db.refresh(boss)
        return boss