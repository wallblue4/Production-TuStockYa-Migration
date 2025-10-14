from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, desc
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.shared.database.models import Mayoreo, VentaMayoreo, User
from .schemas import MayoreoSearchParams, VentaMayoreoSearchParams

class MayoreoRepository:
    def __init__(self, db: Session):
        self.db = db

    # ===== MAYOREO CRUD OPERATIONS =====

    def create_mayoreo(self, mayoreo_data: dict, user_id: int, company_id: int) -> Mayoreo:
        """Crear un nuevo producto de mayoreo"""
        mayoreo = Mayoreo(
            user_id=user_id,
            company_id=company_id,
            **mayoreo_data
        )
        self.db.add(mayoreo)
        self.db.commit()
        self.db.refresh(mayoreo)
        return mayoreo

    def get_mayoreo_by_id(self, mayoreo_id: int) -> Optional[Mayoreo]:
        """Obtener un producto de mayoreo por ID"""
        return self.db.query(Mayoreo).filter(Mayoreo.id == mayoreo_id).first()

    def get_all_mayoreo(self, user_id: int, company_id: int) -> List[Mayoreo]:
        """Obtener todos los productos de mayoreo de un usuario y compañía"""
        return self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id
            )
        ).order_by(desc(Mayoreo.created_at)).all()

    def search_mayoreo(self, user_id: int, company_id: int, search_params: MayoreoSearchParams) -> List[Mayoreo]:
        """Buscar productos de mayoreo con filtros"""
        query = self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id
            )
        )
        
        if search_params.modelo:
            query = query.filter(Mayoreo.modelo.ilike(f"%{search_params.modelo}%"))
        if search_params.tallas:
            query = query.filter(Mayoreo.tallas.ilike(f"%{search_params.tallas}%"))
        if search_params.is_active is not None:
            query = query.filter(Mayoreo.is_active == search_params.is_active)
            
        return query.order_by(desc(Mayoreo.created_at)).all()

    def update_mayoreo(self, mayoreo_id: int, user_id: int, company_id: int, update_data: dict) -> Optional[Mayoreo]:
        """Actualizar un producto de mayoreo"""
        mayoreo = self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.id == mayoreo_id,
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id
            )
        ).first()
        
        if mayoreo:
            for key, value in update_data.items():
                if value is not None:
                    setattr(mayoreo, key, value)
            self.db.commit()
            self.db.refresh(mayoreo)
        
        return mayoreo

    def delete_mayoreo(self, mayoreo_id: int, user_id: int, company_id: int) -> bool:
        """Eliminar un producto de mayoreo (soft delete)"""
        mayoreo = self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.id == mayoreo_id,
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id
            )
        ).first()
        
        if mayoreo:
            mayoreo.is_active = False
            self.db.commit()
            return True
        return False

    def hard_delete_mayoreo(self, mayoreo_id: int, user_id: int) -> bool:
        """Eliminar permanentemente un producto de mayoreo"""
        mayoreo = self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.id == mayoreo_id,
                Mayoreo.user_id == user_id
            )
        ).first()
        
        if mayoreo:
            self.db.delete(mayoreo)
            self.db.commit()
            return True
        return False

    # ===== VENTA MAYOREO CRUD OPERATIONS =====

    def create_venta_mayoreo(self, venta_data: dict, user_id: int, company_id: int) -> VentaMayoreo:
        """Crear una nueva venta de mayoreo"""
        # Calcular el total de la venta
        total_venta = venta_data['cantidad_cajas_vendidas'] * venta_data['precio_unitario_venta']
        
        venta = VentaMayoreo(
            user_id=user_id,
            company_id=company_id,
            total_venta=total_venta,
            **venta_data
        )
        self.db.add(venta)
        
        # Actualizar la cantidad disponible en el producto de mayoreo
        mayoreo = self.get_mayoreo_by_id(venta_data['mayoreo_id'])
        if mayoreo:
            mayoreo.cantidad_cajas_disponibles -= venta_data['cantidad_cajas_vendidas']
            if mayoreo.cantidad_cajas_disponibles < 0:
                mayoreo.cantidad_cajas_disponibles = 0
        
        self.db.commit()
        self.db.refresh(venta)
        return venta

    def get_venta_mayoreo_by_id(self, venta_id: int) -> Optional[VentaMayoreo]:
        """Obtener una venta de mayoreo por ID"""
        return self.db.query(VentaMayoreo).filter(VentaMayoreo.id == venta_id).first()

    def get_all_ventas_mayoreo(self, user_id: int, company_id: int) -> List[VentaMayoreo]:
        """Obtener todas las ventas de mayoreo de un usuario y compañía"""
        return self.db.query(VentaMayoreo).join(Mayoreo).filter(
            and_(
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.company_id == company_id
            )
        ).order_by(desc(VentaMayoreo.fecha_venta)).all()

    def search_ventas_mayoreo(self, user_id: int, company_id: int, search_params: VentaMayoreoSearchParams) -> List[VentaMayoreo]:
        """Buscar ventas de mayoreo con filtros"""
        query = self.db.query(VentaMayoreo).join(Mayoreo).filter(
            and_(
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.company_id == company_id
            )
        )
        
        if search_params.mayoreo_id:
            query = query.filter(VentaMayoreo.mayoreo_id == search_params.mayoreo_id)
        if search_params.fecha_desde:
            query = query.filter(VentaMayoreo.fecha_venta >= search_params.fecha_desde)
        if search_params.fecha_hasta:
            query = query.filter(VentaMayoreo.fecha_venta <= search_params.fecha_hasta)
        if search_params.cantidad_minima:
            query = query.filter(VentaMayoreo.cantidad_cajas_vendidas >= search_params.cantidad_minima)
        if search_params.cantidad_maxima:
            query = query.filter(VentaMayoreo.cantidad_cajas_vendidas <= search_params.cantidad_maxima)
            
        return query.order_by(desc(VentaMayoreo.fecha_venta)).all()

    def get_ventas_by_mayoreo_id(self, mayoreo_id: int, user_id: int, company_id: int) -> List[VentaMayoreo]:
        """Obtener todas las ventas de un producto específico de mayoreo"""
        return self.db.query(VentaMayoreo).filter(
            and_(
                VentaMayoreo.mayoreo_id == mayoreo_id,
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.company_id == company_id
            )
        ).order_by(desc(VentaMayoreo.fecha_venta)).all()

    # ===== STATISTICS AND ANALYTICS =====

    def get_mayoreo_stats(self, user_id: int, company_id: int) -> Dict[str, Any]:
        """Obtener estadísticas de mayoreo"""
        # Estadísticas de productos
        total_productos = self.db.query(func.count(Mayoreo.id)).filter(
            and_(
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id,
                Mayoreo.is_active == True
            )
        ).scalar()
        
        total_cajas_disponibles = self.db.query(func.sum(Mayoreo.cantidad_cajas_disponibles)).filter(
            and_(
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id,
                Mayoreo.is_active == True
            )
        ).scalar() or 0
        
        valor_total_inventario = self.db.query(
            func.sum(Mayoreo.cantidad_cajas_disponibles * Mayoreo.pares_por_caja * Mayoreo.precio)
        ).filter(
            and_(
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id,
                Mayoreo.is_active == True
            )
        ).scalar() or 0
        
        # Estadísticas de ventas
        total_ventas = self.db.query(func.count(VentaMayoreo.id)).join(Mayoreo).filter(
            and_(
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.company_id == company_id
            )
        ).scalar()
        
        valor_total_ventas = self.db.query(func.sum(VentaMayoreo.total_venta)).join(Mayoreo).filter(
            and_(
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.company_id == company_id
            )
        ).scalar() or 0
        
        return {
            'total_productos': total_productos,
            'total_cajas_disponibles': total_cajas_disponibles,
            'valor_total_inventario': valor_total_inventario,
            'total_ventas': total_ventas,
            'valor_total_ventas': valor_total_ventas
        }

    def get_ventas_by_date_range(self, user_id: int, fecha_desde: datetime, fecha_hasta: datetime) -> List[VentaMayoreo]:
        """Obtener ventas en un rango de fechas"""
        return self.db.query(VentaMayoreo).join(Mayoreo).filter(
            and_(
                VentaMayoreo.user_id == user_id,
                VentaMayoreo.fecha_venta >= fecha_desde,
                VentaMayoreo.fecha_venta <= fecha_hasta
            )
        ).order_by(desc(VentaMayoreo.fecha_venta)).all()

    # ===== VALIDATION METHODS =====

    def validate_mayoreo_ownership(self, mayoreo_id: int, user_id: int, company_id: int) -> bool:
        """Validar que un producto de mayoreo pertenece al usuario y compañía"""
        mayoreo = self.db.query(Mayoreo).filter(
            and_(
                Mayoreo.id == mayoreo_id,
                Mayoreo.user_id == user_id,
                Mayoreo.company_id == company_id
            )
        ).first()
        return mayoreo is not None

    def validate_sufficient_stock(self, mayoreo_id: int, cantidad_requerida: int) -> bool:
        """Validar que hay suficiente stock para una venta"""
        mayoreo = self.get_mayoreo_by_id(mayoreo_id)
        if not mayoreo:
            return False
        return mayoreo.cantidad_cajas_disponibles >= cantidad_requerida

    def validate_user_is_admin(self, user_id: int) -> bool:
        """Validar que el usuario tiene rol de administrador"""
        user = self.db.query(User).filter(User.id == user_id).first()
        return user and user.role == 'administrador'
