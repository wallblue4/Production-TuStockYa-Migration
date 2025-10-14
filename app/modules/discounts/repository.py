# app/modules/discounts/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal

from app.shared.database.models import DiscountRequest, User

class DiscountsRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_discount_request(
        self, 
        seller_id: int, 
        amount: float, 
        reason: str,
        company_id: int  # ✅ AGREGAR
    ) -> DiscountRequest:
        """Crear solicitud de descuento"""
        discount_request = DiscountRequest(
            company_id=company_id,  # ✅ AGREGAR
            seller_id=seller_id,
            amount=amount,
            reason=reason,
            status='pending',
            requested_at=datetime.now()
        )
        
        self.db.add(discount_request)
        self.db.commit()
        self.db.refresh(discount_request)
        
        return discount_request
    
    def get_discount_requests_by_seller(
        self, 
        seller_id: int,
        company_id: int  # ✅ AGREGAR
    ) -> List[DiscountRequest]:
        """Obtener solicitudes del vendedor - Solo de su compañía"""
        return self.db.query(DiscountRequest).filter(
            and_(
                DiscountRequest.seller_id == seller_id,
                DiscountRequest.company_id == company_id  # ✅ FILTRO CRÍTICO
            )
        ).order_by(DiscountRequest.requested_at.desc()).all()
    
    def get_discount_requests_summary(
        self, 
        seller_id: int,
        company_id: int  # ✅ AGREGAR
    ) -> Dict[str, int]:
        """Resumen de solicitudes por estado"""
        from sqlalchemy import func, case
        
        result = self.db.query(
            func.count(case((DiscountRequest.status == 'pending', 1))).label('pending'),
            func.count(case((DiscountRequest.status == 'approved', 1))).label('approved'),
            func.count(case((DiscountRequest.status == 'rejected', 1))).label('rejected')
        ).filter(
            and_(
                DiscountRequest.seller_id == seller_id,
                DiscountRequest.company_id == company_id  # ✅ FILTRO CRÍTICO
            )
        ).first()
        
        return {
            'pending': result.pending,
            'approved': result.approved,
            'rejected': result.rejected,
            'total': result.pending + result.approved + result.rejected
        }
    
    def get_pending_discount_requests(
        self,
        company_id: int  # ✅ AGREGAR
    ) -> List[DiscountRequest]:
        """Obtener solicitudes pendientes - Solo de la compañía"""
        return self.db.query(DiscountRequest).filter(
            and_(
                DiscountRequest.status == 'pending',
                DiscountRequest.company_id == company_id  # ✅ FILTRO CRÍTICO
            )
        ).order_by(DiscountRequest.requested_at).all()
    
    def approve_discount_request(
        self,
        request_id: int,
        admin_id: int,
        approved: bool,
        admin_notes: str,
        company_id: int  # ✅ AGREGAR
    ) -> DiscountRequest:
        """Aprobar/rechazar solicitud"""
        discount_request = self.db.query(DiscountRequest).filter(
            and_(
                DiscountRequest.id == request_id,
                DiscountRequest.company_id == company_id  # ✅ VALIDACIÓN DE SEGURIDAD
            )
        ).first()
        
        if not discount_request:
            return None
        
        discount_request.status = 'approved' if approved else 'rejected'
        discount_request.administrator_id = admin_id
        discount_request.reviewed_at = datetime.now()
        discount_request.admin_comments = admin_notes
        
        self.db.commit()
        self.db.refresh(discount_request)
        
        return discount_request