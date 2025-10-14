# app/modules/warehouse_new/service.py
from typing import Dict, Any
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.orm import Session, Query
from sqlalchemy import and_
import logging

from .repository import WarehouseRepository
from .schemas import (
    WarehouseRequestAcceptance, CourierDelivery, 
    PendingRequestsResponse, AcceptedRequestsResponse, InventoryByLocationResponse ,VendorDelivery
)
from app.shared.database.models import TransferRequest

from app.modules.transfers_new.schemas import ReturnReceptionConfirmation

logger = logging.getLogger(__name__)

class WarehouseService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = WarehouseRepository(db)
    
    async def get_pending_requests(self, user_id: int, user_info: Dict[str, Any]) -> PendingRequestsResponse:
        """BG001: Obtener solicitudes pendientes para bodeguero"""
        requests = self.repository.get_pending_requests_for_warehouse(user_id, self.company_id)
        
        # Estadísticas como en backend antiguo
        breakdown = {
            "total": len(requests),
            "transfers": len([r for r in requests if r['request_type'] == 'transfer']),
            "returns": len([r for r in requests if r['request_type'] == 'return']),
            "urgent_returns": len([r for r in requests if r['request_type'] == 'return']),
            "high_priority": len([r for r in requests if r['urgent_action']])
        }
        
        return PendingRequestsResponse(
            success=True,
            message="Vista unificada: transferencias y devoluciones usan el mismo flujo de procesamiento",
            pending_requests=requests,
            count=len(requests),
            breakdown=breakdown,
            warehouse_keeper=f"{user_info['first_name']} {user_info['last_name']}"
        )
    
    async def accept_request(self, acceptance: WarehouseRequestAcceptance, warehouse_keeper_id: int) -> Dict[str, Any]:
        """BG002: Aceptar/rechazar solicitud de transferencia"""
        
        # Validar que la solicitud existe y está pendiente
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(status_code=403, detail="No tienes ubicaciones asignadas")
        
        acceptance_data = {
            'accepted': acceptance.accepted,
            'rejection_reason': acceptance.rejection_reason,
            'warehouse_notes': acceptance.warehouse_notes
        }
        
        success = self.repository.accept_transfer_request(
            acceptance.transfer_request_id, acceptance_data, warehouse_keeper_id, self.company_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada o no autorizada")
        
        return {
            "success": True,
            "message": "Solicitud aceptada - Disponible para corredores" if acceptance.accepted else "Solicitud rechazada",
            "request_id": acceptance.transfer_request_id,
            "status": "accepted" if acceptance.accepted else "rejected",
            "next_step": "Esperando asignación de corredor" if acceptance.accepted else "Solicitud finalizada"
        }
    
    async def get_accepted_requests(self, warehouse_keeper_id: int, user_info: Dict[str, Any]) -> AcceptedRequestsResponse:
        """BG002: Obtener solicitudes aceptadas y en preparación"""
        requests = self.repository.get_accepted_requests_by_warehouse_keeper(warehouse_keeper_id, self.company_id)
        
        return AcceptedRequestsResponse(
            success=True,
            message="Solicitudes aceptadas y en preparación y las devoluciones pendientes",
            accepted_requests=requests,
            count=len(requests),
            warehouse_info={
                "warehouse_keeper": f"{user_info['first_name']} {user_info['last_name']}",
                "location_assignments": len(self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id))
            }
        )
    
    # warehouse_new/service.py

    async def deliver_to_courier(
        self, 
        delivery: CourierDelivery, 
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """BG003: Entregar productos a corredor con todas las validaciones"""
        
        # Validar permisos del bodeguero
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(
                status_code=403, 
                detail="No tienes ubicaciones asignadas como bodeguero"
            )
        
        # Validar que la transferencia es de una ubicación gestionada
        transfer = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.id == delivery.transfer_request_id,
                TransferRequest.company_id == self.company_id
            )
        ).first()
        
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        
        if transfer.source_location_id not in location_ids:
            raise HTTPException(
                status_code=403, 
                detail=f"No tienes permisos para gestionar la ubicación origen (ID: {transfer.source_location_id})"
            )
        
        # Preparar datos
        delivery_data = {
            'courier_id': delivery.courier_id,
            'delivery_notes': delivery.delivery_notes
        }
        
        try:
            # Llamar al repository que hace toda la lógica
            result = self.repository.deliver_to_courier(
                delivery.transfer_request_id, 
                delivery_data,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Producto entregado a corredor - Inventario actualizado automáticamente",
                **result
            }
            
        except ValueError as e:
            # Re-lanzar errores de validación
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # Re-lanzar errores del sistema
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_inventory_by_location(self, location_id: int) -> InventoryByLocationResponse:
        """BG006: Consultar inventario disponible por ubicación"""
        inventory = self.repository.get_inventory_by_location(location_id, self.company_id)
        
        # Calcular resumen
        total_products = len(inventory)
        total_quantity = sum(item['quantity'] for item in inventory)
        total_value = sum(item['total_value'] for item in inventory)
        available_products = len([item for item in inventory if item['quantity'] > 0])
        
        return InventoryByLocationResponse(
            success=True,
            message=f"Inventario de Local #{location_id}",
            location_info={
                "location_id": location_id,
                "location_name": f"Local #{location_id}"
            },
            inventory=inventory,
            summary={
                "total_products": total_products,
                "available_products": available_products,
                "out_of_stock": total_products - available_products,
                "total_quantity": total_quantity,
                "total_value": total_value,
                "average_price": total_value / total_quantity if total_quantity > 0 else 0
            }
        )
    
    async def deliver_to_vendor(
        self, 
        transfer_id: int,
        delivery: VendorDelivery, 
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """
        Entregar producto directamente al vendedor (self-pickup)
        
        Validaciones:
        - Bodeguero tiene permisos para la ubicación origen
        - Transferencia es válida y tiene pickup_type = 'vendedor'
        - Stock disponible para entrega
        
        Proceso:
        - Descuento automático de inventario
        - Cambio de estado a 'in_transit'
        - Registro de timestamp
        """
        
        # Validar permisos del bodeguero
        managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
        location_ids = [loc['location_id'] for loc in managed_locations]
        
        if not location_ids:
            raise HTTPException(
                status_code=403, 
                detail="No tienes ubicaciones asignadas como bodeguero"
            )
        
        # Validar que la transferencia es de una ubicación gestionada
        transfer = self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.id == transfer_id,
                TransferRequest.company_id == self.company_id
            )
        ).first()
        
        if not transfer:
            raise HTTPException(status_code=404, detail="Transferencia no encontrada")
        
        if transfer.source_location_id not in location_ids:
            raise HTTPException(
                status_code=403, 
                detail=f"No tienes permisos para gestionar la ubicación origen (ID: {transfer.source_location_id})"
            )
        
        # Preparar datos para el repository
        delivery_data = {
            'delivered': delivery.delivered,
            'delivery_notes': delivery.delivery_notes or 'Entregado al vendedor para auto-recogida'
        }
        
        try:
            # Llamar al repository que hace toda la lógica
            result = self.repository.deliver_to_vendor(
                transfer_id, 
                delivery_data,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Producto entregado al vendedor - Inventario actualizado automáticamente",
                **result
            }
            
        except ValueError as e:
            # Re-lanzar errores de validación
            raise HTTPException(status_code=400, detail=str(e))
        except RuntimeError as e:
            # Re-lanzar errores del sistema
            raise HTTPException(status_code=500, detail=str(e))

    # AGREGAR AL FINAL DE app/modules/warehouse_new/service.py

    async def confirm_return_reception(
        self,
        return_id: int,
        reception: ReturnReceptionConfirmation,
        warehouse_keeper_id: int
    ) -> Dict[str, Any]:
        """
        BG010: Confirmar recepción de devolución con RESTAURACIÓN de inventario
        
        Proceso:
        1. Validar que es un return (original_transfer_id != NULL)
        2. Validar permisos del bodeguero
        3. Verificar condición del producto
        4. SUMAR inventario en bodega (reversión)
        5. Marcar como completado
        6. Registrar en historial
        """
        
        try:
            logger.info(f"📦 Confirmando recepción de return #{return_id}")
            
            # Validar permisos
            managed_locations = self.repository.get_user_managed_locations(warehouse_keeper_id, self.company_id)
            location_ids = [loc['location_id'] for loc in managed_locations]
            
            if not location_ids:
                raise HTTPException(403, detail="No tienes ubicaciones asignadas")
            
            # Llamar al repository
            result = self.repository.confirm_return_reception(
                return_id,
                reception.dict(),
                warehouse_keeper_id,
                location_ids,
                self.company_id
            )
            
            return {
                "success": True,
                "message": "Devolución recibida - Inventario restaurado automáticamente",
                "return_id": result["return_id"],
                "original_transfer_id": result["original_transfer_id"],
                "received_quantity": result["received_quantity"],
                "product_condition": result["product_condition"],
                "inventory_restored": result["inventory_restored"],
                "warehouse_location": result["warehouse_location"],
                "inventory_change": result["inventory_change"]
            }
            
        except ValueError as e:
            raise HTTPException(400, detail=str(e))
        except RuntimeError as e:
            raise HTTPException(500, detail=str(e))