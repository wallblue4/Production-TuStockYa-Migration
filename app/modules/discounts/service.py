# app/modules/discounts/service.py
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .repository import DiscountsRepository
from .schemas import DiscountRequestCreate, DiscountRequestResponse, MyDiscountRequestsResponse
from app.shared.database.models import Company
from app.shared.database.models import User


class DiscountsService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = DiscountsRepository(db)
        self.MAX_DISCOUNT_AMOUNT = 5000
    
    async def create_discount_request(
        self,
        discount_data: DiscountRequestCreate,
        seller_id: int,
        company_id: int  # ✅ AGREGAR
    ) -> DiscountRequestResponse:
        """Crear solicitud de descuento"""
        
        # Validar que el vendedor pertenece a la compañía
        seller = self.db.query(User).filter(
            and_(
                User.id == seller_id,
                User.company_id == company_id  # ✅ VALIDACIÓN
            )
        ).first()
        
        if not seller:
            raise HTTPException(
                status_code=403,
                detail="Usuario no autorizado para esta operación"
            )
        
        # Validaciones como en el backend antiguo
        if discount_data.amount > self.MAX_DISCOUNT_AMOUNT:
            raise HTTPException(
                status_code=400,
                detail=f"El descuento máximo es de ${self.MAX_DISCOUNT_AMOUNT:,} pesos."
            )
        
        if discount_data.amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="El monto del descuento debe ser mayor a $0"
            )
        
        try:
            # Crear solicitud en BD con company_id
            discount_request = self.repository.create_discount_request(
                seller_id=seller_id,
                amount=discount_data.amount,
                reason=discount_data.reason,
                company_id=company_id  # ✅ PASAR COMPANY_ID
            )
            
            return DiscountRequestResponse(
                success=True,
                message="Solicitud de descuento enviada al administrador",
                discount_request_id=discount_request.id,
                amount=discount_request.amount,
                reason=discount_request.reason,
                status=discount_request.status,
                requested_at=discount_request.requested_at,
                seller_info={
                    "seller_id": seller_id,
                    "seller_name": seller.full_name
                },
                within_limit=discount_data.amount <= self.MAX_DISCOUNT_AMOUNT,
                max_allowed=self.MAX_DISCOUNT_AMOUNT
            )
            
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error creando solicitud: {str(e)}"
            )
    
    async def get_my_discount_requests(
        self, 
        seller_id: int,
        company_id: int  # ✅ AGREGAR
    ) -> MyDiscountRequestsResponse:
        """Obtener mis solicitudes de descuento"""
        
        # Obtener solicitudes del vendedor (ya filtradas por company_id en repo)
        requests = self.repository.get_discount_requests_by_seller(
            seller_id, 
            company_id  # ✅ PASAR COMPANY_ID
        )
        summary = self.repository.get_discount_requests_summary(
            seller_id,
            company_id  # ✅ PASAR COMPANY_ID
        )
        
        return MyDiscountRequestsResponse(
            success=True,
            message="Solicitudes de descuento obtenidas",
            requests=requests,
            summary=summary,
            seller_info={
                "seller_id": seller_id,
                "can_request_more": True,
                "max_amount_per_request": self.MAX_DISCOUNT_AMOUNT
            }
        )