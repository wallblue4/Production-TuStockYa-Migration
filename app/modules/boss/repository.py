# app/modules/boss/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, desc
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.shared.database.models import (
    Location, User, Product, ProductSize, Sale, SaleItem,
    SalePayment, CostConfiguration, CostPayment, InventoryChange,
    TransferRequest, Company
)

class BossRepository:
    """Repositorio para consultas ejecutivas del Boss"""
    
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
    
    # ==================== CREACIÓN DE UBICACIONES ====================
    
    def create_location(self, location_data: Dict[str, Any], boss_id: int) -> Location:
        """BS008 & BS009: Crear nueva ubicación (local o bodega)"""
        
        location = Location(
            company_id=self.company_id,
            name=location_data['name'],
            type=location_data['type'],
            address=location_data.get('address'),
            phone=location_data.get('phone'),
            is_active=True,
            created_at=datetime.now()
        )
        
        self.db.add(location)
        self.db.flush()
        
        return location
    
    def get_all_company_locations(self, include_inactive: bool = False) -> List[Location]:
        """Obtener todas las ubicaciones de la empresa"""
        
        query = self.db.query(Location).filter(
            Location.company_id == self.company_id
        )
        
        if not include_inactive:
            query = query.filter(Location.is_active == True)
        
        return query.order_by(Location.type, Location.name).all()
    
    # ==================== DASHBOARD EJECUTIVO ====================
    
    def get_company_kpis(self, target_date: date) -> Dict[str, Any]:
        """BS001: Obtener KPIs principales de la empresa"""
        
        # Período actual (hoy)
        today_start = datetime.combine(target_date, datetime.min.time())
        today_end = datetime.combine(target_date, datetime.max.time())
        
        # Período anterior (ayer)
        yesterday = target_date - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        yesterday_end = datetime.combine(yesterday, datetime.max.time())
        
        # Mes actual
        month_start = target_date.replace(day=1)
        
        # Mes anterior
        if month_start.month == 1:
            prev_month_start = month_start.replace(year=month_start.year - 1, month=12)
        else:
            prev_month_start = month_start.replace(month=month_start.month - 1)
        
        prev_month_end = month_start - timedelta(days=1)
        
        # Ventas de hoy
        today_sales = self.db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
            Sale.company_id == self.company_id,
            Sale.sale_date >= today_start,
            Sale.sale_date <= today_end,
            Sale.status == 'completed'
        ).scalar() or Decimal('0')
        
        # Ventas de ayer
        yesterday_sales = self.db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
            Sale.company_id == self.company_id,
            Sale.sale_date >= yesterday_start,
            Sale.sale_date <= yesterday_end,
            Sale.status == 'completed'
        ).scalar() or Decimal('0')
        
        # Ventas del mes actual
        month_sales = self.db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
            Sale.company_id == self.company_id,
            Sale.sale_date >= month_start,
            Sale.status == 'completed'
        ).scalar() or Decimal('0')
        
        # Ventas del mes anterior
        prev_month_sales = self.db.query(func.coalesce(func.sum(Sale.total_amount), 0)).filter(
            Sale.company_id == self.company_id,
            Sale.sale_date >= prev_month_start,
            Sale.sale_date <= prev_month_end,
            Sale.status == 'completed'
        ).scalar() or Decimal('0')
        
        # Transacciones de hoy
        today_transactions = self.db.query(func.count(Sale.id)).filter(
            Sale.company_id == self.company_id,
            Sale.sale_date >= today_start,
            Sale.sale_date <= today_end,
            Sale.status == 'completed'
        ).scalar() or 0
        
        # Valor total de inventario
        inventory_value = self.db.query(
            func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0)
        ).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            Product.is_active == 1
        ).scalar() or Decimal('0')
        
        # Usuarios activos
        active_users = self.db.query(func.count(User.id)).filter(
            User.company_id == self.company_id,
            User.is_active == True
        ).scalar() or 0
        
        # Ubicaciones activas
        active_locations = self.db.query(func.count(Location.id)).filter(
            Location.company_id == self.company_id,
            Location.is_active == True
        ).scalar() or 0
        
        return {
            'today_sales': today_sales,
            'yesterday_sales': yesterday_sales,
            'month_sales': month_sales,
            'prev_month_sales': prev_month_sales,
            'today_transactions': today_transactions,
            'inventory_value': inventory_value,
            'active_users': active_users,
            'active_locations': active_locations
        }
    
    def get_locations_performance(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Obtener performance de todas las ubicaciones"""
        
        locations = self.get_all_company_locations()
        performance = []
        
        for location in locations:
            # Ventas del período
            sales_data = self.db.query(
                func.coalesce(func.sum(Sale.total_amount), 0).label('total_sales'),
                func.count(Sale.id).label('transactions')
            ).filter(
                Sale.company_id == self.company_id,
                Sale.location_id == location.id,
                func.date(Sale.sale_date) >= start_date,
                func.date(Sale.sale_date) <= end_date,
                Sale.status == 'completed'
            ).first()
            
            # Inventario
            inventory_value = self.db.query(
                func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0)
            ).join(Product).filter(
                Product.company_id == self.company_id,
                ProductSize.company_id == self.company_id,
                ProductSize.location_name == location.name,
                Product.is_active == 1
            ).scalar() or Decimal('0')
            
            # Usuarios activos
            active_users_count = self.db.query(func.count(User.id)).filter(
                User.company_id == self.company_id,
                User.location_id == location.id,
                User.is_active == True
            ).scalar() or 0
            
            # Transferencias pendientes
            pending_transfers = self.db.query(func.count(TransferRequest.id)).filter(
                TransferRequest.company_id == self.company_id,
                or_(
                    TransferRequest.source_location_id == location.id,
                    TransferRequest.destination_location_id == location.id
                ),
                TransferRequest.status.in_(['pending', 'accepted', 'in_transit'])
            ).scalar() or 0
            
            # Calcular efficiency score (basado en ventas y transacciones)
            efficiency = 0.0
            if sales_data.transactions > 0:
                avg_ticket = float(sales_data.total_sales / sales_data.transactions)
                # Score simple: normalizar entre 0-100
                efficiency = min(100.0, (avg_ticket / 100000) * 100)  # Ajustar según tu negocio
            
            performance.append({
                'location_id': location.id,
                'location_name': location.name,
                'location_type': location.type,
                'daily_sales': sales_data.total_sales / ((end_date - start_date).days + 1),
                'monthly_sales': sales_data.total_sales,
                'inventory_value': inventory_value,
                'active_users': active_users_count,
                'pending_transfers': pending_transfers,
                'efficiency_score': round(efficiency, 2)
            })
        
        return performance
    
    def get_company_alerts(self) -> List[Dict[str, Any]]:
        """Obtener alertas críticas de la empresa"""
        
        alerts = []
        
        # Alertas de stock bajo
        low_stock = self.db.query(
            Product.reference_code,
            Product.model,
            ProductSize.location_name,
            ProductSize.quantity
        ).join(ProductSize).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            ProductSize.quantity < 5,
            ProductSize.quantity > 0,
            Product.is_active == 1
        ).limit(10).all()
        
        for item in low_stock:
            alerts.append({
                'type': 'low_stock',
                'severity': 'warning',
                'message': f'Stock bajo: {item.model} en {item.location_name} ({item.quantity} unidades)',
                'data': {
                    'reference': item.reference_code,
                    'location': item.location_name,
                    'quantity': item.quantity
                }
            })
        
        # Alertas de productos agotados
        out_of_stock_count = self.db.query(func.count(ProductSize.id)).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            ProductSize.quantity == 0,
            Product.is_active == 1
        ).scalar() or 0
        
        if out_of_stock_count > 0:
            alerts.append({
                'type': 'out_of_stock',
                'severity': 'critical',
                'message': f'{out_of_stock_count} productos agotados en inventario',
                'data': {'count': out_of_stock_count}
            })
        
        # Transferencias pendientes hace más de 24 horas
        old_transfers = self.db.query(func.count(TransferRequest.id)).filter(
            TransferRequest.company_id == self.company_id,
            TransferRequest.status == 'pending',
            TransferRequest.requested_at < (datetime.now() - timedelta(hours=24))
        ).scalar() or 0
        
        if old_transfers > 0:
            alerts.append({
                'type': 'delayed_transfers',
                'severity': 'warning',
                'message': f'{old_transfers} transferencias pendientes hace más de 24 horas',
                'data': {'count': old_transfers}
            })
        
        return alerts
    
    # ==================== REPORTES DE VENTAS ====================
    
    def get_consolidated_sales_report(
        self, 
        start_date: date, 
        end_date: date,
        location_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """BS002: Generar reporte consolidado de ventas"""
        
        # Filtro base
        query_filter = and_(
            Sale.company_id == self.company_id,
            func.date(Sale.sale_date) >= start_date,
            func.date(Sale.sale_date) <= end_date,
            Sale.status == 'completed'
        )
        
        if location_ids:
            query_filter = and_(query_filter, Sale.location_id.in_(location_ids))
        
        # Totales generales
        totals = self.db.query(
            func.coalesce(func.sum(Sale.total_amount), 0).label('total_sales'),
            func.count(Sale.id).label('total_transactions')
        ).filter(query_filter).first()
        
        total_sales = totals.total_sales or Decimal('0')
        total_transactions = totals.total_transactions or 0
        avg_ticket = total_sales / total_transactions if total_transactions > 0 else Decimal('0')
        
        # Ventas por ubicación
        sales_by_location = self.db.query(
            Location.id,
            Location.name,
            Location.type,
            func.coalesce(func.sum(Sale.total_amount), 0).label('total'),
            func.count(Sale.id).label('transactions')
        ).join(Sale).filter(query_filter).group_by(
            Location.id, Location.name, Location.type
        ).order_by(desc('total')).all()
        
        # Top vendedores
        top_sellers = self.db.query(
            User.id,
            User.first_name,
            User.last_name,
            func.coalesce(func.sum(Sale.total_amount), 0).label('total_sales'),
            func.count(Sale.id).label('transactions')
        ).join(Sale, Sale.seller_id == User.id).filter(
            query_filter
        ).group_by(
            User.id, User.first_name, User.last_name
        ).order_by(desc('total_sales')).limit(10).all()
        
        # Top productos (por unidades vendidas)
        top_products = self.db.query(
            SaleItem.brand,
            SaleItem.model,
            func.sum(SaleItem.quantity).label('units_sold'),
            func.coalesce(func.sum(SaleItem.subtotal), 0).label('total_revenue')
        ).join(Sale).filter(
            Sale.company_id == self.company_id,
            func.date(Sale.sale_date) >= start_date,
            func.date(Sale.sale_date) <= end_date,
            Sale.status == 'completed'
        ).group_by(
            SaleItem.brand, SaleItem.model
        ).order_by(desc('units_sold')).limit(10).all()
        
        # Métodos de pago
        payment_methods = self.db.query(
            SalePayment.payment_type,
            func.coalesce(func.sum(SalePayment.amount), 0).label('total')
        ).join(Sale).filter(
            Sale.company_id == self.company_id,
            func.date(Sale.sale_date) >= start_date,
            func.date(Sale.sale_date) <= end_date,
            Sale.status == 'completed'
        ).group_by(SalePayment.payment_type).all()
        
        return {
            'total_sales': total_sales,
            'total_transactions': total_transactions,
            'average_ticket': avg_ticket,
            'sales_by_location': [
                {
                    'location_id': loc.id,
                    'location_name': loc.name,
                    'location_type': loc.type,
                    'total_sales': loc.total,
                    'transactions': loc.transactions,
                    'avg_ticket': loc.total / loc.transactions if loc.transactions > 0 else Decimal('0')
                }
                for loc in sales_by_location
            ],
            'top_sellers': [
                {
                    'seller_id': seller.id,
                    'seller_name': f"{seller.first_name} {seller.last_name}",
                    'total_sales': seller.total_sales,
                    'transactions': seller.transactions,
                    'avg_ticket': seller.total_sales / seller.transactions if seller.transactions > 0 else Decimal('0')
                }
                for seller in top_sellers
            ],
            'top_products': [
                {
                    'brand': prod.brand,
                    'model': prod.model,
                    'units_sold': prod.units_sold,
                    'total_revenue': prod.total_revenue
                }
                for prod in top_products
            ],
            'payment_methods': {
                method.payment_type: method.total
                for method in payment_methods
            }
        }
    
    # ==================== INVENTARIO CONSOLIDADO ====================
    
    def get_consolidated_inventory(self) -> Dict[str, Any]:
        """BS003: Obtener inventario total consolidado"""
        
        # Totales generales
        totals = self.db.query(
            func.count(func.distinct(Product.id)).label('total_products'),
            func.coalesce(func.sum(ProductSize.quantity), 0).label('total_units'),
            func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0).label('total_value')
        ).join(ProductSize).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            Product.is_active == 1
        ).first()
        
        # Por marca (brand)
        by_brand = self.db.query(
            Product.brand,
            func.coalesce(func.sum(ProductSize.quantity), 0).label('total_units'),
            func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0).label('total_value'),
            func.count(func.distinct(ProductSize.location_name)).label('locations_count')
        ).join(ProductSize).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            Product.is_active == 1,
            Product.brand.isnot(None)
        ).group_by(Product.brand).order_by(desc('total_value')).all()
        
        total_value_all = totals.total_value if totals.total_value else Decimal('1')
        
        by_brand_list = [
            {
                'category_name': brand.brand or 'Sin marca',
                'total_units': brand.total_units,
                'total_value': brand.total_value,
                'locations_count': brand.locations_count,
                'percentage_of_total': float((brand.total_value / total_value_all) * 100) if total_value_all > 0 else 0.0
            }
            for brand in by_brand
        ]
        
        # Por ubicación
        by_location = self.db.query(
            ProductSize.location_name,
            func.count(func.distinct(Product.id)).label('total_products'),
            func.coalesce(func.sum(ProductSize.quantity), 0).label('total_units'),
            func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0).label('total_value')
        ).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            Product.is_active == 1
        ).group_by(ProductSize.location_name).all()
        
        by_location_list = []
        for loc_inv in by_location:
            # Obtener location_id
            location = self.db.query(Location).filter(
                Location.company_id == self.company_id,
                Location.name == loc_inv.location_name
            ).first()
            
            # Stock bajo en esta ubicación
            low_stock = self.db.query(func.count(ProductSize.id)).join(Product).filter(
                Product.company_id == self.company_id,
                ProductSize.company_id == self.company_id,
                ProductSize.location_name == loc_inv.location_name,
                ProductSize.quantity < 5,
                ProductSize.quantity > 0,
                Product.is_active == 1
            ).scalar() or 0
            
            by_location_list.append({
                'location_id': location.id if location else 0,
                'location_name': loc_inv.location_name,
                'location_type': location.type if location else 'unknown',
                'total_products': loc_inv.total_products,
                'total_units': loc_inv.total_units,
                'total_value': loc_inv.total_value,
                'low_stock_items': low_stock
            })
        
        # Alertas
        low_stock_count = self.db.query(func.count(ProductSize.id)).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            ProductSize.quantity < 5,
            ProductSize.quantity > 0,
            Product.is_active == 1
        ).scalar() or 0
        
        out_of_stock_count = self.db.query(func.count(ProductSize.id)).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            ProductSize.quantity == 0,
            Product.is_active == 1
        ).scalar() or 0
        
        # Productos con sobrestock (más de 100 unidades)
        overstocked_count = self.db.query(func.count(ProductSize.id)).join(Product).filter(
            Product.company_id == self.company_id,
            ProductSize.company_id == self.company_id,
            ProductSize.quantity > 100,
            Product.is_active == 1
        ).scalar() or 0
        
        return {
            'total_products': totals.total_products or 0,
            'total_units': totals.total_units or 0,
            'total_value': totals.total_value or Decimal('0'),
            'by_brand': by_brand_list,
            'by_location': by_location_list,
            'low_stock_alerts': low_stock_count,
            'out_of_stock_alerts': out_of_stock_count,
            'overstocked_alerts': overstocked_count
        }
    
    # ==================== ANÁLISIS FINANCIERO ====================
    
    def get_financial_analysis(
        self, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, Any]:
        """BS004: Obtener análisis financiero con costos y márgenes"""
        
        # Ingresos totales
        total_revenue = self.db.query(
            func.coalesce(func.sum(Sale.total_amount), 0)
        ).filter(
            Sale.company_id == self.company_id,
            func.date(Sale.sale_date) >= start_date,
            func.date(Sale.sale_date) <= end_date,
            Sale.status == 'completed'
        ).scalar() or Decimal('0')
        
        # Costos totales (del período)
        # Calcular cuántos días del período para costos recurrentes
        days_in_period = (end_date - start_date).days + 1
        
        # Costos fijos y variables configurados
        cost_configs = self.db.query(CostConfiguration).filter(
            CostConfiguration.company_id == self.company_id,
            CostConfiguration.is_active == True
        ).all()
        
        total_costs = Decimal('0')
        costs_by_type = {}
        
        for cost_config in cost_configs:
            # Calcular costo para el período según frecuencia
            cost_for_period = self._calculate_cost_for_period(
                cost_config, start_date, end_date, days_in_period
            )
            
            total_costs += cost_for_period
            
            cost_type = cost_config.cost_type
            if cost_type not in costs_by_type:
                costs_by_type[cost_type] = Decimal('0')
            costs_by_type[cost_type] += cost_for_period
        
        # Calcular utilidad y margen
        net_profit = total_revenue - total_costs
        margin_percentage = float((net_profit / total_revenue * 100)) if total_revenue > 0 else 0.0
        
        # Análisis por ubicación
        locations_financials = []
        locations = self.get_all_company_locations()
        
        for location in locations:
            # Ingresos de esta ubicación
            location_revenue = self.db.query(
                func.coalesce(func.sum(Sale.total_amount), 0)
            ).filter(
                Sale.company_id == self.company_id,
                Sale.location_id == location.id,
                func.date(Sale.sale_date) >= start_date,
                func.date(Sale.sale_date) <= end_date,
                Sale.status == 'completed'
            ).scalar() or Decimal('0')
            
            # Costos de esta ubicación
            location_costs = Decimal('0')
            location_cost_breakdown = {}
            
            location_cost_configs = self.db.query(CostConfiguration).filter(
                CostConfiguration.company_id == self.company_id,
                CostConfiguration.location_id == location.id,
                CostConfiguration.is_active == True
            ).all()
            
            for cost_config in location_cost_configs:
                cost_for_period = self._calculate_cost_for_period(
                    cost_config, start_date, end_date, days_in_period
                )
                location_costs += cost_for_period
                
                cost_type = cost_config.cost_type
                if cost_type not in location_cost_breakdown:
                    location_cost_breakdown[cost_type] = Decimal('0')
                location_cost_breakdown[cost_type] += cost_for_period
            
            # Calcular utilidad y margen
            location_profit = location_revenue - location_costs
            location_margin = float((location_profit / location_revenue * 100)) if location_revenue > 0 else 0.0
            
            locations_financials.append({
                'location_id': location.id,
                'location_name': location.name,
                'location_type': location.type,
                'total_sales': location_revenue,
                'operational_costs': location_costs,
                'cost_breakdown': location_cost_breakdown,
                'gross_profit': location_profit,
                'profit_margin_percentage': round(location_margin, 2),
                'roi_percentage': None  # Podría calcularse si hay inversión inicial registrada
            })
        
        # Encontrar mejor y peor ubicación
        if locations_financials:
            sorted_by_margin = sorted(
                locations_financials, 
                key=lambda x: x['profit_margin_percentage'], 
                reverse=True
            )
            best_performing = sorted_by_margin[0] if sorted_by_margin else None
            worst_performing = sorted_by_margin[-1] if sorted_by_margin and len(sorted_by_margin) > 1 else None
        else:
            best_performing = None
            worst_performing = None
        
        return {
            'total_revenue': total_revenue,
            'total_costs': total_costs,
            'net_profit': net_profit,
            'overall_margin_percentage': round(margin_percentage, 2),
            'locations_financials': locations_financials,
            'costs_by_type': costs_by_type,
            'best_performing_location': best_performing,
            'worst_performing_location': worst_performing
        }
    
    def _calculate_cost_for_period(
        self, 
        cost_config: CostConfiguration, 
        start_date: date, 
        end_date: date,
        days_in_period: int
    ) -> Decimal:
        """Calcular costo para un período según su frecuencia"""
        
        amount = cost_config.amount
        frequency = cost_config.frequency
        
        if frequency == 'daily':
            return amount * days_in_period
        elif frequency == 'weekly':
            weeks = days_in_period / 7
            return amount * Decimal(str(weeks))
        elif frequency == 'monthly':
            months = days_in_period / 30  # Aproximado
            return amount * Decimal(str(months))
        elif frequency == 'quarterly':
            quarters = days_in_period / 90  # Aproximado
            return amount * Decimal(str(quarters))
        elif frequency == 'annual':
            years = days_in_period / 365  # Aproximado
            return amount * Decimal(str(years))
        else:
            # Frecuencia desconocida, asumir mensual
            months = days_in_period / 30
            return amount * Decimal(str(months))
    
    # ==================== UTILIDADES ====================
    
    def get_company_info(self) -> Optional[Company]:
        """Obtener información de la empresa"""
        return self.db.query(Company).filter(
            Company.id == self.company_id
        ).first()