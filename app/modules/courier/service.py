# app/modules/courier/service.py
from typing import Dict, Any
from datetime import datetime, date
from fastapi import HTTPException
from sqlalchemy.orm import Session

from .repository import CourierRepository
from .schemas import (
    CourierAcceptance, PickupConfirmation, DeliveryConfirmation, TransportIncidentReport,
    AvailableRequestsResponse, MyTransportsResponse, DeliveryHistoryResponse
)

class CourierService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = CourierRepository(db)
    
    async def get_available_requests(self, courier_id: int, user_info: Dict[str, Any]) -> Dict[str, Any]:
        """CO001: Obtener solicitudes disponibles para corredor"""
        
        requests = self.repository.get_available_requests_for_courier(self.company_id)
        
        # ✅ USAR .get() PARA EVITAR KeyError
        breakdown = {
            "total": len(requests),
            "available_to_accept": len([
                r for r in requests 
                if r.get('status') == 'accepted' and r.get('courier_id') is None
            ]),
            "assigned_to_me": len([
                r for r in requests 
                if r.get('courier_id') == courier_id
            ]),
            "in_transit": len([
                r for r in requests 
                if r.get('status') == 'in_transit' and r.get('courier_id') == courier_id
            ])
        }
        
        return {
            "success": True,
            "message": f"Solicitudes disponibles para transporte",
            "available_requests": requests,
            "count": len(requests),
            "breakdown": breakdown,
            "courier_info": {
                "name": f"{user_info['first_name']} {user_info['last_name']}",
                "courier_id": courier_id
            }
        }
    
    async def accept_request(self, request_id: int, acceptance: CourierAcceptance, courier_id: int) -> Dict[str, Any]:
        """CO002: Aceptar solicitud e iniciar recorrido"""
        
        success = self.repository.accept_courier_request(
            request_id, courier_id, acceptance.estimated_pickup_time, acceptance.notes, self.company_id
        )
        
        if not success:
            raise HTTPException(
                status_code=404, 
                detail="Solicitud no disponible o ya fue asignada a otro corredor"
            )
        
        return {
            "success": True,
            "message": "Solicitud de transporte aceptada exitosamente",
            "request_id": request_id,
            "status": "courier_assigned",
            "estimated_pickup_time": acceptance.estimated_pickup_time,
            "accepted_at": datetime.now().isoformat(),
            "next_step": "Dirigirse al punto de recolección"
        }
    
    async def confirm_pickup(self, request_id: int, pickup_data: PickupConfirmation, courier_id: int) -> Dict[str, Any]:
        """CO003: Confirmar recolección"""
        
        success = self.repository.confirm_pickup(request_id, courier_id, pickup_data.pickup_notes, self.company_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada o no autorizada")
        
        return {
            "success": True,
            "message": "Recolección confirmada - Producto en tránsito",
            "request_id": request_id,
            "picked_up_at": datetime.now().isoformat(),
            "status": "in_transit",
            "next_step": "Dirigirse al punto de entrega"
        }
    
    async def confirm_delivery(self, request_id: int, delivery_data: DeliveryConfirmation, courier_id: int) -> Dict[str, Any]:
        """CO004: Confirmar entrega"""
        
        success = self.repository.confirm_delivery(
            request_id, courier_id, delivery_data.delivery_successful, delivery_data.notes, self.company_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        
        status = "delivered" if delivery_data.delivery_successful else "delivery_failed"
        message = "Entrega confirmada exitosamente" if delivery_data.delivery_successful else "Entrega marcada con problemas"
        next_step = "Vendedor debe confirmar recepción" if delivery_data.delivery_successful else "Revisar problemas reportados"
        
        return {
            "success": True,
            "message": message,
            "transfer_id": request_id,
            "status": status,
            "delivered_at": datetime.now().isoformat(),
            "delivery_successful": delivery_data.delivery_successful,
            "next_step": next_step
        }
    
    async def report_incident(self, request_id: int, incident_data: TransportIncidentReport, courier_id: int) -> Dict[str, Any]:
        """CO005: Reportar incidencias durante el transporte"""
        
        incident_id = self.repository.report_incident(
            request_id, courier_id, incident_data.incident_type, incident_data.description, self.company_id
        )
        
        if not incident_id:
            raise HTTPException(status_code=500, detail="Error reportando incidencia")
        
        return {
            "success": True,
            "message": "Incidencia reportada exitosamente",
            "incident_id": incident_id,
            "transfer_request_id": request_id,
            "incident_type": incident_data.incident_type,
            "reported_at": datetime.now().isoformat(),
            "next_steps": [
                "El incidente será revisado por supervisión",
                "Continúa con la entrega si es posible",
                "Contacta soporte si necesitas asistencia"
            ]
        }
    
    async def get_my_transports(self, courier_id: int, user_info: Dict[str, Any]) -> MyTransportsResponse:
        """Obtener transportes asignados al corredor"""
        transports = self.repository.get_my_transports(courier_id, self.company_id)
        
        # Estadísticas del corredor
        total_transports = len(transports)
        in_progress = len([t for t in transports if t['status'] in ['courier_assigned', 'in_transit']])
        completed = len([t for t in transports if t['status'] in ['delivered', 'completed']])
        
        return MyTransportsResponse(
            success=True,
            message="Transportes asignados",
            my_transports=transports,
            count=total_transports,
            courier_stats={
                "total_transports": total_transports,
                "in_progress": in_progress,
                "completed": completed,
                "completion_rate": (completed / total_transports * 100) if total_transports > 0 else 0
            }
        )
    
    async def get_delivery_history(self, courier_id: int, user_info: Dict[str, Any]) -> DeliveryHistoryResponse:
        """CO006: Obtener historial de entregas del día"""
        deliveries = self.repository.get_delivery_history_today(courier_id, self.company_id)
        
        # Estadísticas del día
        total_deliveries = len(deliveries)
        successful_deliveries = len([d for d in deliveries if d['delivery_successful']])
        failed_deliveries = total_deliveries - successful_deliveries
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        return DeliveryHistoryResponse(
            success=True,
            message=f"Entregas del día - {date.today().isoformat()}",
            recent_deliveries=deliveries,
            today_stats={
                "total_deliveries": total_deliveries,
                "successful_deliveries": successful_deliveries,
                "failed_deliveries": failed_deliveries,
                "success_rate": round(success_rate, 1)
            },
            performance_metrics={
                "efficiency": "Excelente" if success_rate >= 95 else "Buena" if success_rate >= 80 else "Regular",
                "courier_name": f"{user_info['first_name']} {user_info['last_name']}",
                "date": date.today().isoformat()
            }
        )