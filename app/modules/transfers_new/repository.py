# app/modules/transfers_new/repository.py
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, text
from typing import List, Dict, Any, Optional ,Literal
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from app.shared.database.models import (
    TransferRequest, User, Location, Product, ProductSize, InventoryChange
)

logger = logging.getLogger(__name__)

class TransfersRepository:
    def __init__(self, db: Session):
        self.db = db
    
    def create_transfer_request(self, transfer_data: Dict[str, Any], requester_id: int, company_id: int) -> TransferRequest:
        """Crear nueva solicitud de transferencia"""
        transfer = TransferRequest(
            requester_id=requester_id,
            company_id=company_id,
            source_location_id=transfer_data['source_location_id'],
            destination_location_id=transfer_data['destination_location_id'],
            sneaker_reference_code=transfer_data['sneaker_reference_code'],
            brand=transfer_data['brand'],
            model=transfer_data['model'],
            size=transfer_data['size'],
            quantity=transfer_data['quantity'],
            purpose=transfer_data['purpose'],
            pickup_type=transfer_data['pickup_type'],
            destination_type=transfer_data.get('destination_type', 'bodega'),
            notes=transfer_data.get('notes'),
            inventory_type=transfer_data.get('inventory_type', 'pair'),
            status='pending',
            requested_at=datetime.now()
        )
        
        self.db.add(transfer)
        self.db.commit()
        self.db.refresh(transfer)
        return transfer
    
    def get_transfer_requests_by_user(self, user_id: int, company_id: int) -> List[Dict[str, Any]]:
        """Obtener solicitudes de transferencia por usuario - igual que backend antiguo"""
        # Query compleja como en el backend standalone
        query = text("""
            SELECT tr.*, 
                   sl.name as source_location_name,
                   dl.name as destination_location_name,
                   c.first_name as courier_first_name, c.last_name as courier_last_name,
                   wk.first_name as warehouse_keeper_first_name, wk.last_name as warehouse_keeper_last_name,
                   CASE 
                       WHEN tr.request_type = 'return' THEN 'Devolución'
                       ELSE 'Transferencia'
                   END as request_display_type,
                   CASE 
                       WHEN tr.request_type = 'return' THEN 'Devolviendo a origen'
                       ELSE 'Enviando a destino'
                   END as workflow_description,
                   orig.id as original_transfer_info,
                   orig.requested_at as original_transfer_date
            FROM transfer_requests tr
            JOIN locations sl ON tr.source_location_id = sl.id
            JOIN locations dl ON tr.destination_location_id = dl.id
            LEFT JOIN users c ON tr.courier_id = c.id
            LEFT JOIN users wk ON tr.warehouse_keeper_id = wk.id
            LEFT JOIN transfer_requests orig ON tr.original_transfer_id = orig.id
            WHERE tr.requester_id = :user_id AND tr.company_id = :company_id
            ORDER BY tr.requested_at DESC
        """)
        
        results = self.db.execute(query, {"user_id": user_id, "company_id": company_id}).fetchall()
        
        transfers = []
        for row in results:
            # Calcular tiempo transcurrido
            requested_at = row.requested_at
            if isinstance(requested_at, str):
                requested_at = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))
            
            time_diff = datetime.now() - requested_at
            hours = int(time_diff.total_seconds() // 3600)
            minutes = int((time_diff.total_seconds() % 3600) // 60)
            time_elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            # Información de estado
            status_info = self._get_transfer_status_info(row.status, row.purpose)
            
            # Determinar prioridad
            priority = 'high' if row.purpose == 'cliente' else 'normal'
            
            transfers.append({
                'id': row.id,
                'status': row.status,
                'sneaker_reference_code': row.sneaker_reference_code,
                'brand': row.brand,
                'model': row.model,
                'size': row.size,
                'quantity': row.quantity,
                'purpose': row.purpose,
                'pickup_type': row.pickup_type,
                'destination_type': row.destination_type or 'bodega',
                'requested_at': requested_at.isoformat(),
                'time_elapsed': time_elapsed,
                'priority': priority,
                'status_info': status_info,
                'location_info': {
                    'from': {
                        'name': row.source_location_name,
                        'address': 'Dirección no disponible'
                    },
                    'to': {
                        'name': row.destination_location_name
                    }
                },
                'participants': {
                    'courier_name': f"{row.courier_first_name} {row.courier_last_name}" if row.courier_first_name else None,
                    'warehouse_keeper_name': f"{row.warehouse_keeper_first_name} {row.warehouse_keeper_last_name}" if row.warehouse_keeper_first_name else None
                },
                'notes': row.notes,
                'is_self_pickup': row.pickup_type == 'vendedor',
                'request_display_type': row.request_display_type,
                'workflow_description': row.workflow_description
            })
        
        return transfers
    
    def _get_transfer_status_info(self, status: str, purpose: str) -> Dict[str, Any]:
        """Obtener información detallada del estado"""
        status_mapping = {
            'pending': {
                'title': 'Solicitud Pendiente',
                'description': 'Esperando que bodeguero acepte la solicitud',
                'detail': 'Tu solicitud está en cola para ser procesada',
                'action_required': 'Esperar confirmación del bodeguero',
                'next_step': 'El bodeguero revisará disponibilidad',
                'urgency': 'high' if purpose == 'cliente' else 'normal',
                'progress_percentage': 10
            },
            'accepted': {
                'title': 'Solicitud Aceptada',
                'description': 'Bodeguero confirmó disponibilidad y está preparando el producto',
                'detail': 'El producto está siendo preparado para envío',
                'action_required': 'Esperar que corredor recoja',
                'next_step': 'Asignación de corredor',
                'urgency': 'medium',
                'progress_percentage': 30
            },
            'in_transit': {
                'title': 'En Tránsito',
                'description': 'Corredor tiene el producto y está en camino',
                'detail': 'El producto está siendo transportado a tu ubicación',
                'action_required': 'Esperar entrega del corredor',
                'next_step': 'Corredor entregará el producto',
                'urgency': 'medium',
                'progress_percentage': 70
            },
            'delivered': {
                'title': 'Producto Entregado',
                'description': 'Corredor entregó el producto',
                'detail': 'Confirma que recibiste el producto en buenas condiciones',
                'action_required': 'Confirmar recepción',
                'next_step': 'Confirmar recepción del producto',
                'urgency': 'high',
                'progress_percentage': 90
            },
            'completed': {
                'title': 'Transferencia Completada',
                'description': 'Proceso completado exitosamente',
                'detail': 'El inventario fue actualizado automáticamente',
                'action_required': None,
                'next_step': 'Transferencia finalizada',
                'urgency': 'normal',
                'progress_percentage': 100
            },
            'cancelled': {
                'title': 'Transferencia Cancelada',
                'description': 'La solicitud fue cancelada',
                'detail': 'La transferencia no se completó',
                'action_required': None,
                'next_step': 'Puede solicitar nuevamente si es necesario',
                'urgency': 'normal',
                'progress_percentage': 0
            }
        }
        
        return status_mapping.get(status, {
            'title': 'Estado Desconocido',
            'description': 'Estado no reconocido',
            'detail': f'Estado actual: {status}',
            'urgency': 'normal',
            'progress_percentage': 0
        })
    
    def get_transfer_summary(self, user_id: int, company_id: int) -> Dict[str, Any]:
        """Obtener resumen de transferencias del usuario"""
        transfers = self.get_transfer_requests_by_user(user_id, company_id)
        
        summary = {
            "total_requests": len(transfers),
            "transfers": len([t for t in transfers if t.get('request_display_type') == 'Transferencia']),
            "returns": len([t for t in transfers if t.get('request_display_type') == 'Devolución']),
            "pending": len([t for t in transfers if t['status'] == 'pending']),
            "in_progress": len([t for t in transfers if t['status'] in ['accepted', 'in_transit']]),
            "completed": len([t for t in transfers if t['status'] in ['delivered', 'completed']]),
            "cancelled": len([t for t in transfers if t['status'] == 'cancelled']),
            "awaiting_confirmation": len([t for t in transfers if t['status'] == 'delivered'])
        }
        
        return summary
    
    
    def confirm_reception(
        self, 
        transfer_id: int, 
        received_quantity: int, 
        condition_ok: bool, 
        notes: str, 
        user_id: int,
        company_id: int
    ) -> bool:
        """Confirmar recepción de transferencia con actualización de inventario"""
        try:
            logger.info(f"📝 Repository: Confirmando recepción #{transfer_id}")
            
            # Obtener transferencia
            transfer = self.db.query(TransferRequest).filter(
                TransferRequest.id == transfer_id,
                TransferRequest.company_id == company_id
            ).first()
            
            if not transfer:
                logger.warning(f"❌ Transferencia {transfer_id} no encontrada")
                return False
            
            logger.info(f"✅ Transferencia encontrada: {transfer.sneaker_reference_code}")
            
            # ✅ OBTENER NOMBRE REAL DE UBICACIÓN DESTINO + MULTI-TENANT
            destination_location = self.db.query(Location).filter(
                Location.id == transfer.destination_location_id,
                Location.company_id == company_id  # ✅ MULTI-TENANT
            ).first()
            
            if not destination_location:
                logger.error(f"❌ Ubicación destino no encontrada: ID {transfer.destination_location_id}")
                return False
            
            destination_location_name = destination_location.name
            logger.info(f"✅ Ubicación destino: '{destination_location_name}'")
            
            # Actualizar estado de transferencia
            transfer.status = 'completed'
            transfer.confirmed_reception_at = datetime.now()
            transfer.received_quantity = received_quantity
            transfer.reception_notes = notes
            
            logger.info(f"✅ Estado actualizado a 'completed'")
            
            # Actualizar inventario si condición OK
            if condition_ok:
                logger.info(f"🔄 Actualizando inventario en '{destination_location_name}'")
                
                # Buscar producto GLOBAL (sin location_name si ya corregiste el modelo)
                product = self.db.query(Product).filter(
                    Product.reference_code == transfer.sneaker_reference_code,
                    Product.company_id == company_id
                ).first()
                
                # Si no existe producto global, buscar por location (compatible con BD actual)
                if not product:
                    logger.info(f"   Buscando producto con location_name (BD actual)")
                    product = self.db.query(Product).filter(
                        and_(
                            Product.reference_code == transfer.sneaker_reference_code,
                            Product.location_name == destination_location_name,
                            Product.company_id == company_id
                        )
                    ).first()
                
                if not product:
                    logger.warning(
                        f"⚠️ Producto {transfer.sneaker_reference_code} no existe, "
                        f"se creará en '{destination_location_name}'"
                    )
                    # Crear producto (compatible con BD actual que tiene location_name)
                    product = Product(
                        reference_code=transfer.sneaker_reference_code,
                        brand=transfer.brand,
                        model=transfer.model,
                        description=f"{transfer.brand} {transfer.model}",
                        location_name=destination_location_name,  # Por ahora, hasta migración
                        unit_price=0,
                        box_price=0,
                        is_active=1,
                        created_at=datetime.now(),
                        company_id=company_id

                    )
                    self.db.add(product)
                    self.db.flush()
                    logger.info(f"✅ Producto creado: ID {product.id}")
                
                # Buscar product_size destino
                product_size = self.db.query(ProductSize).filter(
                    and_(
                        ProductSize.product_id == product.id,
                        ProductSize.size == transfer.size,
                        ProductSize.location_name == destination_location_name ,
                        ProductSize.company_id == company_id  
                    )
                ).first()
                
                quantity_before = 0
                
                if product_size:
                    # CASO A: Ya existe esta talla en esta ubicación
                    quantity_before = product_size.quantity
                    product_size.quantity += received_quantity
                    logger.info(
                        f"✅ Stock actualizado en '{destination_location_name}': "
                        f"{quantity_before} → {product_size.quantity}"
                    )
                else:
                    # CASO B: Primera vez que llega esta talla a esta ubicación
                    product_size = ProductSize(
                        product_id=product.id,
                        size=transfer.size,
                        quantity=received_quantity,
                        quantity_exhibition=0,
                        location_name=destination_location_name,  # ✅ NOMBRE REAL
                        created_at=datetime.now(),
                        updated_at=datetime.now(),
                        company_id=company_id

                    )
                    self.db.add(product_size)
                    logger.info(
                        f"✅ Nuevo product_size creado en '{destination_location_name}': "
                        f"qty={received_quantity}"
                    )
                
                quantity_after = product_size.quantity if product_size else received_quantity
                
                # Registrar cambio en historial
                inventory_change = InventoryChange(
                    product_id=product.id,
                    change_type='transfer_reception',
                    size=transfer.size,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    user_id=user_id,
                    reference_id=transfer_id,
                    notes=f"Recepción de transferencia #{transfer_id} en '{destination_location_name}' - {notes}",
                    created_at=datetime.now(),
                    company_id=company_id

                )
                self.db.add(inventory_change)
                
                logger.info(f"✅ Cambio registrado en inventory_changes")
            else:
                logger.warning(f"⚠️ Condición no OK - inventario NO actualizado")
            
            self.db.commit()
            logger.info(f"✅ Commit exitoso - Recepción completada")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.exception(f"❌ Error en confirm_reception")
            return False

    # AGREGAR AL FINAL DE app/modules/transfers_new/repository.py

    def get_returns_by_vendor(self, vendor_id: int, company_id: int) -> List[Dict[str, Any]]:
        """Obtener devoluciones del vendedor"""
        try:
            returns = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.requester_id == vendor_id,
                    TransferRequest.company_id == company_id,
                    TransferRequest.request_type == 'return',
                    TransferRequest.original_transfer_id.isnot(None)
                )
            ).order_by(desc(TransferRequest.requested_at)).all()
            
            result = []
            for ret in returns:
                # Tiempo transcurrido
                time_diff = datetime.now() - ret.requested_at
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                time_elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Información de estado
                status_info = self._get_return_status_info(ret.status)
                pickup_method_display = "🚚 Corredor" if ret.pickup_type == 'corredor' else "🚶 Tú mismo"
                
                result.append({
                    'id': ret.id,
                    'return_type': 'return',
                    'original_transfer_id': ret.original_transfer_id,
                    'status': ret.status,
                    'status_info': status_info,
                    'sneaker_reference_code': ret.sneaker_reference_code,
                    'brand': ret.brand,
                    'model': ret.model,
                    'size': ret.size,
                    'quantity': ret.quantity,
                    'reason': self._extract_reason_from_notes(ret.notes),
                    'requested_at': ret.requested_at.isoformat(),
                    'time_elapsed': time_elapsed,
                    'pickup_type': ret.pickup_type,
                    'source_location': ret.source_location.name if ret.source_location else None,
                    'destination_location': ret.destination_location.name if ret.destination_location else None,
                    'courier_name': f"{ret.courier.first_name} {ret.courier.last_name}" if ret.courier else None,
                    'notes': ret.notes
                })
            
            return result
            
        except Exception as e:
            logger.exception("Error obteniendo returns")
            return []
    
    def _get_return_status_info(self, status: str) -> Dict[str, Any]:
        """Info de estado específica para returns"""
        status_map = {
            'pending': {
                'title': 'Devolución Pendiente',
                'description': 'Esperando que bodeguero acepte la devolución',
                'progress': 10
            },
            'accepted': {
                'title': 'Devolución Aceptada',
                'description': 'Bodega aceptó la devolución, esperando corredor',
                'progress': 30
            },
            'courier_assigned': {
                'title': 'Corredor Asignado',
                'description': 'Corredor en camino a recoger el producto',
                'progress': 50
            },
            'in_transit': {
                'title': 'En Tránsito a Bodega',
                'description': 'Corredor transportando producto de regreso',
                'progress': 70
            },
            'delivered': {
                'title': 'Entregado en Bodega',
                'description': 'Esperando confirmación de bodeguero',
                'progress': 90
            },
            'completed': {
                'title': 'Devolución Completada',
                'description': 'Inventario restaurado en bodega',
                'progress': 100
            }
        }
        
        return status_map.get(status, {
            'title': 'Estado Desconocido',
            'description': status,
            'progress': 0
        })
    
    def _extract_reason_from_notes(self, notes: Optional[str]) -> str:
        """Extraer razón de las notas"""
        if not notes:
            return "No especificado"
        
        # Buscar "Razón: X" en las notas
        if "Razón:" in notes:
            lines = notes.split('\n')
            for line in lines:
                if line.startswith("Razón:"):
                    return line.replace("Razón:", "").strip()
        
        return "No especificado"    

    def validate_single_foot_availability(
        self,
        product_id: int,
        size: str,
        inventory_type: Literal['left_only', 'right_only'],
        location_name: str,
        quantity: int,
        company_id: int
    ) -> Dict[str, Any]:
        """
        Validar que hay suficientes pies del tipo solicitado
        
        Returns:
            {
                "available": bool,
                "current_stock": int,
                "requested": int,
                "can_fulfill": bool
            }
        """
        
        product_size = self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product_id,
                ProductSize.size == size,
                ProductSize.location_name == location_name,
                ProductSize.inventory_type == inventory_type,
                ProductSize.company_id == company_id
            )
        ).first()
        
        current_stock = product_size.quantity if product_size else 0
        can_fulfill = current_stock >= quantity
        
        return {
            "available": product_size is not None,
            "current_stock": current_stock,
            "requested": quantity,
            "can_fulfill": can_fulfill
        }
    
    
    # ========== BUSCAR PIE OPUESTO EN DESTINO ==========
    def find_opposite_foot_in_location(
        self,
        reference_code: str,
        size: str,
        location_id: int,
        received_inventory_type: str,
        company_id: int
    ) -> Optional[Dict[str, Any]]:  # ✅ Cambiar a Dict en lugar de OppositeFootInfo
        """
        Buscar si existe el pie opuesto en la ubicación destino
        
        Returns:
            Dict con información del pie opuesto o None si no existe
        """
        
        # Determinar qué pie buscar
        opposite_type = 'right_only' if received_inventory_type == 'left_only' else 'left_only'
        
        # Buscar producto
        product = self.db.query(Product).filter(
            and_(
                Product.reference_code == reference_code,
                Product.company_id == company_id
            )
        ).first()
        
        if not product:
            return None
        
        # Buscar ubicación
        location = self.db.query(Location).filter(
            and_(
                Location.id == location_id,
                Location.company_id == company_id
            )
        ).first()
        
        if not location:
            return None
        
        # Buscar ProductSize del pie opuesto
        opposite_foot = self.db.query(ProductSize).filter(
            and_(
                ProductSize.product_id == product.id,
                ProductSize.size == size,
                ProductSize.location_name == location.name,
                ProductSize.inventory_type == opposite_type,
                ProductSize.quantity > 0,
                ProductSize.company_id == company_id
            )
        ).first()
        
        if not opposite_foot:
            return None
        
        # ✅ RETORNAR COMO DICCIONARIO (no como OppositeFootInfo)
        return {
            "exists": True,
            "product_size_id": opposite_foot.id,
            "inventory_type": opposite_foot.inventory_type,
            "quantity": opposite_foot.quantity,
            "location_name": location.name,
            "can_form_pairs": True
        }
    
    
    # ========== BUSCAR TRANSFERENCIA PENDIENTE DEL PIE OPUESTO ==========
    def find_pending_opposite_transfer(
        self,
        reference_code: str,
        size: str,
        destination_location_id: int,
        received_inventory_type: Literal['left_only', 'right_only'],
        company_id: int
    ) -> Optional[TransferRequest]:
        """
        Buscar si hay una transferencia pendiente del pie opuesto
        hacia la misma ubicación
        
        Útil para:
        - Detectar que llegó el primer pie de un par
        - Auto-formar cuando llegue el segundo
        """
        
        opposite_type = 'right_only' if received_inventory_type == 'left_only' else 'left_only'
        
        return self.db.query(TransferRequest).filter(
            and_(
                TransferRequest.sneaker_reference_code == reference_code,
                TransferRequest.size == size,
                TransferRequest.destination_location_id == destination_location_id,
                TransferRequest.inventory_type == opposite_type,
                TransferRequest.status.in_(['pending', 'accepted', 'in_transit']),
                TransferRequest.company_id == company_id
            )
        ).first()

    def link_formed_pair_transfers(
        self,
        left_transfer_id: int,
        right_transfer_id: int
    ) -> None:
        """
        Vincular dos transferencias que formaron un par
        """
        left_transfer = self.db.query(TransferRequest).filter(
            TransferRequest.id == left_transfer_id
        ).first()
        
        right_transfer = self.db.query(TransferRequest).filter(
            TransferRequest.id == right_transfer_id
        ).first()
        
        if left_transfer and right_transfer:
            left_transfer.auto_formed_pair_id = right_transfer_id
            right_transfer.auto_formed_pair_id = left_transfer_id
            self.db.commit()
            
            logger.info(f"✅ Transfers {left_transfer_id} y {right_transfer_id} vinculados como par formado")


    def validate_return_availability(
        self,
        product_id: int,
        size: str,
        inventory_type: str,  # 'pair', 'left_only', 'right_only'
        location_name: str,
        quantity_requested: int,
        company_id: int
    ) -> Dict[str, Any]:
        """
        🆕 Validar disponibilidad para devolución considerando:
        1. Pies sueltos del tipo solicitado
        2. Pares disponibles que se pueden partir
        
        Este método calcula la estrategia óptima para cumplir con la
        devolución solicitada, priorizando usar pies sueltos antes de
        partir pares.
        
        Args:
            product_id: ID del producto
            size: Talla del producto
            inventory_type: Tipo de inventario ('pair', 'left_only', 'right_only')
            location_name: Nombre de la ubicación (local del vendedor)
            quantity_requested: Cantidad que se desea devolver
            company_id: ID de la compañía
        
        Returns:
            Dict con información de disponibilidad y estrategia:
            - can_fulfill: bool
            - loose_feet_available: int (solo para pies individuales)
            - pairs_available: int
            - total_feet_available: int (solo para pies individuales)
            - requires_split: bool
            - loose_feet_to_use: int (solo para pies individuales)
            - pairs_to_split: int (solo para pies individuales)
            - remaining_opposite_feet: int (solo para pies individuales)
            - error: str (si can_fulfill es False)
        """
        
        try:
            if inventory_type == 'pair':
                # ========== CASO 1: DEVOLUCIÓN DE PARES COMPLETOS ==========
                logger.info(f"🔍 Validando devolución de {quantity_requested} par(es)")
                
                pair_stock = self.db.query(ProductSize).filter(
                    and_(
                        ProductSize.product_id == product_id,
                        ProductSize.size == size,
                        ProductSize.location_name == location_name,
                        ProductSize.inventory_type == 'pair',
                        ProductSize.company_id == company_id
                    )
                ).first()
                
                available = pair_stock.quantity if pair_stock else 0
                can_fulfill = available >= quantity_requested
                
                if not can_fulfill:
                    logger.warning(
                        f"❌ Stock insuficiente de pares: "
                        f"Disponible: {available}, Solicitado: {quantity_requested}"
                    )
                    return {
                        "can_fulfill": False,
                        "pairs_available": available,
                        "requires_split": False,
                        "error": (
                            f"Stock insuficiente de pares. "
                            f"Disponible: {available}, Solicitado: {quantity_requested}"
                        )
                    }
                
                logger.info(f"✅ Stock suficiente de pares: {available}")
                return {
                    "can_fulfill": True,
                    "pairs_available": available,
                    "requires_split": False
                }
            
            else:
                # ========== CASO 2: DEVOLUCIÓN DE PIE INDIVIDUAL ==========
                foot_type_name = "izquierdo" if inventory_type == 'left_only' else "derecho"
                logger.info(
                    f"🔍 Validando devolución de {quantity_requested} pie(s) {foot_type_name}"
                )
                
                # 2.1 Buscar pies sueltos del tipo solicitado
                loose_foot_stock = self.db.query(ProductSize).filter(
                    and_(
                        ProductSize.product_id == product_id,
                        ProductSize.size == size,
                        ProductSize.location_name == location_name,
                        ProductSize.inventory_type == inventory_type,
                        ProductSize.company_id == company_id
                    )
                ).first()
                
                loose_feet = loose_foot_stock.quantity if loose_foot_stock else 0
                logger.info(f"   📦 Pies {foot_type_name} sueltos: {loose_feet}")
                
                # 2.2 Buscar pares disponibles (cada par contiene 1 pie del tipo solicitado)
                pair_stock = self.db.query(ProductSize).filter(
                    and_(
                        ProductSize.product_id == product_id,
                        ProductSize.size == size,
                        ProductSize.location_name == location_name,
                        ProductSize.inventory_type == 'pair',
                        ProductSize.company_id == company_id
                    )
                ).first()
                
                pairs_available = pair_stock.quantity if pair_stock else 0
                logger.info(f"   📦 Pares disponibles: {pairs_available}")
                
                # 2.3 Calcular total disponible
                # Total = pies sueltos + pies disponibles dentro de pares
                total_available = loose_feet + pairs_available
                logger.info(
                    f"   📊 Total disponible: {total_available} "
                    f"({loose_feet} sueltos + {pairs_available} en pares)"
                )
                
                # 2.4 Verificar si se puede cumplir
                can_fulfill = total_available >= quantity_requested
                
                if not can_fulfill:
                    logger.warning(
                        f"❌ Stock insuficiente: "
                        f"Disponible: {total_available}, Solicitado: {quantity_requested}"
                    )
                    return {
                        "can_fulfill": False,
                        "loose_feet_available": loose_feet,
                        "pairs_available": pairs_available,
                        "total_feet_available": total_available,
                        "requires_split": False,
                        "error": (
                            f"Stock insuficiente de pies {foot_type_name}. "
                            f"Disponible: {total_available} "
                            f"({loose_feet} sueltos + {pairs_available} en pares), "
                            f"Solicitado: {quantity_requested}"
                        )
                    }
                
                # 2.5 Calcular estrategia de partición
                # Estrategia: usar primero pies sueltos, luego partir pares
                loose_feet_to_use = min(loose_feet, quantity_requested)
                remaining_needed = quantity_requested - loose_feet_to_use
                pairs_to_split = remaining_needed  # 1 par partido = 1 pie del tipo necesario
                requires_split = pairs_to_split > 0
                
                logger.info(f"   📋 Estrategia calculada:")
                logger.info(f"      - Usar {loose_feet_to_use} pie(s) suelto(s)")
                logger.info(f"      - Partir {pairs_to_split} par(es)")
                logger.info(f"      - Quedarán {pairs_to_split} pie(s) opuesto(s)")
                
                return {
                    "can_fulfill": True,
                    "loose_feet_available": loose_feet,
                    "pairs_available": pairs_available,
                    "total_feet_available": total_available,
                    "requires_split": requires_split,
                    "loose_feet_to_use": loose_feet_to_use,
                    "pairs_to_split": pairs_to_split,
                    "remaining_opposite_feet": pairs_to_split
                }
                
        except Exception as e:
            logger.exception(f"❌ Error validando disponibilidad para devolución: {str(e)}")
            raise


    def split_pair_for_return(
        self,
        product_id: int,
        size: str,
        location_name: str,
        inventory_type_needed: str,  # 'left_only' o 'right_only'
        pairs_to_split: int,
        company_id: int,
        user_id: int,
        return_id: int
    ) -> Dict[str, Any]:
        """
        🆕 Partir pares para obtener pies individuales necesarios para devolución
        
        Este método realiza la operación crítica de:
        1. Descontar pares del inventario
        2. Los pies del tipo solicitado se usan para la devolución (no se agregan)
        3. Los pies opuestos se agregan como inventario suelto
        4. Registrar la operación en el historial
        
        IMPORTANTE: Esta operación modifica el inventario y debe ejecutarse
        dentro de una transacción.
        
        Args:
            product_id: ID del producto
            size: Talla
            location_name: Ubicación donde están los pares
            inventory_type_needed: Tipo de pie que se necesita ('left_only' o 'right_only')
            pairs_to_split: Cantidad de pares a partir
            company_id: ID de la compañía
            user_id: ID del usuario que solicita la devolución
            return_id: ID de la devolución (para referencia en historial)
        
        Returns:
            Dict con resultado de la operación:
            - success: bool
            - pairs_split: int
            - opposite_feet_added: int
            - pairs_remaining: int
            - loose_feet_remaining: int
        
        Raises:
            ValueError: Si no hay suficientes pares o datos inválidos
            Exception: Cualquier otro error en la operación
        """
        
        try:
            foot_name = "izquierdo" if inventory_type_needed == 'left_only' else "derecho"
            opposite_foot_name = "derecho" if inventory_type_needed == 'left_only' else "izquierdo"
            
            logger.info(f"🔪 Iniciando partición de {pairs_to_split} par(es)")
            logger.info(f"   Producto ID: {product_id}, Talla: {size}")
            logger.info(f"   Ubicación: {location_name}")
            logger.info(f"   Pie necesario: {foot_name}")
            
            # ========== 1. OBTENER PRODUCTSIZE DE PARES (CON LOCK) ==========
            pair_stock = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product_id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == 'pair',
                    ProductSize.company_id == company_id
                )
            ).with_for_update().first()  # ⚠️ LOCK para evitar race conditions
            
            if not pair_stock:
                raise ValueError(
                    f"No se encontró stock de pares para "
                    f"Producto {product_id}, Talla {size}, Ubicación {location_name}"
                )
            
            if pair_stock.quantity < pairs_to_split:
                raise ValueError(
                    f"Stock insuficiente de pares. "
                    f"Disponible: {pair_stock.quantity}, Necesario: {pairs_to_split}"
                )
            
            # ========== 2. DESCONTAR PARES ==========
            pairs_before = pair_stock.quantity
            pair_stock.quantity -= pairs_to_split
            pair_stock.updated_at = datetime.now()
            
            logger.info(
                f"   ✂️ Pares descontados: {pairs_before} → {pair_stock.quantity} "
                f"(-{pairs_to_split})"
            )
            
            # ========== 3. DETERMINAR TIPO OPUESTO ==========
            opposite_type = 'right_only' if inventory_type_needed == 'left_only' else 'left_only'
            
            # ========== 4. AGREGAR PIES OPUESTOS COMO SUELTOS ==========
            # Los pies del tipo solicitado NO se agregan porque se van en la devolución
            # Solo agregamos los pies opuestos que quedan en inventario
            
            opposite_foot_stock = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product_id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == opposite_type,
                    ProductSize.company_id == company_id
                )
            ).with_for_update().first()
            
            if opposite_foot_stock:
                # Ya existe registro de pies opuestos - incrementar
                opposite_before = opposite_foot_stock.quantity
                opposite_foot_stock.quantity += pairs_to_split
                opposite_foot_stock.updated_at = datetime.now()
                
                logger.info(
                    f"   ➕ Pies {opposite_foot_name} agregados: "
                    f"{opposite_before} → {opposite_foot_stock.quantity} (+{pairs_to_split})"
                )
            else:
                # No existe registro - crear nuevo
                opposite_foot_stock = ProductSize(
                    product_id=product_id,
                    size=size,
                    quantity=pairs_to_split,
                    quantity_exhibition=0,
                    inventory_type=opposite_type,
                    location_name=location_name,
                    company_id=company_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(opposite_foot_stock)
                
                logger.info(
                    f"   ✨ Nuevo registro de pies {opposite_foot_name} creado: {pairs_to_split}"
                )
            
            # ========== 5. OBTENER CANTIDAD DE PIES SUELTOS DEL TIPO NECESARIO ==========
            # (Para información en la respuesta)
            needed_foot_stock = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product_id,
                    ProductSize.size == size,
                    ProductSize.location_name == location_name,
                    ProductSize.inventory_type == inventory_type_needed,
                    ProductSize.company_id == company_id
                )
            ).first()
            
            loose_feet_remaining = needed_foot_stock.quantity if needed_foot_stock else 0
            
            # ========== 6. REGISTRAR EN HISTORIAL ==========
            inventory_change = InventoryChange(
                product_id=product_id,
                change_type='pair_split_for_return',
                size=size,
                quantity_before=pairs_before,
                quantity_after=pair_stock.quantity,
                user_id=user_id,
                reference_id=return_id,
                notes=(
                    f"Partición para devolución: {pairs_to_split} par(es) partido(s). "
                    f"Resultado: {pairs_to_split} pie(s) {foot_name} (para devolución) + "
                    f"{pairs_to_split} pie(s) {opposite_foot_name} (quedan en inventario). "
                    f"Ubicación: {location_name}"
                ),
                created_at=datetime.now(),
                company_id=company_id
            )
            self.db.add(inventory_change)
            
            logger.info(f"   📝 Cambio registrado en historial")
            
            # ========== 7. COMMIT ==========
            self.db.commit()
            
            logger.info(f"   ✅ Partición completada exitosamente")
            
            # ========== 8. RETORNAR RESULTADO ==========
            return {
                "success": True,
                "pairs_split": pairs_to_split,
                "opposite_feet_added": pairs_to_split,
                "pairs_remaining": pair_stock.quantity,
                "loose_feet_remaining": loose_feet_remaining,
                "opposite_foot_stock": opposite_foot_stock.quantity
            }
            
        except ValueError as ve:
            # Errores de validación - no hacer rollback
            logger.error(f"❌ Error de validación: {str(ve)}")
            raise
            
        except Exception as e:
            # Errores inesperados - hacer rollback
            self.db.rollback()
            logger.exception(f"❌ Error crítico partiendo pares: {str(e)}")
            raise Exception(f"Error partiendo pares: {str(e)}")