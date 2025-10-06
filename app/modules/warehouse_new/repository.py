# app/modules/warehouse_new/repository.py - VERSIÓN COMPLETA

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, desc, func ,case
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime, date
import logging

from app.shared.database.models import (
    TransferRequest, User, Location, Product, ProductSize, 
    InventoryChange, UserLocationAssignment
)

logger = logging.getLogger(__name__)

class WarehouseRepository:
    """Repository para operaciones de bodega"""
    
    def __init__(self, db: Session):
        """Constructor del repository"""
        self.db = db
        logger.info("✅ WarehouseRepository inicializado")
    
    def get_pending_requests_for_warehouse(self, warehouse_keeper_id: int) -> List[Dict[str, Any]]:
        """
        BG001: Obtener solicitudes pendientes para bodeguero
        
        Retorna transferencias en estado 'pending' para ubicaciones
        que el bodeguero puede gestionar. 
        
        *Ajustado para que las devoluciones (return) muestren las solicitudes
        cuya ubicación de destino es gestionada por el bodeguero.*
        """
        try:
            logger.info(f"📋 Buscando solicitudes pendientes para bodeguero {warehouse_keeper_id}")
            
            # Obtener ubicaciones que este bodeguero puede gestionar
            managed_locations = self.get_user_managed_locations(warehouse_keeper_id)
            location_ids = [loc['location_id'] for loc in managed_locations]
            
            if not location_ids:
                logger.warning(f"⚠️ Bodeguero {warehouse_keeper_id} no tiene ubicaciones asignadas")
                return []
            
            logger.info(f"✅ Ubicaciones gestionadas: {location_ids}")
            
            # Query compleja para obtener todas las solicitudes pendientes
            query = text("""
                SELECT 
                    tr.*,
                    sl.name as source_location_name,
                    sl.address as source_address,
                    dl.name as destination_location_name,
                    dl.address as destination_address,
                    r.first_name as requester_first_name,
                    r.last_name as requester_last_name,
                    r.email as requester_email,
                    p.image_url as product_image,
                    p.unit_price,
                    p.box_price,
                    ps.quantity as stock_available,
                    CASE 
                        WHEN tr.original_transfer_id IS NOT NULL THEN 'return'
                        ELSE 'transfer'
                    END as request_type,
                    CASE 
                        WHEN tr.original_transfer_id IS NOT NULL THEN 'DEVOLUCIÓN'
                        ELSE 'TRANSFERENCIA'
                    END as request_display_type
                FROM transfer_requests tr
                JOIN locations sl ON tr.source_location_id = sl.id
                JOIN locations dl ON tr.destination_location_id = dl.id
                JOIN users r ON tr.requester_id = r.id
                LEFT JOIN products p ON tr.sneaker_reference_code = p.reference_code
                LEFT JOIN product_sizes ps ON (
                    ps.product_id = p.id 
                    AND ps.size = tr.size 
                    AND ps.location_name = sl.name
                )
                WHERE tr.status = 'pending'
                AND (
                    -- Lógica para TRANSFERENCIAS (el bodeguero gestiona la ubicación de ORIGEN)
                    (tr.original_transfer_id IS NULL AND tr.source_location_id = ANY(:location_ids))
                    -- Lógica para DEVOLUCIONES (el bodeguero gestiona la ubicación de DESTINO)
                    OR (tr.original_transfer_id IS NOT NULL AND tr.destination_location_id = ANY(:location_ids))
                )
                ORDER BY 
                    CASE WHEN tr.purpose = 'cliente' THEN 1 ELSE 2 END,
                    tr.requested_at ASC
            """)
            
            results = self.db.execute(query, {"location_ids": location_ids}).fetchall()
            
            logger.info(f"✅ {len(results)} solicitudes pendientes encontradas")
            
            # Procesar resultados (El resto del código se mantiene igual ya que el cambio es solo en la consulta)
            requests = []
            for row in results:
                # Calcular tiempo transcurrido
                requested_at = row.requested_at
                if isinstance(requested_at, str):
                    requested_at = datetime.fromisoformat(requested_at.replace('Z', '+00:00'))
                
                time_diff = datetime.now() - requested_at
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                time_elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Determinar si requiere acción urgente
                urgent_action = row.purpose == 'cliente' or hours >= 2
                
                # Determinar nivel de prioridad
                if row.purpose == 'cliente':
                    priority_level = 'URGENT'
                elif hours >= 2:
                    priority_level = 'HIGH'
                elif hours >= 1:
                    priority_level = 'MEDIUM'
                else:
                    priority_level = 'NORMAL'
                
                # Imagen del producto
                product_image = row.product_image
                if not product_image:
                    product_image = f"https://via.placeholder.com/300x200?text={row.brand}+{row.model}"
                
                requests.append({
                    'id': row.id,
                    'status': row.status,
                    'request_type': row.request_type,
                    'request_display_type': row.request_display_type,
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
                    'urgent_action': urgent_action,
                    'priority_level': priority_level,
                    'product_info': {
                        'image': product_image,
                        'unit_price': float(row.unit_price) if row.unit_price else 0,
                        'box_price': float(row.box_price) if row.box_price else 0,
                        'stock_available': row.stock_available or 0,
                        'description': f"{row.brand} {row.model} - Talla {row.size}"
                    },
                    'requester_info': {
                        'name': f"{row.requester_first_name} {row.requester_last_name}",
                        'email': row.requester_email
                    },
                    'location_info': {
                        'from': {
                            'id': row.source_location_id,
                            'name': row.source_location_name,
                            'address': row.source_address or 'No especificada'
                        },
                        'to': {
                            'id': row.destination_location_id,
                            'name': row.destination_location_name,
                            'address': row.destination_address or 'No especificada'
                        }
                    },
                    'notes': row.notes
                })
            
            return requests
            
        except Exception as e:
            logger.exception("❌ Error obteniendo solicitudes pendientes")
            return []
    
    def get_user_managed_locations(self, user_id: int) -> List[Dict[str, Any]]:
        """Obtener ubicaciones que un bodeguero puede gestionar"""
        try:
            # Obtener asignaciones de ubicaciones
            assignments = self.db.query(UserLocationAssignment).filter(
                and_(
                    UserLocationAssignment.user_id == user_id,
                    UserLocationAssignment.is_active == True
                )
            ).all()
            
            if not assignments:
                # Si no tiene asignaciones, usar su location_id principal
                user = self.db.query(User).filter(User.id == user_id).first()
                if user and user.location_id:
                    return [{'location_id': user.location_id}]
                return []
            
            return [{'location_id': assignment.location_id} for assignment in assignments]
            
        except Exception as e:
            logger.exception("❌ Error obteniendo ubicaciones gestionadas")
            return []
    
    def accept_transfer_request(
        self, 
        request_id: int, 
        acceptance_data: Dict[str, Any], 
        warehouse_keeper_id: int
    ) -> bool:
        """BG002: Aceptar o rechazar solicitud de transferencia"""
        try:
            logger.info(f"✅ Aceptando solicitud {request_id}")
            
            transfer = self.db.query(TransferRequest).filter(
                TransferRequest.id == request_id
            ).first()
            
            if not transfer:
                logger.warning(f"❌ Transferencia {request_id} no encontrada")
                return False
            
            if transfer.status != 'pending':
                logger.warning(f"❌ Estado inválido: {transfer.status}")
                return False
            
            if acceptance_data['accepted']:
                # ACEPTAR
                transfer.status = 'accepted'
                transfer.warehouse_keeper_id = warehouse_keeper_id
                transfer.accepted_at = datetime.now()
                transfer.notes = acceptance_data.get('warehouse_notes', '')
                logger.info(f"✅ Solicitud aceptada por bodeguero {warehouse_keeper_id}")
            else:
                # RECHAZAR
                transfer.status = 'rejected'
                transfer.warehouse_keeper_id = warehouse_keeper_id
                transfer.notes = f"Rechazado: {acceptance_data.get('rejection_reason', 'No especificado')}"
                logger.info(f"❌ Solicitud rechazada: {acceptance_data.get('rejection_reason')}")
            
            self.db.commit()
            return True
            
        except Exception as e:
            logger.exception("❌ Error aceptando solicitud")
            self.db.rollback()
            return False
    
   # app/modules/warehouse_new/repository.py - VERSIÓN MEJORADA

    def get_accepted_requests_by_warehouse_keeper(self, warehouse_keeper_id: int) -> List[Dict[str, Any]]:
        """
        Obtener solicitudes aceptadas por este bodeguero
        
        Incluye:
        - Imagen del producto
        - Tipo de recogida (vendedor o corredor)
        - Tipo de transferencia (transfer o return)
        - Información completa de participantes
        - Estado detallado con siguiente acción
        """
        try:
            logger.info(f"Obteniendo solicitudes aceptadas para bodeguero {warehouse_keeper_id}")
            
            active_statuses = ['accepted', 'courier_assigned']
            
            transfers = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.warehouse_keeper_id == warehouse_keeper_id,
                    TransferRequest.status.in_(active_statuses)
                )
            ).order_by(
                # ✅ SINTAXIS CORRECTA con case()
                case(
                    (TransferRequest.purpose == 'cliente', 1),
                    else_=2
                ),
                case(
                    (TransferRequest.status == 'courier_assigned', 1),
                    (TransferRequest.status == 'accepted', 2),
                    else_=3
                ),
                TransferRequest.accepted_at.asc()
            ).all()
            
            results = []
            for transfer in transfers:
                # Calcular tiempo desde aceptación
                time_diff = datetime.now() - transfer.accepted_at if transfer.accepted_at else timedelta(0)
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                time_since_accepted = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Obtener imagen del producto
                product_image = self._get_product_image(
                    transfer.sneaker_reference_code,
                    transfer.source_location_id
                )
                
                # Determinar tipo de transferencia
                transfer_type = 'return' if transfer.original_transfer_id else 'transfer'
                transfer_type_display = 'DEVOLUCIÓN' if transfer_type == 'return' else 'TRANSFERENCIA'
                
                # Determinar quién recoge
                pickup_info = self._get_pickup_info(transfer)
                
                # Estado y siguiente acción
                status_info = self._get_warehouse_status_info(transfer.status, transfer.pickup_type)
                
                # Información de ubicaciones
                source_location = self.db.query(Location).filter(
                    Location.id == transfer.source_location_id
                ).first()
                
                destination_location = self.db.query(Location).filter(
                    Location.id == transfer.destination_location_id
                ).first()
                
                results.append({
                    'id': transfer.id,
                    'status': transfer.status,
                    'status_info': status_info,
                    
                    # Información del producto
                    'sneaker_reference_code': transfer.sneaker_reference_code,
                    'brand': transfer.brand,
                    'model': transfer.model,
                    'size': transfer.size,
                    'quantity': transfer.quantity,
                    'product_image': product_image,
                    'product_description': f"{transfer.brand} {transfer.model} - Talla {transfer.size}",
                    
                    # Tipo de transferencia
                    'transfer_type': transfer_type,
                    'transfer_type_display': transfer_type_display,
                    'purpose': transfer.purpose,
                    'priority': 'high' if transfer.purpose == 'cliente' else 'normal',
                    
                    # Información de recogida
                    'pickup_type': transfer.pickup_type,
                    'pickup_info': pickup_info,
                    
                    # Participantes
                    'requester_info': {
                        'id': transfer.requester_id,
                        'name': f"{transfer.requester.first_name} {transfer.requester.last_name}" if transfer.requester else None,
                        'role': transfer.requester.role if transfer.requester else None
                    },
                    'courier_info': {
                        'id': transfer.courier_id,
                        'name': f"{transfer.courier.first_name} {transfer.courier.last_name}" if transfer.courier else None,
                        'assigned': transfer.courier_id is not None
                    } if transfer.pickup_type == 'corredor' else None,
                    
                    # Ubicaciones
                    'location_info': {
                        'source': {
                            'id': transfer.source_location_id,
                            'name': source_location.name if source_location else None
                        },
                        'destination': {
                            'id': transfer.destination_location_id,
                            'name': destination_location.name if destination_location else None
                        }
                    },
                    
                    # Timestamps
                    'requested_at': transfer.requested_at.isoformat() if transfer.requested_at else None,
                    'accepted_at': transfer.accepted_at.isoformat() if transfer.accepted_at else None,
                    'courier_accepted_at': transfer.courier_accepted_at.isoformat() if transfer.courier_accepted_at else None,
                    'picked_up_at': transfer.picked_up_at.isoformat() if transfer.picked_up_at else None,
                    'time_since_accepted': time_since_accepted,
                    
                    # Notas
                    'notes': transfer.notes,
                    'warehouse_notes': transfer.notes
                })
            
            logger.info(f"{len(results)} solicitudes encontradas")
            return results
            
        except Exception as e:
            logger.exception("Error obteniendo solicitudes aceptadas")
            return []

    def _get_pickup_info(self, transfer: TransferRequest) -> Dict[str, Any]:
        """Obtener información detallada de quién recoge"""
        
        if transfer.pickup_type == 'vendedor':
            # El vendedor recoge personalmente
            return {
                'type': 'vendedor',
                'type_display': 'Recoge Vendedor',
                'who': f"{transfer.requester.first_name} {transfer.requester.last_name}" if transfer.requester else 'Vendedor',
                'description': 'El vendedor vendrá a recoger el producto personalmente',
                'icon': '🚶',
                'requires_courier': False
            }
        else:
            # Requiere corredor
            if transfer.courier_id:
                return {
                    'type': 'corredor',
                    'type_display': 'Recoge Corredor',
                    'who': f"{transfer.courier.first_name} {transfer.courier.last_name}",
                    'description': f"Corredor {transfer.courier.first_name} recogerá el producto",
                    'icon': '🚚',
                    'requires_courier': True,
                    'courier_assigned': True,
                    'courier_id': transfer.courier_id
                }
            else:
                return {
                    'type': 'corredor',
                    'type_display': 'Esperando Corredor',
                    'who': 'Pendiente de asignar',
                    'description': 'Esperando que un corredor acepte la solicitud',
                    'icon': '⏳',
                    'requires_courier': True,
                    'courier_assigned': False
                }

    def _get_warehouse_status_info(self, status: str, pickup_type: str) -> Dict[str, Any]:
        """Información detallada del estado para el bodeguero"""
        
        status_map = {
            'accepted': {
                'title': 'Producto Preparado',
                'description': 'Esperando asignación de corredor' if pickup_type == 'corredor' else 'Esperando que vendedor recoja',
                'action_required': 'wait',
                'next_step': 'Corredor aceptará solicitud' if pickup_type == 'corredor' else 'Vendedor vendrá a recoger',
                'progress': 30
            },
            'courier_assigned': {
                'title': 'Corredor Asignado',
                'description': 'Corredor en camino a bodega',
                'action_required': 'prepare',
                'next_step': 'Preparar producto para entrega a corredor',
                'progress': 50
            },
            'in_transit': {
                'title': 'En Tránsito',
                'description': 'Producto entregado a corredor',
                'action_required': 'completed',
                'next_step': 'Inventario descontado - proceso completado para bodega',
                'progress': 80
            }
        }
        
        return status_map.get(status, {
            'title': 'Estado Desconocido',
            'description': status,
            'action_required': 'check',
            'next_step': 'Verificar estado',
            'progress': 0
        })

    def _get_product_image(self, reference_code: str, source_location_id: int) -> str:
        """
        Obtener imagen del producto (reutilizar lógica del vendor repository)
        """
        try:
            source_location = self.db.query(Location).filter(
                Location.id == source_location_id
            ).first()
            
            if not source_location:
                return self._get_placeholder_image(reference_code)
            
            # Buscar producto con imagen
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == reference_code,
                    Product.location_name == source_location.name
                )
            ).first()
            
            # Si no existe o no tiene imagen, buscar global
            if not product or not product.image_url:
                product = self.db.query(Product).filter(
                    Product.reference_code == reference_code
                ).first()
            
            # Retornar imagen o placeholder
            if product and product.image_url:
                return product.image_url
            
            return self._get_placeholder_image(reference_code)
            
        except Exception as e:
            logger.exception(f"Error obteniendo imagen: {e}")
            return self._get_placeholder_image(reference_code)

    def _get_placeholder_image(self, reference_code: str) -> str:
        """Generar placeholder"""
        brand = reference_code.split('-')[0] if '-' in reference_code else 'Product'
        return f"https://via.placeholder.com/300x200?text={brand}+{reference_code}"
    
    def get_inventory_by_location(self, location_id: int) -> List[Dict[str, Any]]:
        """BG006: Consultar inventario por ubicación"""
        try:
            logger.info(f"📊 Obteniendo inventario de ubicación {location_id}")
            
            # Obtener nombre real de ubicación
            location = self.db.query(Location).filter(
                Location.id == location_id
            ).first()
            
            if not location:
                logger.warning(f"❌ Ubicación {location_id} no encontrada")
                return []
            
            location_name = location.name
            logger.info(f"✅ Consultando inventario de '{location_name}'")
            
            # Query de inventario
            inventory = self.db.query(
                Product.reference_code,
                Product.brand,
                Product.model,
                Product.description,
                Product.unit_price,
                Product.box_price,
                Product.image_url,
                ProductSize.size,
                ProductSize.quantity,
                ProductSize.quantity_exhibition
            ).join(ProductSize).filter(
                ProductSize.location_name == location_name
            ).order_by(
                Product.brand, Product.model, ProductSize.size
            ).all()
            
            results = []
            for item in inventory:
                total_value = float(item.unit_price or 0) * item.quantity
                results.append({
                    'reference_code': item.reference_code,
                    'brand': item.brand,
                    'model': item.model,
                    'description': item.description,
                    'size': item.size,
                    'quantity': item.quantity,
                    'quantity_exhibition': item.quantity_exhibition,
                    'unit_price': float(item.unit_price or 0),
                    'box_price': float(item.box_price or 0),
                    'total_value': total_value,
                    'image_url': item.image_url,
                    'status': 'in_stock' if item.quantity > 0 else 'out_of_stock'
                })
            
            logger.info(f"✅ {len(results)} items en inventario")
            return results
            
        except Exception as e:
            logger.exception("❌ Error obteniendo inventario")
            return []
    
    def deliver_to_courier(
        self, 
        request_id: int, 
        delivery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        BG003: Entregar producto a corredor con descuento automático de inventario
        
        VALIDACIONES:
        1. Transferencia existe y está en estado válido
        2. Producto existe en ubicación origen
        3. Stock es suficiente
        4. No hay problemas de concurrencia (locks)
        
        Raises:
            ValueError: Errores de validación de negocio
            RuntimeError: Errores del sistema/base de datos
        """
        
        # ==================== VALIDACIÓN 1: TRANSFERENCIA ====================
        logger.info(f"🔍 Validando transferencia {request_id}")
        
        transfer = self.db.query(TransferRequest).filter(
            TransferRequest.id == request_id
        ).with_for_update().first()  # ← LOCK: Evita procesamiento simultáneo
        
        if not transfer:
            logger.warning(f"❌ Transferencia {request_id} no encontrada")
            raise ValueError(
                f"Transferencia #{request_id} no encontrada en el sistema"
            )
        
        # Validar estado
        if transfer.status != 'courier_assigned':
            logger.warning(
                f"❌ Estado inválido: {transfer.status} (esperado: courier_assigned)"
            )
            raise ValueError(
                f"La transferencia debe estar en estado 'courier_assigned'. "
                f"Estado actual: '{transfer.status}'"
            )
        
        # Validar que tenga corredor asignado
        if not transfer.courier_id:
            logger.warning(f"❌ Sin corredor asignado")
            raise ValueError(
                "No hay corredor asignado a esta transferencia. "
                "Primero debe aceptar un corredor."
            )
        
        # Validar que tenga bodeguero asignado
        if not transfer.warehouse_keeper_id:
            logger.warning(f"❌ Sin bodeguero asignado")
            raise ValueError(
                "No hay bodeguero asignado a esta transferencia."
            )
        
        logger.info(f"✅ Transferencia válida: {transfer.sneaker_reference_code}")
        
        # ==================== VALIDACIÓN 2: UBICACIÓN ORIGEN ====================
        # ✅ OBTENER NOMBRE REAL DE UBICACIÓN
        source_location = self.db.query(Location).filter(
            Location.id == transfer.source_location_id
        ).first()
        
        if not source_location:
            logger.error(f"❌ Ubicación origen no encontrada: ID {transfer.source_location_id}")
            raise ValueError(f"Ubicación origen ID {transfer.source_location_id} no existe")
        
        source_location_name = source_location.name
        logger.info(f"✅ Ubicación origen: '{source_location_name}'")
        
        # ==================== VALIDACIÓN 3: PRODUCTO EXISTE ====================
        logger.info(f"🔍 Buscando producto en inventario")
        
        product_size = self.db.query(ProductSize).join(Product).filter(
            and_(
                Product.reference_code == transfer.sneaker_reference_code,
                ProductSize.size == transfer.size,
                ProductSize.location_name == source_location_name  # ✅ NOMBRE REAL
            )
        ).with_for_update().first()  # ← LOCK: Evita descuento simultáneo
        
        if not product_size:
            logger.error(
                f"❌ Producto no encontrado: {transfer.sneaker_reference_code} "
                f"talla {transfer.size} en '{source_location_name}'"
            )
            raise ValueError(
                f"El producto {transfer.sneaker_reference_code} "
                f"talla {transfer.size} no existe en '{source_location_name}'. "
                f"Verifica que el producto esté correctamente registrado en el inventario."
            )
        
        logger.info(
            f"✅ Producto encontrado: stock actual = {product_size.quantity}"
        )
        
        # ==================== VALIDACIÓN 4: STOCK SUFICIENTE ====================
        logger.info(f"🔍 Validando stock suficiente")
        
        if product_size.quantity < transfer.quantity:
            logger.error(
                f"❌ Stock insuficiente: disponible={product_size.quantity}, "
                f"solicitado={transfer.quantity}"
            )
            raise ValueError(
                f"Stock insuficiente en '{source_location_name}'. "
                f"Solicitado: {transfer.quantity} unidades, "
                f"Disponible: {product_size.quantity} unidades. "
                f"Faltan: {transfer.quantity - product_size.quantity} unidades."
            )
        
        logger.info(f"✅ Stock suficiente para procesar")
        
        # ==================== ACTUALIZACIÓN ATÓMICA ====================
        try:
            # Usar UPDATE con WHERE para validar stock en la misma query
            result = self.db.execute(
                text("""
                    UPDATE product_sizes
                    SET quantity = quantity - :qty
                    WHERE id = :id
                      AND quantity >= :qty
                    RETURNING id, quantity
                """),
                {
                    "id": product_size.id,
                    "qty": transfer.quantity
                }
            )
            
            updated_row = result.fetchone()
            
            if not updated_row:
                logger.error(f"❌ Race condition detectada: stock modificado por otra transacción")
                raise ValueError(
                    "El stock fue modificado por otra operación. "
                    "Por favor, intenta nuevamente."
                )
            
            quantity_before = product_size.quantity
            quantity_after = updated_row[1]
            
            logger.info(
                f"✅ Inventario actualizado: {quantity_before} → {quantity_after}"
            )
            
        except IntegrityError as e:
            logger.error(f"❌ Error de integridad: {e}")
            raise RuntimeError(
                "Error de integridad en la base de datos al actualizar inventario"
            )
        
        # ==================== ACTUALIZAR TRANSFERENCIA ====================
        logger.info(f"📝 Actualizando estado de transferencia")
        
        transfer.status = 'in_transit'
        transfer.picked_up_at = datetime.now()
        transfer.pickup_notes = delivery_data.get('delivery_notes', '')
        
        # ==================== REGISTRAR CAMBIO EN HISTORIAL ====================
        logger.info(f"📋 Registrando cambio en historial")
        
        inventory_change = InventoryChange(
            product_id=product_size.product_id,
            change_type='transfer_pickup',
            size=transfer.size,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            user_id=transfer.warehouse_keeper_id,
            reference_id=transfer.id,
            notes=(
                f"Entrega a corredor (ID: {transfer.courier_id}) - "
                f"Transferencia #{transfer.id} - "
                f"{delivery_data.get('delivery_notes', 'Sin notas')}"
            ),
            created_at=datetime.now()
        )
        self.db.add(inventory_change)
        
        # ==================== COMMIT ====================
        try:
            self.db.commit()
            logger.info(f"✅ Transacción completada exitosamente")
            
        except SQLAlchemyError as e:
            logger.error(f"❌ Error en commit: {e}")
            self.db.rollback()
            raise RuntimeError(
                f"Error guardando cambios en la base de datos: {str(e)}"
            )
        
        # ==================== RETORNAR RESULTADO DETALLADO ====================
        return {
            "success": True,
            "transfer_id": transfer.id,
            "status": transfer.status,
            "picked_up_at": transfer.picked_up_at.isoformat(),
            "inventory_updated": True,
            "inventory_change": {
                "product_reference": transfer.sneaker_reference_code,
                "product_name": f"{transfer.brand} {transfer.model}",
                "size": transfer.size,
                "quantity_transferred": transfer.quantity,
                "quantity_before": quantity_before,
                "quantity_after": quantity_after,
                "location": source_location_name
            },
            "courier_info": {
                "courier_id": transfer.courier_id,
                "notes": transfer.pickup_notes
            },
            "timestamps": {
                "requested_at": transfer.requested_at.isoformat(),
                "accepted_at": transfer.accepted_at.isoformat() if transfer.accepted_at else None,
                "picked_up_at": transfer.picked_up_at.isoformat()
            }
        }
    
    def deliver_to_vendor(
        self, 
        transfer_id: int, 
        delivery_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Entregar producto directamente al vendedor (self-pickup)
        Similar a deliver_to_courier pero sin corredor intermedio
        
        VALIDACIONES:
        1. Transferencia existe y está en estado 'accepted'
        2. pickup_type = 'vendedor' (NO corredor)
        3. Producto existe en ubicación origen
        4. Stock suficiente
        5. Vendedor (courier_id) está asignado
        
        PROCESO:
        1. Validar transferencia y pickup_type
        2. Descontar inventario automáticamente
        3. Cambiar estado a 'in_transit'
        4. Registrar timestamp de entrega
        5. Registrar cambio en historial de inventario
        """
        
        logger.info(f"🚶 Iniciando entrega directa al vendedor - Transfer ID: {transfer_id}")
        
        # ==================== VALIDACIÓN 1: TRANSFERENCIA EXISTE ====================
        transfer = self.db.query(TransferRequest).filter(
            TransferRequest.id == transfer_id
        ).first()
        
        if not transfer:
            logger.error(f"❌ Transferencia {transfer_id} no encontrada")
            raise ValueError(f"Transferencia #{transfer_id} no existe")
        
        logger.info(f"✅ Transferencia encontrada: {transfer.sneaker_reference_code}")
        
        # ==================== VALIDACIÓN 2: ESTADO VÁLIDO ====================
        if transfer.status != 'accepted':
            logger.error(f"❌ Estado inválido: {transfer.status}")
            raise ValueError(
                f"La transferencia debe estar en estado 'accepted'. Estado actual: {transfer.status}"
            )
        
        # ==================== VALIDACIÓN 3: PICKUP_TYPE = 'VENDEDOR' ====================
        if transfer.pickup_type != 'vendedor':
            logger.error(f"❌ pickup_type incorrecto: {transfer.pickup_type}")
            raise ValueError(
                f"Esta transferencia requiere corredor (pickup_type: {transfer.pickup_type}). "
                f"Use /deliver-to-courier para entregas con corredor."
            )
        
        logger.info(f"✅ Validación pickup_type correcta: vendedor")
        
    
        # ==================== OBTENER UBICACIÓN ORIGEN ====================
        source_location = self.db.query(Location).filter(
            Location.id == transfer.source_location_id
        ).first()
        
        if not source_location:
            logger.error(f"❌ Ubicación origen no encontrada: {transfer.source_location_id}")
            raise ValueError(f"Ubicación origen (ID: {transfer.source_location_id}) no existe")
        
        source_location_name = source_location.name
        logger.info(f"✅ Ubicación origen: {source_location_name}")
        
        # ==================== VALIDACIÓN 5: PRODUCTO EXISTE ====================
        product_size = self.db.query(ProductSize).join(Product).filter(
            and_(
                Product.reference_code == transfer.sneaker_reference_code,
                ProductSize.size == transfer.size,
                ProductSize.location_name == source_location_name
            )
        ).first()
        
        if not product_size:
            logger.error(f"❌ Producto no encontrado en inventario")
            raise ValueError(
                f"Producto {transfer.sneaker_reference_code} talla {transfer.size} "
                f"no encontrado en {source_location_name}"
            )
        
        logger.info(f"✅ Producto encontrado - Stock actual: {product_size.quantity}")
        
        # ==================== VALIDACIÓN 6: STOCK SUFICIENTE ====================
        if product_size.quantity < transfer.quantity:
            logger.error(
                f"❌ Stock insuficiente: "
                f"Requerido: {transfer.quantity}, Disponible: {product_size.quantity}"
            )
            raise ValueError(
                f"Stock insuficiente. Disponible: {product_size.quantity}, "
                f"Requerido: {transfer.quantity}"
            )
        
        logger.info(f"✅ Stock suficiente para transferir {transfer.quantity} unidades")
        
        # ==================== DESCUENTO AUTOMÁTICO DE INVENTARIO ====================
        quantity_before = product_size.quantity
        product_size.quantity -= transfer.quantity
        quantity_after = product_size.quantity
        
        logger.info(
            f"📦 Inventario actualizado: {quantity_before} → {quantity_after} "
            f"(-{transfer.quantity})"
        )
        
        # ==================== ACTUALIZAR TRANSFERENCIA ====================
        transfer.status = 'delivered'
        transfer.picked_up_at = datetime.now()
        transfer.pickup_notes = delivery_data.get('delivery_notes', 'Entregado al vendedor para auto-recogida')
        
        logger.info(f"✅ Estado actualizado: accepted → in_transit")
        logger.info(f"✅ Timestamp registrado: {transfer.picked_up_at}")
        
        # ==================== REGISTRAR EN HISTORIAL ====================
        inventory_change = InventoryChange(
            product_id=product_size.product_id,
            change_type='vendor_pickup',  # Tipo específico para self-pickup
            size=transfer.size,
            quantity_before=quantity_before,
            quantity_after=quantity_after,
            user_id=transfer.warehouse_keeper_id,
            reference_id=transfer.id,
            notes=(
                f"Entrega directa a vendedor (ID: {transfer.courier_id}) - "
                f"Transferencia #{transfer.id} - "
                f"{delivery_data.get('delivery_notes', 'Self-pickup confirmado')}"
            ),
            created_at=datetime.now()
        )
        self.db.add(inventory_change)
        
        # ==================== COMMIT ====================
        try:
            self.db.commit()
            logger.info(f"✅ Transacción completada exitosamente")
            
        except SQLAlchemyError as e:
            logger.error(f"❌ Error en commit: {e}")
            self.db.rollback()
            raise RuntimeError(
                f"Error guardando cambios en la base de datos: {str(e)}"
            )
        
        # ==================== RETORNAR RESULTADO DETALLADO ====================
        return {
            "success": True,
            "transfer_id": transfer.id,
            "status": transfer.status,
            "pickup_type": "vendedor",
            "picked_up_at": transfer.picked_up_at.isoformat(),
            "inventory_updated": True,
            "inventory_change": {
                "product_reference": transfer.sneaker_reference_code,
                "product_name": f"{transfer.brand} {transfer.model}",
                "size": transfer.size,
                "quantity_transferred": transfer.quantity,
                "quantity_before": quantity_before,
                "quantity_after": quantity_after,
                "location": source_location_name
            },
            "vendor_info": {
                "vendor_id": transfer.courier_id,  # En self-pickup, courier_id es el vendedor
                "notes": transfer.pickup_notes,
                "pickup_method": "self_pickup"
            },
            "timestamps": {
                "requested_at": transfer.requested_at.isoformat(),
                "accepted_at": transfer.accepted_at.isoformat() if transfer.accepted_at else None,
                "picked_up_at": transfer.picked_up_at.isoformat()
            },
            "next_steps": [
                "Vendedor debe confirmar llegada a su ubicación",
                "Inventario se incrementará automáticamente en destino al confirmar"
            ]
        }
    

    def confirm_return_reception(
        self,
        return_id: int,
        reception_data: Dict[str, Any],
        warehouse_keeper_id: int,
        managed_location_ids: List[int]
    ) -> Dict[str, Any]:
        """
        BG010: Confirmar recepción de devolución con RESTAURACIÓN de inventario
        
        FLUJO CORRECTO:
        1. Buscar Product GLOBAL (sin location_name) - SOLO UNA VEZ
        2. Buscar/crear ProductSize en ubicación DESTINO (bodega)
        3. SUMAR cantidad en ProductSize
        4. Registrar cambio en InventoryChange
        """
        
        try:
            logger.info(f"📦 Procesando recepción de return {return_id}")
            
            # ==================== VALIDACIÓN 1: OBTENER RETURN ====================
            return_transfer = self.db.query(TransferRequest).filter(
                TransferRequest.id == return_id
            ).first()
            
            if not return_transfer:
                raise ValueError(f"Return #{return_id} no encontrado")
            
            # ==================== VALIDACIÓN 2: ES UN RETURN ====================
            if not return_transfer.original_transfer_id:
                raise ValueError("Esta transferencia no es una devolución")
            
            # ==================== VALIDACIÓN 3: PERMISOS ====================
            if return_transfer.destination_location_id not in managed_location_ids:
                raise ValueError(
                    f"No tienes permisos para gestionar ubicación destino (bodega)"
                )
            
            # ==================== VALIDACIÓN 4: ESTADO ====================
            if return_transfer.status != 'delivered':
                raise ValueError(
                    f"Return debe estar en estado 'delivered'. Estado actual: {return_transfer.status}"
                )
            
            logger.info(f"✅ Return válido: {return_transfer.sneaker_reference_code}")
            
            # ==================== OBTENER UBICACIÓN DESTINO (BODEGA) ====================
            destination_location = self.db.query(Location).filter(
                Location.id == return_transfer.destination_location_id
            ).first()
            
            if not destination_location:
                raise ValueError("Ubicación destino (bodega) no encontrada")
            
            destination_location_name = destination_location.name
            logger.info(f"📍 Bodega destino: {destination_location_name}")
            
            # ==================== BUSCAR PRODUCTO GLOBAL (SIN LOCATION) ====================
            # ✅ CORRECTO: Buscar Product SIN filtrar por location_name
            product = self.db.query(Product).filter(
                Product.reference_code == return_transfer.sneaker_reference_code
            ).first()
            
            if not product:
                logger.error(
                    f"❌ Producto {return_transfer.sneaker_reference_code} no existe en el sistema"
                )
                raise ValueError(
                    f"Producto {return_transfer.sneaker_reference_code} no existe. "
                    f"Debe estar registrado en el sistema antes de procesar devoluciones."
                )
            
            logger.info(f"✅ Producto encontrado: ID {product.id}")
            
            # ==================== BUSCAR/CREAR PRODUCT_SIZE EN DESTINO ====================
            # ✅ CORRECTO: ProductSize es específico por ubicación
            product_size = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == return_transfer.size,
                    ProductSize.location_name == destination_location_name  # ← BODEGA
                )
            ).with_for_update().first()  # ← LOCK para evitar race conditions
            
            quantity_before = 0
            
            if product_size:
                # ✅ YA EXISTE: SUMAR cantidad (RESTAURACIÓN)
                quantity_before = product_size.quantity
                product_size.quantity += reception_data['received_quantity']
                product_size.updated_at = datetime.now()
                
                logger.info(
                    f"✅ Stock restaurado en ProductSize (ID: {product_size.id}): "
                    f"{quantity_before} → {product_size.quantity} "
                    f"(+{reception_data['received_quantity']})"
                )
            else:
                # ✅ NO EXISTE: CREAR ProductSize en bodega
                product_size = ProductSize(
                    product_id=product.id,
                    size=return_transfer.size,
                    quantity=reception_data['received_quantity'],
                    quantity_exhibition=0,
                    location_name=destination_location_name,  # ← BODEGA
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(product_size)
                self.db.flush()  # Obtener ID
                
                logger.info(
                    f"✅ Nuevo ProductSize creado (ID: {product_size.id}): "
                    f"qty={reception_data['received_quantity']} en '{destination_location_name}'"
                )
            
            quantity_after = product_size.quantity
            
            # ==================== MANEJAR PRODUCTO SEGÚN CONDICIÓN ====================
            inventory_restored = True
            change_type = 'return_reception'
            
            if reception_data['product_condition'] == 'damaged':
                # Producto dañado: SUMA pero marca para revisión
                change_type = 'return_reception_damaged'
                logger.warning(
                    f"⚠️ Producto recibido CON DAÑOS pero suma a inventario para reparación"
                )
            
            elif reception_data['product_condition'] == 'unusable':
                # Producto inservible: REVERTIR suma (NO regresa a inventario)
                product_size.quantity = quantity_before  # ← Deshacer suma
                quantity_after = quantity_before
                inventory_restored = False
                change_type = 'return_reception_unusable'
                
                logger.warning(
                    f"❌ Producto INSERVIBLE - NO suma a inventario vendible "
                    f"(quantity se mantiene en {quantity_before})"
                )
            
            # ==================== ACTUALIZAR ESTADO DEL RETURN ====================
            return_transfer.status = 'completed'
            return_transfer.confirmed_reception_at = datetime.now()
            return_transfer.received_quantity = reception_data['received_quantity']
            return_transfer.reception_notes = (
                f"Condición: {reception_data['product_condition']}\n"
                f"Control calidad: {'✅ Pasó' if reception_data['quality_check_passed'] else '❌ No pasó'}\n"
                f"Restaurado a inventario: {'✅ Sí' if inventory_restored else '❌ No'}\n"
                f"{reception_data.get('notes', '')}"
            )
            
            logger.info(f"✅ Return marcado como completado")
            
            # ==================== REGISTRAR EN HISTORIAL ====================
            inventory_change = InventoryChange(
                product_id=product.id,  # ← Product ID global
                change_type=change_type,
                size=return_transfer.size,
                quantity_before=quantity_before,
                quantity_after=quantity_after,
                user_id=warehouse_keeper_id,
                reference_id=return_id,
                notes=(
                    f"DEVOLUCIÓN recibida - Transfer original #{return_transfer.original_transfer_id}\n"
                    f"Ubicación: {destination_location_name}\n"
                    f"Condición: {reception_data['product_condition']}\n"
                    f"Cantidad restaurada: {reception_data['received_quantity']}\n"
                    f"Calidad OK: {'Sí' if reception_data['quality_check_passed'] else 'No'}\n"
                    f"{reception_data.get('notes', '')}"
                ),
                created_at=datetime.now()
            )
            self.db.add(inventory_change)
            
            logger.info(f"✅ Cambio registrado en InventoryChange")
            
            # ==================== COMMIT ====================
            self.db.commit()
            logger.info(f"✅ Return completado - Transacción confirmada")
            
            # ==================== RESPUESTA DETALLADA ====================
            return {
                "return_id": return_id,
                "original_transfer_id": return_transfer.original_transfer_id,
                "received_quantity": reception_data['received_quantity'],
                "product_condition": reception_data['product_condition'],
                "inventory_restored": inventory_restored,
                "warehouse_location": destination_location_name,
                "inventory_change": {
                    "product_id": product.id,
                    "product_size_id": product_size.id,
                    "product_reference": return_transfer.sneaker_reference_code,
                    "product_name": f"{return_transfer.brand} {return_transfer.model}",
                    "size": return_transfer.size,
                    "quantity_returned": reception_data['received_quantity'],
                    "quantity_before": quantity_before,
                    "quantity_after": quantity_after,
                    "location": destination_location_name,
                    "change_type": change_type
                },
                "timestamps": {
                    "return_requested_at": return_transfer.requested_at.isoformat(),
                    "delivered_at": return_transfer.delivered_at.isoformat() if return_transfer.delivered_at else None,
                    "confirmed_reception_at": return_transfer.confirmed_reception_at.isoformat()
                },
                "quality_info": {
                    "condition": reception_data['product_condition'],
                    "quality_check_passed": reception_data['quality_check_passed'],
                    "returned_to_inventory": inventory_restored,
                    "notes": reception_data.get('notes', '')
                }
            }
            
        except ValueError as e:
            logger.error(f"❌ Error validación: {e}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.exception("❌ Error confirmando return")
            self.db.rollback()
            raise RuntimeError(f"Error procesando return: {str(e)}")