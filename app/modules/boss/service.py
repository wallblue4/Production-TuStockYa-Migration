# app/modules/boss/service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Dict, Any, List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.shared.database.models import User, Location
from .repository import BossRepository
from .schemas import (
    LocationCreate, LocationResponse, ExecutiveDashboard, KPIMetric,
    LocationPerformance, SalesConsolidatedReport, ReportFilters,
    ConsolidatedInventory, CategoryInventory, LocationInventory,
    FinancialAnalysis, LocationFinancials
)

class BossService:
    """Servicio de lógica de negocio para Boss"""
    
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = BossRepository(db, company_id)
    
    # ==================== CREACIÓN DE UBICACIONES ====================
    
    async def create_location(
        self, 
        location_data: LocationCreate, 
        boss: User
    ) -> LocationResponse:
        """
        BS008: Crear nuevos locales de venta
        BS009: Crear nuevas bodegas
        """
        
        # Validar que el usuario es Boss
        if boss.role != "boss":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo el Boss puede crear ubicaciones"
            )
        
        # Validar que no exista una ubicación con el mismo nombre
        existing = self.db.query(Location).filter(
            Location.company_id == self.company_id,
            Location.name == location_data.name
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe una ubicación con el nombre '{location_data.name}'"
            )
        
        # Crear ubicación
        location_dict = location_data.dict()
        location_dict['type'] = location_data.type.value
        
        location = self.repository.create_location(location_dict, boss.id)
        
        try:
            self.db.commit()
            self.db.refresh(location)
        except Exception as e:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear ubicación: {str(e)}"
            )
        
        # Construir respuesta
        return LocationResponse(
            id=location.id,
            company_id=location.company_id,
            name=location.name,
            type=location.type,
            address=location.address,
            phone=location.phone,
            is_active=location.is_active,
            created_at=location.created_at,
            created_by_name=boss.full_name,
            total_users=0,
            total_products=0,
            total_inventory_value=Decimal('0')
        )
    
    async def get_all_locations(
        self, 
        boss: User,
        include_inactive: bool = False
    ) -> List[LocationResponse]:
        """Obtener todas las ubicaciones de la empresa"""
        
        locations = self.repository.get_all_company_locations(include_inactive)
        
        response = []
        for location in locations:
            # Contar usuarios
            users_count = self.db.query(User).filter(
                User.company_id == self.company_id,
                User.location_id == location.id,
                User.is_active == True
            ).count()
            
            # Contar productos y valor
            from app.shared.database.models import Product, ProductSize
            from sqlalchemy import func
            
            inventory_data = self.db.query(
                func.count(func.distinct(Product.id)),
                func.coalesce(func.sum(ProductSize.quantity * Product.unit_price), 0)
            ).join(ProductSize).filter(
                Product.company_id == self.company_id,
                ProductSize.company_id == self.company_id,
                ProductSize.location_name == location.name,
                Product.is_active == 1
            ).first()
            
            response.append(LocationResponse(
                id=location.id,
                company_id=location.company_id,
                name=location.name,
                type=location.type,
                address=location.address,
                phone=location.phone,
                is_active=location.is_active,
                created_at=location.created_at,
                created_by_name=None,
                total_users=users_count,
                total_products=inventory_data[0] or 0,
                total_inventory_value=inventory_data[1] or Decimal('0')
            ))
        
        return response
    
    # ==================== DASHBOARD EJECUTIVO ====================
    
    async def get_executive_dashboard(
        self, 
        boss: User,
        target_date: Optional[date] = None
    ) -> ExecutiveDashboard:
        """BS001: Visualizar dashboard ejecutivo con KPIs principales"""
        
        if not target_date:
            target_date = date.today()
        
        # Obtener información de la empresa
        company = self.repository.get_company_info()
        
        # Obtener KPIs
        kpis_data = self.repository.get_company_kpis(target_date)
        
        # Construir KPIs
        kpis = {}
        
        # Ventas de hoy
        today_change = self._calculate_change_percentage(
            kpis_data['today_sales'], 
            kpis_data['yesterday_sales']
        )
        kpis['ventas_hoy'] = KPIMetric(
            label="Ventas Hoy",
            value=kpis_data['today_sales'],
            previous_value=kpis_data['yesterday_sales'],
            change_percentage=today_change,
            trend=self._get_trend(today_change)
        )
        
        # Ventas del mes
        month_change = self._calculate_change_percentage(
            kpis_data['month_sales'], 
            kpis_data['prev_month_sales']
        )
        kpis['ventas_mes'] = KPIMetric(
            label="Ventas del Mes",
            value=kpis_data['month_sales'],
            previous_value=kpis_data['prev_month_sales'],
            change_percentage=month_change,
            trend=self._get_trend(month_change)
        )
        
        # Inventario
        kpis['inventario_total'] = KPIMetric(
            label="Valor Inventario",
            value=kpis_data['inventory_value'],
            previous_value=None,
            change_percentage=None,
            trend="stable"
        )
        
        # Transacciones
        kpis['transacciones_hoy'] = KPIMetric(
            label="Transacciones Hoy",
            value=Decimal(str(kpis_data['today_transactions'])),
            previous_value=None,
            change_percentage=None,
            trend="stable"
        )
        
        # Usuarios activos
        kpis['usuarios_activos'] = KPIMetric(
            label="Usuarios Activos",
            value=Decimal(str(kpis_data['active_users'])),
            previous_value=None,
            change_percentage=None,
            trend="stable"
        )
        
        # Ubicaciones activas
        kpis['ubicaciones_activas'] = KPIMetric(
            label="Ubicaciones Activas",
            value=Decimal(str(kpis_data['active_locations'])),
            previous_value=None,
            change_percentage=None,
            trend="stable"
        )
        
        # Performance de ubicaciones (último mes)
        end_date = target_date
        start_date = end_date - timedelta(days=30)
        locations_perf = self.repository.get_locations_performance(start_date, end_date)
        
        locations_performance = [
            LocationPerformance(**loc) for loc in locations_perf
        ]
        
        # Resumen financiero (último mes)
        financial_data = self.repository.get_financial_analysis(start_date, end_date)
        financial_summary = {
            'ingresos_totales': financial_data['total_revenue'],
            'costos_totales': financial_data['total_costs'],
            'utilidad_neta': financial_data['net_profit'],
            'margen_porcentaje': Decimal(str(financial_data['overall_margin_percentage']))
        }
        
        # Alertas
        alerts = self.repository.get_company_alerts()
        
        # Métricas de crecimiento
        growth_metrics = {
            'ventas_mes_anterior': kpis_data['prev_month_sales'],
            'ventas_mes_actual': kpis_data['month_sales'],
            'crecimiento_porcentaje': month_change,
            'proyeccion_mes': self._project_month_sales(kpis_data['month_sales'], target_date)
        }
        
        return ExecutiveDashboard(
            company_name=company.name if company else "Mi Empresa",
            boss_name=boss.full_name,
            dashboard_date=target_date,
            kpis=kpis,
            locations_performance=locations_performance,
            financial_summary=financial_summary,
            alerts=alerts,
            growth_metrics=growth_metrics
        )
    
    # ==================== REPORTES DE VENTAS ====================
    
    async def get_consolidated_sales_report(
        self,
        boss: User,
        filters: ReportFilters
    ) -> SalesConsolidatedReport:
        """BS002: Acceder a reportes de ventas consolidados"""
        
        report_data = self.repository.get_consolidated_sales_report(
            filters.start_date,
            filters.end_date,
            filters.location_ids
        )
        
        # Determinar período
        days_diff = (filters.end_date - filters.start_date).days + 1
        if days_diff == 1:
            period = "Diario"
        elif days_diff <= 7:
            period = "Semanal"
        elif days_diff <= 31:
            period = "Mensual"
        else:
            period = "Personalizado"
        
        return SalesConsolidatedReport(
            report_period=period,
            start_date=filters.start_date,
            end_date=filters.end_date,
            generated_at=datetime.now(),
            total_sales=report_data['total_sales'],
            total_transactions=report_data['total_transactions'],
            average_ticket=report_data['average_ticket'],
            sales_by_location=report_data['sales_by_location'],
            top_sellers=report_data['top_sellers'],
            top_products=report_data['top_products'],
            payment_methods_breakdown=report_data['payment_methods']
        )
    
    # ==================== INVENTARIO CONSOLIDADO ====================
    
    async def get_consolidated_inventory(
        self,
        boss: User
    ) -> ConsolidatedInventory:
        """BS003: Consultar inventario total por categorías"""
        
        inventory_data = self.repository.get_consolidated_inventory()
        
        # Obtener número de ubicaciones activas
        total_locations = len(self.repository.get_all_company_locations())
        
        # Convertir listas
        by_brand = [CategoryInventory(**cat) for cat in inventory_data['by_brand']]
        by_location = [LocationInventory(**loc) for loc in inventory_data['by_location']]
        
        return ConsolidatedInventory(
            report_date=date.today(),
            total_locations=total_locations,
            total_products=inventory_data['total_products'],
            total_units=inventory_data['total_units'],
            total_value=inventory_data['total_value'],
            by_brand=by_brand,
            by_location=by_location,
            low_stock_alerts=inventory_data['low_stock_alerts'],
            out_of_stock_alerts=inventory_data['out_of_stock_alerts'],
            overstocked_alerts=inventory_data['overstocked_alerts']
        )
    
    # ==================== ANÁLISIS FINANCIERO ====================
    
    async def get_financial_analysis(
        self,
        boss: User,
        start_date: date,
        end_date: date
    ) -> FinancialAnalysis:
        """BS004: Revisar costos operativos y márgenes de ganancia"""
        
        financial_data = self.repository.get_financial_analysis(start_date, end_date)
        
        # Determinar período
        days_diff = (end_date - start_date).days + 1
        if days_diff <= 31:
            period = "Mensual"
        elif days_diff <= 92:
            period = "Trimestral"
        elif days_diff <= 366:
            period = "Anual"
        else:
            period = "Personalizado"
        
        # Convertir ubicaciones financieras
        locations_financials = [
            LocationFinancials(**loc) for loc in financial_data['locations_financials']
        ]
        
        return FinancialAnalysis(
            analysis_period=period,
            start_date=start_date,
            end_date=end_date,
            total_revenue=financial_data['total_revenue'],
            total_costs=financial_data['total_costs'],
            net_profit=financial_data['net_profit'],
            overall_margin_percentage=financial_data['overall_margin_percentage'],
            locations_financials=locations_financials,
            costs_by_type=financial_data['costs_by_type'],
            best_performing_location=financial_data['best_performing_location'],
            worst_performing_location=financial_data['worst_performing_location'],
            margin_trend=None  # Podría implementarse con datos históricos
        )
    
    # ==================== UTILIDADES ====================
    
    def _calculate_change_percentage(
        self, 
        current: Decimal, 
        previous: Decimal
    ) -> Optional[float]:
        """Calcular porcentaje de cambio"""
        if previous == 0:
            return None if current == 0 else 100.0
        
        change = ((current - previous) / previous) * 100
        return round(float(change), 2)
    
    def _get_trend(self, change_percentage: Optional[float]) -> str:
        """Determinar tendencia basada en porcentaje de cambio"""
        if change_percentage is None:
            return "stable"
        elif change_percentage > 5:
            return "up"
        elif change_percentage < -5:
            return "down"
        else:
            return "stable"
    
    def _project_month_sales(self, current_month_sales: Decimal, target_date: date) -> Decimal:
        """Proyectar ventas del mes completo"""
        day_of_month = target_date.day
        
        if day_of_month == 0:
            return current_month_sales
        
        # Calcular días del mes
        import calendar
        days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
        
        # Proyección simple lineal
        daily_average = current_month_sales / day_of_month
        projected = daily_average * days_in_month
        
        return projected