# app/shared/database/models.py
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Text, 
    Numeric, ForeignKey, UniqueConstraint, CheckConstraint,
    func, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime

Base = declarative_base()

# =====================================================
# MIXIN PARA TIMESTAMPS
# =====================================================
class TimestampMixin:
    """Mixin que agrega campos created_at y updated_at"""
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# =====================================================
# MODELOS MULTITENANT
# =====================================================

class Company(Base, TimestampMixin):
    """Modelo de Empresa/Tenant"""
    __tablename__ = "companies"
    
    # Identificación
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=False, index=True)
    legal_name = Column(String(255))
    tax_id = Column(String(50))
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    
    # Suscripción
    subscription_plan = Column(String(20), nullable=False, default='basic')
    subscription_status = Column(String(20), nullable=False, default='active')
    subscription_started_at = Column(DateTime, server_default=func.current_timestamp())
    subscription_ends_at = Column(DateTime)
    
    # Límites del plan
    max_locations = Column(Integer, nullable=False)
    max_employees = Column(Integer, nullable=False)
    price_per_location = Column(Numeric(10, 2), nullable=False)
    
    # Contadores
    current_locations_count = Column(Integer, default=0)
    current_employees_count = Column(Integer, default=0)
    
    # Facturación
    billing_day = Column(Integer, default=1)
    last_billing_date = Column(Date)
    next_billing_date = Column(Date)
    
    # Configuración
    settings = Column(JSONB, default={})
    
    # Auditoría
    is_active = Column(Boolean, default=True)
    # ✅ CORREGIDO: use_alter=True para evitar referencia circular
    created_by_user_id = Column(Integer, ForeignKey("users.id", use_alter=True, name='fk_companies_created_by'))
    
    # Relationships
    users = relationship("User", back_populates="company", foreign_keys="User.company_id")
    locations = relationship("Location", back_populates="company")
    products = relationship("Product", back_populates="company")
    sales = relationship("Sale", back_populates="company")
    invoices = relationship("CompanyInvoice", back_populates="company")
    subscription_changes = relationship("SubscriptionChange", back_populates="company")
    mayoreo_items = relationship("Mayoreo", back_populates="company")
    
    @property
    def is_at_location_limit(self) -> bool:
        return self.current_locations_count >= self.max_locations
    
    @property
    def is_at_employee_limit(self) -> bool:
        return self.current_employees_count >= self.max_employees
    
    @property
    def monthly_cost(self) -> float:
        return float(self.current_locations_count * self.price_per_location)


class CompanyInvoice(Base):
    """Modelo de Factura"""
    __tablename__ = "company_invoices"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    
    invoice_number = Column(String(50), unique=True, nullable=False)
    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)
    
    locations_count = Column(Integer, nullable=False)
    price_per_location = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(12, 2), nullable=False)
    tax_percentage = Column(Numeric(5, 2), default=19.00)
    tax_amount = Column(Numeric(12, 2), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)
    
    status = Column(String(20), default='pending')
    due_date = Column(Date, nullable=False)
    paid_at = Column(DateTime)
    payment_method = Column(String(50))
    payment_reference = Column(String(100))
    
    details = Column(JSONB)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    company = relationship("Company", back_populates="invoices")


class SubscriptionChange(Base):
    """Modelo de Cambio de Suscripción"""
    __tablename__ = "subscription_changes"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    
    old_plan = Column(String(20))
    new_plan = Column(String(20), nullable=False)
    old_max_locations = Column(Integer)
    new_max_locations = Column(Integer, nullable=False)
    old_max_employees = Column(Integer)
    new_max_employees = Column(Integer, nullable=False)
    old_price_per_location = Column(Numeric(10, 2))
    new_price_per_location = Column(Numeric(10, 2), nullable=False)
    
    reason = Column(Text)
    effective_date = Column(Date, nullable=False)
    changed_by_user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    company = relationship("Company", back_populates="subscription_changes")
    changed_by = relationship("User", foreign_keys=[changed_by_user_id])


class PlanTemplate(Base):
    """Modelo de Plantilla de Plan"""
    __tablename__ = "plan_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    plan_code = Column(String(20), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text)
    
    max_locations = Column(Integer, nullable=False)
    max_employees = Column(Integer, nullable=False)
    price_per_location = Column(Numeric(10, 2), nullable=False)
    
    features = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())


# =====================================================
# LOCALIZACIONES
# =====================================================

class Location(Base):
    """Modelo de Ubicación (Local o Bodega)"""
    __tablename__ = "locations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    address = Column(Text)
    phone = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    company = relationship("Company", back_populates="locations")
    users = relationship("User", back_populates="location")
    expenses = relationship("Expense", back_populates="location")
    sales = relationship("Sale", back_populates="location")
    cost_configurations = relationship("CostConfiguration", back_populates="location")
    # NO agregar 'products' porque Product usa location_name (String) no location_id


# =====================================================
# USUARIOS
# =====================================================

class User(Base):
    """Modelo de Usuario"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    # ✅ NULLABLE para superadmin
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
    email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)
    # ✅ CORREGIDO: Default 'vendedor' según DDL
    role = Column(String(50), default='vendedor', nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    location = relationship("Location", back_populates="users")
    sales = relationship("Sale", back_populates="seller", foreign_keys="Sale.seller_id")
    expenses = relationship("Expense", back_populates="user")
    location_assignments = relationship("UserLocationAssignment", back_populates="user")
    
    created_cost_configurations = relationship("CostConfiguration", foreign_keys="CostConfiguration.created_by_user_id", back_populates="created_by")
    paid_cost_payments = relationship("CostPayment", foreign_keys="CostPayment.paid_by_user_id", back_populates="paid_by")
    created_cost_exceptions = relationship("CostPaymentException", foreign_keys="CostPaymentException.created_by_user_id", back_populates="created_by")
    deleted_cost_archives = relationship("CostDeletionArchive", foreign_keys="CostDeletionArchive.deleted_by_user_id", back_populates="deleted_by")
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# =====================================================
# PRODUCTOS
# =====================================================

class Product(Base, TimestampMixin):
    """Modelo de Producto"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    reference_code = Column(String(255), nullable=False, index=True)
    description = Column(String(255), nullable=False)
    brand = Column(String(255))
    model = Column(String(255))
    color_info = Column(String(255))
    video_url = Column(String(255))
    image_url = Column(String(255))
    total_quantity = Column(Integer, default=0)
    location_name = Column(String(255), nullable=False, index=True)
    unit_price = Column(Numeric(10, 2), default=0.0)
    box_price = Column(Numeric(10, 2), default=0.0)
    # ✅ CORREGIDO: Integer según DDL
    is_active = Column(Integer, default=1)
    
    __table_args__ = (
        UniqueConstraint('reference_code', 'location_name', name='products_unique_per_location'),
    )
    
    # Relationships
    company = relationship("Company", back_populates="products")
    sizes = relationship("ProductSize", back_populates="product", cascade="all, delete-orphan")
    mappings = relationship("ProductMapping", back_populates="product", cascade="all, delete-orphan")
    inventory_changes = relationship("InventoryChange", back_populates="product")


class ProductSize(Base, TimestampMixin):
    """Modelo de Tallas de Producto"""
    __tablename__ = "product_sizes"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    size = Column(String(255), nullable=False)
    quantity = Column(Integer, default=0)
    quantity_exhibition = Column(Integer, default=0)
    location_name = Column(String(255), nullable=False)
    
    # Relationships
    product = relationship("Product", back_populates="sizes")


class ProductMapping(Base):
    """Modelo de Mapeo de Productos con IA"""
    __tablename__ = "product_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    api_reference_code = Column(String(255), nullable=False)
    model_name = Column(String(255))
    similarity_score = Column(Numeric(10, 2), default=1.0)
    original_db_id = Column(Integer)
    image_path = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Relationships
    product = relationship("Product", back_populates="mappings")


class InventoryChange(Base):
    """Modelo de Cambios de Inventario"""
    __tablename__ = "inventory_changes"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    change_type = Column(String(255), nullable=False)
    size = Column(String(255))
    quantity_before = Column(Integer)
    quantity_after = Column(Integer)
    reference_id = Column(Integer)
    user_id = Column(Integer)
    notes = Column(String(255))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    
    # Relationships
    product = relationship("Product", back_populates="inventory_changes")


# =====================================================
# VENTAS
# =====================================================

class Sale(Base):
    """Modelo de Venta"""
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    receipt_image = Column(Text)
    sale_date = Column(DateTime, server_default=func.current_timestamp())
    status = Column(String(50), default='completed')
    notes = Column(Text)
    requires_confirmation = Column(Boolean, default=False)
    confirmed = Column(Boolean, default=True)
    confirmed_at = Column(DateTime)
    
    # Relationships
    company = relationship("Company", back_populates="sales")
    seller = relationship("User", back_populates="sales", foreign_keys=[seller_id])
    location = relationship("Location", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("SalePayment", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    """Modelo de Item de Venta"""
    __tablename__ = "sale_items"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    sneaker_reference_code = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    color = Column(String(255))
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    sale = relationship("Sale", back_populates="items")


class SalePayment(Base):
    """Modelo de Pago de Venta"""
    __tablename__ = "sale_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    payment_type = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    reference = Column(String(255))
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    sale = relationship("Sale", back_populates="payments")


# =====================================================
# GASTOS
# =====================================================

class Expense(Base):
    """Modelo de Gasto"""
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    concept = Column(String(255), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    receipt_image = Column(Text)
    expense_date = Column(DateTime, server_default=func.current_timestamp())
    notes = Column(Text)
    
    # Relationships
    user = relationship("User", back_populates="expenses")
    location = relationship("Location", back_populates="expenses")


# =====================================================
# TRANSFERENCIAS
# =====================================================

class TransferRequest(Base):
    """Modelo de Solicitud de Transferencia"""
    __tablename__ = "transfer_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    destination_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    sneaker_reference_code = Column(String(255), nullable=False)
    brand = Column(String(255), nullable=False)
    model = Column(String(255), nullable=False)
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    purpose = Column(String(50), nullable=False)
    pickup_type = Column(String(50), nullable=False)
    destination_type = Column(String(50), default='bodega')
    courier_id = Column(Integer, ForeignKey("users.id"))
    warehouse_keeper_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50), default='pending')
    requested_at = Column(DateTime, server_default=func.current_timestamp())
    accepted_at = Column(DateTime)
    picked_up_at = Column(DateTime)
    delivered_at = Column(DateTime)
    notes = Column(Text)
    confirmed_reception_at = Column(DateTime)
    received_quantity = Column(Integer)
    reception_notes = Column(Text)
    courier_accepted_at = Column(DateTime)
    courier_notes = Column(Text)
    estimated_pickup_time = Column(Integer)
    pickup_notes = Column(Text)
    request_type = Column(String(20), default='transfer')
    original_transfer_id = Column(Integer, ForeignKey('transfer_requests.id'))
    
    # Relationships
    requester = relationship("User", foreign_keys=[requester_id])
    courier = relationship("User", foreign_keys=[courier_id])
    warehouse_keeper = relationship("User", foreign_keys=[warehouse_keeper_id])
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])


# =====================================================
# DESCUENTOS Y RESERVAS
# =====================================================

class DiscountRequest(Base):
    """Modelo de Solicitud de Descuento"""
    __tablename__ = "discount_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(50), default='pending')
    administrator_id = Column(Integer, ForeignKey("users.id"))
    requested_at = Column(DateTime, server_default=func.current_timestamp())
    reviewed_at = Column(DateTime)
    admin_comments = Column(Text)
    
    # Relationships
    seller = relationship("User", foreign_keys=[seller_id])
    administrator = relationship("User", foreign_keys=[administrator_id])


class ProductReservation(Base):
    """Modelo de Reserva de Producto"""
    __tablename__ = "product_reservations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    sneaker_reference_code = Column(String(255), nullable=False)
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    purpose = Column(String(50), nullable=False)
    status = Column(String(50), default='active')
    reserved_at = Column(DateTime, server_default=func.current_timestamp())
    expires_at = Column(DateTime, nullable=False)
    released_at = Column(DateTime)
    
    # Relationships
    user = relationship("User")
    location = relationship("Location")


# =====================================================
# ASIGNACIONES
# =====================================================

class UserLocationAssignment(Base):
    """Modelo de Asignación Usuario-Ubicación"""
    __tablename__ = "user_location_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    role_at_location = Column(String(50), default='bodeguero', nullable=False)
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, server_default=func.current_timestamp())
    
    __table_args__ = (
        UniqueConstraint('user_id', 'location_id', name='user_location_assignments_user_id_location_id_key'),
    )
    
    # Relationships
    user = relationship("User", back_populates="location_assignments")
    location = relationship("Location")


class AdminLocationAssignment(Base):
    """Modelo de Asignación Administrador-Ubicación"""
    __tablename__ = "admin_location_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, server_default=func.current_timestamp())
    assigned_by_user_id = Column(Integer, ForeignKey("users.id"))
    notes = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('admin_id', 'location_id', name='admin_location_unique'),
    )
    
    # Relationships
    admin = relationship("User", foreign_keys=[admin_id])
    location = relationship("Location")
    assigned_by = relationship("User", foreign_keys=[assigned_by_user_id])


# =====================================================
# DEVOLUCIONES
# =====================================================

class ReturnRequest(Base):
    """Modelo de Solicitud de Devolución"""
    __tablename__ = "return_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    original_transfer_id = Column(Integer, ForeignKey("transfer_requests.id"), nullable=False)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    destination_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    sneaker_reference_code = Column(String(255), nullable=False)
    size = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False)
    courier_id = Column(Integer, ForeignKey("users.id"))
    warehouse_keeper_id = Column(Integer, ForeignKey("users.id"))
    status = Column(String(50), default='pending')
    requested_at = Column(DateTime, server_default=func.current_timestamp())
    completed_at = Column(DateTime)
    notes = Column(Text)
    
    # Relationships
    original_transfer = relationship("TransferRequest", foreign_keys=[original_transfer_id])
    requester = relationship("User", foreign_keys=[requester_id])
    courier = relationship("User", foreign_keys=[courier_id])
    warehouse_keeper = relationship("User", foreign_keys=[warehouse_keeper_id])
    source_location = relationship("Location", foreign_keys=[source_location_id])
    destination_location = relationship("Location", foreign_keys=[destination_location_id])


class ReturnNotification(Base):
    """Modelo de Notificación de Devolución"""
    __tablename__ = "return_notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    transfer_request_id = Column(Integer, ForeignKey("transfer_requests.id"), nullable=False)
    returned_to_location = Column(String(255), nullable=False)
    returned_at = Column(DateTime, server_default=func.current_timestamp())
    notes = Column(Text)
    read_by_requester = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    transfer_request = relationship("TransferRequest")


class TransportIncident(Base):
    """Modelo de Incidente de Transporte"""
    __tablename__ = "transport_incidents"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    transfer_request_id = Column(Integer, ForeignKey("transfer_requests.id"), nullable=False)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    incident_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    reported_at = Column(DateTime, server_default=func.current_timestamp())
    resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    
    # Relationships
    transfer_request = relationship("TransferRequest")
    courier = relationship("User", foreign_keys=[courier_id])


# =====================================================
# COSTOS
# =====================================================

class CostConfiguration(Base):
    """Modelo de Configuración de Costos"""
    __tablename__ = "cost_configurations"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    cost_type = Column(String(50), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    frequency = Column(String(20), nullable=False)
    description = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    location = relationship("Location", back_populates="cost_configurations")
    created_by = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_cost_configurations")
    payments = relationship("CostPayment", back_populates="cost_configuration", cascade="all, delete-orphan")
    exceptions = relationship("CostPaymentException", back_populates="cost_configuration", cascade="all, delete-orphan")


class CostPayment(Base):
    """Modelo de Pago de Costo"""
    __tablename__ = "cost_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    cost_configuration_id = Column(Integer, ForeignKey("cost_configurations.id"), nullable=False)
    due_date = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    payment_method = Column(String(50), nullable=False)
    payment_reference = Column(String(255))
    notes = Column(Text)
    paid_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    cost_configuration = relationship("CostConfiguration", back_populates="payments")
    paid_by = relationship("User", foreign_keys=[paid_by_user_id], back_populates="paid_cost_payments")


class CostPaymentException(Base):
    """Modelo de Excepción de Pago de Costo"""
    __tablename__ = "cost_payment_exceptions"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    cost_configuration_id = Column(Integer, ForeignKey("cost_configurations.id"), nullable=False)
    exception_date = Column(Date, nullable=False)
    exception_type = Column(String(20), nullable=False)
    original_amount = Column(Numeric(10, 2))
    new_amount = Column(Numeric(10, 2))
    new_due_date = Column(Date)
    reason = Column(Text)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    cost_configuration = relationship("CostConfiguration", back_populates="exceptions")
    created_by = relationship("User", foreign_keys=[created_by_user_id], back_populates="created_cost_exceptions")


class CostDeletionArchive(Base):
    """Modelo de Archivo de Eliminación de Costo"""
    __tablename__ = "cost_deletion_archives"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    original_cost_id = Column(Integer, nullable=False)
    configuration_data = Column(JSONB, nullable=False)
    paid_payments_data = Column(JSONB)
    exceptions_data = Column(JSONB)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    deletion_date = Column(DateTime, server_default=func.current_timestamp())
    deletion_reason = Column(String(100))
    
    # Relationships
    deleted_by = relationship("User", foreign_keys=[deleted_by_user_id], back_populates="deleted_cost_archives")


# =====================================================
# VIDEO PROCESSING
# =====================================================

class VideoProcessingJob(Base):
    """Modelo de Job de Procesamiento de Video"""
    __tablename__ = "video_processing_jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    video_file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    file_size_bytes = Column(Integer)
    warehouse_location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    estimated_quantity = Column(Integer, nullable=False)
    product_brand = Column(String(255))
    product_model = Column(String(255))
    expected_sizes = Column(Text)
    notes = Column(Text)
    processing_status = Column(String(50), default="processing")
    ai_results_json = Column(Text)
    confidence_score = Column(Numeric(5, 4), default=0.0)
    detected_brand = Column(String(255))
    detected_model = Column(String(255))
    detected_colors = Column(Text)
    detected_sizes = Column(Text)
    frames_extracted = Column(Integer)
    processing_time_seconds = Column(Integer)
    microservice_job_id = Column(String(100))
    processed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    processing_started_at = Column(DateTime)
    processing_completed_at = Column(DateTime)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    created_product_id = Column(Integer, ForeignKey("products.id"))
    created_inventory_change_id = Column(Integer, ForeignKey("inventory_changes.id"))
    
    # Relationships
    warehouse = relationship("Location")
    processed_by = relationship("User")
    created_product = relationship("Product")
    created_inventory_change = relationship("InventoryChange")


# =====================================================
# MAYOREO - ✅ TABLAS FALTANTES AGREGADAS
# =====================================================

class Mayoreo(Base):
    """Modelo de Producto Mayoreo"""
    __tablename__ = "mayoreo"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    modelo = Column(String(255), nullable=False)
    foto = Column(Text)
    tallas = Column(String(255))
    cantidad_cajas_disponibles = Column(Integer, default=0, nullable=False)
    pares_por_caja = Column(Integer, nullable=False)
    precio = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    updated_at = Column(DateTime, server_default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    company = relationship("Company", back_populates="mayoreo_items")
    user = relationship("User")
    ventas = relationship("VentaMayoreo", back_populates="mayoreo")


class VentaMayoreo(Base):
    """Modelo de Venta de Mayoreo"""
    __tablename__ = "venta_mayoreo"
    
    id = Column(Integer, primary_key=True, index=True)
    mayoreo_id = Column(Integer, ForeignKey("mayoreo.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    cantidad_cajas_vendidas = Column(Integer, nullable=False)
    precio_unitario_venta = Column(Numeric(10, 2), nullable=False)
    total_venta = Column(Numeric(12, 2), nullable=False)
    fecha_venta = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    notas = Column(Text)
    created_at = Column(DateTime, server_default=func.current_timestamp())
    
    # Relationships
    mayoreo = relationship("Mayoreo", back_populates="ventas")
    user = relationship("User")