# app/modules/warehouse_new/repository.py - VERSIÓN COMPLETA

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_, text, desc, func ,case ,or_ 
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
    
    
        

    def get_pending_requests_for_warehouse(self, warehouse_keeper_id: int, company_id: int) -> List[Dict[str, Any]]:
        """
        BG001: Obtener solicitudes pendientes para bodeguero
        ✅ CON ROLLBACK PREVENTIVO
        """
        
        # ✅ CRÍTICO: Rollback al inicio para limpiar cualquier transacción fallida
        try:
            self.db.rollback()
        except:
            pass
        
        try:
            logger.info(f"📋 Buscando solicitudes pendientes para bodeguero {warehouse_keeper_id}")
            
            # Obtener ubicaciones que este bodeguero puede gestionar
            managed_locations = self.get_user_managed_locations(warehouse_keeper_id, company_id)
            location_ids = [loc['location_id'] for loc in managed_locations]
            
            if not location_ids:
                logger.warning(f"⚠️ Bodeguero {warehouse_keeper_id} no tiene ubicaciones asignadas")
                return []
            
            logger.info(f"✅ Ubicaciones gestionadas: {location_ids}")
            
            # Query usando ORM
            from sqlalchemy import case, func, or_
            
            query = self.db.query(
                TransferRequest,
                User.first_name.label('requester_first_name'),
                User.last_name.label('requester_last_name'),
                User.email.label('requester_email'),
                Location.name.label('source_location_name'),
                Location.address.label('source_address'),
                func.coalesce(Product.image_url, '').label('product_image'),
                func.coalesce(Product.unit_price, 0).label('unit_price'),
                func.coalesce(Product.box_price, 0).label('box_price'),
                func.coalesce(ProductSize.quantity, 0).label('stock_available')
            ).join(
                User, TransferRequest.requester_id == User.id
            ).join(
                Location, TransferRequest.source_location_id == Location.id
            ).outerjoin(
                Product, 
                and_(
                    Product.reference_code == TransferRequest.sneaker_reference_code,
                    Product.company_id == TransferRequest.company_id
                )
            ).outerjoin(
                ProductSize,
                and_(
                    ProductSize.product_id == Product.id,
                    ProductSize.size == TransferRequest.size,
                    ProductSize.location_name == Location.name,
                    ProductSize.inventory_type == TransferRequest.inventory_type.cast(ProductSize.inventory_type.type),
                    ProductSize.company_id == TransferRequest.company_id
                )
            ).filter(
                TransferRequest.status == 'pending',
                TransferRequest.company_id == company_id,
                or_(
                    and_(
                        TransferRequest.request_type == 'transfer',
                        TransferRequest.source_location_id.in_(location_ids)
                    ),
                    and_(
                        TransferRequest.request_type == 'return',
                        TransferRequest.destination_location_id.in_(location_ids)
                    )
                )
            ).order_by(
                case(
                    (TransferRequest.purpose == 'cliente', 1),
                    (TransferRequest.request_type == 'return', 2),
                    else_=3
                ),
                TransferRequest.requested_at.asc()
            )
            
            results = query.all()
            
            logger.info(f"✅ Query ejecutado, {len(results)} resultados encontrados")
            
            # Formatear resultados
            requests = []
            for row in results:
                tr = row.TransferRequest
                
                # Calcular prioridad
                urgent_action = tr.purpose == 'cliente' or tr.request_type == 'return'
                priority_level = 'alta' if urgent_action else 'normal'
                
                # Calcular tiempo transcurrido
                time_elapsed = datetime.now() - tr.requested_at
                hours = int(time_elapsed.total_seconds() // 3600)
                minutes = int((time_elapsed.total_seconds() % 3600) // 60)
                time_elapsed_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Determinar qué preparar
                inventory_type_label = {
                    'pair': '👟👟 Par completo',
                    'left_only': '👟← Pie IZQUIERDO',
                    'right_only': '👟→ Pie DERECHO'
                }.get(tr.inventory_type or 'pair', '❓ Desconocido')
                
                # Instrucción de preparación
                if tr.inventory_type == 'pair' or not tr.inventory_type:
                    preparation_instruction = f"✅ Preparar {tr.quantity} par(es) completo(s) de {tr.brand} {tr.model} talla {tr.size}"
                elif tr.inventory_type == 'left_only':
                    preparation_instruction = f"👟← Preparar {tr.quantity} pie(s) IZQUIERDO(S) de {tr.brand} {tr.model} talla {tr.size}"
                elif tr.inventory_type == 'right_only':
                    preparation_instruction = f"👟→ Preparar {tr.quantity} pie(s) DERECHO(S) de {tr.brand} {tr.model} talla {tr.size}"
                else:
                    preparation_instruction = f"⚠️ Preparar {tr.quantity} unidad(es) de {tr.brand} {tr.model} talla {tr.size}"
                
                # Obtener ubicación destino
                dest_location = self.db.query(Location).filter(
                    Location.id == tr.destination_location_id
                ).first()
                
                requests.append({
                    'id': tr.id,
                    'status': tr.status,
                    'request_type': tr.request_type,
                    'sneaker_reference_code': tr.sneaker_reference_code,
                    'brand': tr.brand,
                    'model': tr.model,
                    'size': tr.size,
                    'quantity': tr.quantity,
                    
                    # Información de tipo de inventario
                    'inventory_type': tr.inventory_type or 'pair',
                    'inventory_type_label': inventory_type_label,
                    'preparation_instruction': preparation_instruction,
                    
                    'purpose': tr.purpose,
                    'pickup_type': tr.pickup_type,
                    'urgent_action': urgent_action,
                    'priority_level': priority_level,
                    'time_elapsed': time_elapsed_str,
                    'requested_at': tr.requested_at.isoformat(),
                    
                    'product_info': {
                        'image_url': row.product_image,
                        'unit_price': float(row.unit_price),
                        'box_price': float(row.box_price),
                        'stock_available': row.stock_available,
                        'description': f"{tr.brand} {tr.model} - Talla {tr.size}"
                    },
                    'requester_info': {
                        'name': f"{row.requester_first_name} {row.requester_last_name}",
                        'email': row.requester_email
                    },
                    'location_info': {
                        'from': {
                            'id': tr.source_location_id,
                            'name': row.source_location_name,
                            'address': row.source_address or 'No especificada'
                        },
                        'to': {
                            'id': tr.destination_location_id,
                            'name': dest_location.name if dest_location else 'Desconocido',
                            'address': dest_location.address if dest_location else 'No especificada'
                        }
                    },
                    'notes': tr.notes
                })
            
            logger.info(f"✅ Formateadas {len(requests)} solicitudes pendientes")
            return requests
            
        except Exception as e:
            logger.exception(f"❌ Error obteniendo solicitudes pendientes: {str(e)}")
            # Rollback en caso de error
            try:
                self.db.rollback()
            except:
                pass
            return []

    def _get_preparation_instruction(
        self,
        inventory_type: str,
        brand: str,
        model: str,
        size: str,
        quantity: int
    ) -> str:
        """
        Generar instrucción clara de preparación para el bodeguero
            """
        product_name = f"{brand} {model} talla {size}"
            
        if inventory_type == 'pair':
            return f"✅ Preparar {quantity} par(es) completo(s) de {product_name}"
        elif inventory_type == 'left_only':
            return f"👟← Preparar {quantity} pie(s) IZQUIERDO(S) de {product_name}"
        elif inventory_type == 'right_only':
            return f"👟→ Preparar {quantity} pie(s) DERECHO(S) de {product_name}"
        else:
            return f"⚠️ Preparar {quantity} unidad(es) de {product_name} (tipo desconocido)"
    
    def get_user_managed_locations(self, user_id: int, company_id: int) -> List[Dict[str, Any]]:
        """Obtener ubicaciones que un bodeguero puede gestionar - FILTRADO POR COMPANY_ID"""
        try:
            # Obtener asignaciones de ubicaciones
            assignments = self.db.query(UserLocationAssignment).filter(
                and_(
                    UserLocationAssignment.user_id == user_id,
                    UserLocationAssignment.company_id == company_id,
                    UserLocationAssignment.is_active == True
                )
            ).all()
            
            if not assignments:
                # Si no tiene asignaciones, usar su location_id principal
                user = self.db.query(User).filter(
                    and_(
                        User.id == user_id,
                        User.company_id == company_id
                    )
                ).first()
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
        warehouse_keeper_id: int,
        company_id: int
    ) -> bool:
        """BG002: Aceptar o rechazar solicitud de transferencia - FILTRADO POR COMPANY_ID"""
        try:
            logger.info(f"✅ Aceptando solicitud {request_id}")
            
            transfer = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.id == request_id,
                    TransferRequest.company_id == company_id
                )
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
    

    # def get_accepted_requests_by_warehouse_keeper(self, warehouse_keeper_id: int, company_id: int) -> List[Dict[str, Any]]:
    #     """
    #     Obtener solicitudes aceptadas por este bodeguero - FILTRADO POR COMPANY_ID
        
    #     Incluye:
    #     - Imagen del producto
    #     - Tipo de recogida (vendedor o corredor)
    #     - Tipo de transferencia (transfer o return)
    #     - Información completa de participantes
    #     - Estado detallado con siguiente acción
    #     """
    #     try:
    #         logger.info(f"Obteniendo solicitudes aceptadas para bodeguero {warehouse_keeper_id}")
            
    #         active_statuses = ['accepted', 'courier_assigned', 'delivered']
            
    #         transfers = self.db.query(TransferRequest).filter(
    #             and_(
    #                 TransferRequest.warehouse_keeper_id == warehouse_keeper_id,
    #                 TransferRequest.company_id == company_id,
    #                 TransferRequest.status.in_(active_statuses)
    #             )
    #         ).order_by(
    #             # ✅ SINTAXIS CORRECTA con case()
    #             case(
    #                 (TransferRequest.purpose == 'cliente', 1),
    #                 else_=2
    #             ),
    #             case(
    #                 (TransferRequest.status == 'courier_assigned', 1),
    #                 (TransferRequest.status == 'accepted', 2),
    #                 else_=3
    #             ),
    #             TransferRequest.accepted_at.asc()
    #         ).all()
            
    #         results = []
    #         for transfer in transfers:
    #             # Calcular tiempo desde aceptación
    #             time_diff = datetime.now() - transfer.accepted_at if transfer.accepted_at else timedelta(0)
    #             hours = int(time_diff.total_seconds() // 3600)
    #             minutes = int((time_diff.total_seconds() % 3600) // 60)
    #             time_since_accepted = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
    #             # Obtener imagen del producto
    #             product_image = self._get_product_image(
    #                 transfer.sneaker_reference_code,
    #                 transfer.source_location_id,
    #                 company_id
    #             )
                
    #             # Determinar tipo de transferencia
    #             transfer_type = 'return' if transfer.original_transfer_id else 'transfer'
    #             transfer_type_display = 'DEVOLUCIÓN' if transfer_type == 'return' else 'TRANSFERENCIA'
                
    #             # Determinar quién recoge
    #             pickup_info = self._get_pickup_info(transfer)
                
    #             # Estado y siguiente acción
    #             status_info = self._get_warehouse_status_info(transfer.status, transfer.pickup_type)
                
    #             # Información de ubicaciones
    #             source_location = self.db.query(Location).filter(
    #                 and_(
    #                     Location.id == transfer.source_location_id,
    #                     Location.company_id == company_id
    #                 )
    #             ).first()
                
    #             destination_location = self.db.query(Location).filter(
    #                 and_(
    #                     Location.id == transfer.destination_location_id,
    #                     Location.company_id == company_id
    #                 )
    #             ).first()
                
    #             results.append({
    #                 'id': transfer.id,
    #                 'status': transfer.status,
    #                 'status_info': status_info,
                    
    #                 # Información del producto
    #                 'sneaker_reference_code': transfer.sneaker_reference_code,
    #                 'brand': transfer.brand,
    #                 'model': transfer.model,
    #                 'size': transfer.size,
    #                 'quantity': transfer.quantity,
    #                 'product_image': product_image,
    #                 'product_description': f"{transfer.brand} {transfer.model} - Talla {transfer.size}",
                    
    #                 # Tipo de transferencia
    #                 'transfer_type': transfer_type,
    #                 'transfer_type_display': transfer_type_display,
    #                 'purpose': transfer.purpose,
    #                 'priority': 'high' if transfer.purpose == 'cliente' else 'normal',
                    
    #                 # Información de recogida
    #                 'pickup_type': transfer.pickup_type,
    #                 'pickup_info': pickup_info,
                    
    #                 # Participantes
    #                 'requester_info': {
    #                     'id': transfer.requester_id,
    #                     'name': f"{transfer.requester.first_name} {transfer.requester.last_name}" if transfer.requester else None,
    #                     'role': transfer.requester.role if transfer.requester else None
    #                 },
    #                 'courier_info': {
    #                     'id': transfer.courier_id,
    #                     'name': f"{transfer.courier.first_name} {transfer.courier.last_name}" if transfer.courier else None,
    #                     'assigned': transfer.courier_id is not None
    #                 } if transfer.pickup_type == 'corredor' else None,
                    
    #                 # Ubicaciones
    #                 'location_info': {
    #                     'source': {
    #                         'id': transfer.source_location_id,
    #                         'name': source_location.name if source_location else None
    #                     },
    #                     'destination': {
    #                         'id': transfer.destination_location_id,
    #                         'name': destination_location.name if destination_location else None
    #                     }
    #                 },
                    
    #                 # Timestamps
    #                 'requested_at': transfer.requested_at.isoformat() if transfer.requested_at else None,
    #                 'accepted_at': transfer.accepted_at.isoformat() if transfer.accepted_at else None,
    #                 'courier_accepted_at': transfer.courier_accepted_at.isoformat() if transfer.courier_accepted_at else None,
    #                 'picked_up_at': transfer.picked_up_at.isoformat() if transfer.picked_up_at else None,
    #                 'time_since_accepted': time_since_accepted,
                    
    #                 # Notas
    #                 'notes': transfer.notes,
    #                 'warehouse_notes': transfer.notes
    #             })
            
    #         logger.info(f"{len(results)} solicitudes encontradas")
    #         return results
            
    #     except Exception as e:
    #         logger.exception("Error obteniendo solicitudes aceptadas")
    #         return []


    # app/modules/warehouse_new/repository.py

    # Actualización del método get_accepted_requests_by_warehouse_keeper
# Para incluir el nombre del corredor asignado cuando el pickup_type es 'corredor'

    def get_accepted_requests_by_warehouse_keeper(self, warehouse_keeper_id: int, company_id: int) -> List[Dict[str, Any]]:
        """
        BG002: Obtener solicitudes aceptadas
        ✅ CON ROLLBACK PREVENTIVO
        ✅ INCLUYE NOMBRE DEL CORREDOR cuando pickup_type = 'corredor' y hay courier_id
        """
        
        # ✅ Rollback preventivo
        try:
            self.db.rollback()
        except:
            pass
        
        try:
            logger.info(f"📋 Buscando solicitudes aceptadas para bodeguero {warehouse_keeper_id}")
            
            # Alias para el corredor
            Courier = aliased(User)
            
            query = self.db.query(
                TransferRequest,
                User.first_name.label('requester_first_name'),
                User.last_name.label('requester_last_name'),
                Location.name.label('source_location_name'),
                func.coalesce(Product.image_url, '').label('product_image'),
                func.coalesce(ProductSize.quantity, 0).label('stock_available'),
                # ✅ NUEVO: Incluir nombre del corredor
                Courier.first_name.label('courier_first_name'),
                Courier.last_name.label('courier_last_name')
            ).join(
                User, TransferRequest.requester_id == User.id
            ).join(
                Location, TransferRequest.source_location_id == Location.id
            ).outerjoin(
                Product,
                and_(
                    Product.reference_code == TransferRequest.sneaker_reference_code,
                    Product.company_id == TransferRequest.company_id
                )
            ).outerjoin(
                ProductSize,
                and_(
                    ProductSize.product_id == Product.id,
                    ProductSize.size == TransferRequest.size,
                    ProductSize.location_name == Location.name,
                    ProductSize.inventory_type == TransferRequest.inventory_type.cast(ProductSize.inventory_type.type),
                    ProductSize.company_id == TransferRequest.company_id
                )
            ).outerjoin(
                # ✅ NUEVO: Join con la tabla User para obtener info del corredor
                Courier, 
                and_(
                    TransferRequest.courier_id == Courier.id,
                    TransferRequest.pickup_type == 'corredor'  # Solo cuando es tipo corredor
                )
            ).filter(
                TransferRequest.status.in_(['accepted','delivered', 'in_transit','courier_assigned']),
                TransferRequest.warehouse_keeper_id == warehouse_keeper_id,
                TransferRequest.company_id == company_id
            ).order_by(
                TransferRequest.accepted_at.asc()
            )
            
            results = query.all()
            
            logger.info(f"✅ Query ejecutado, {len(results)} resultados encontrados")
            
            requests = []
            for row in results:
                tr = row.TransferRequest
                
                # Etiquetas descriptivas
                inventory_type_label = {
                    'pair': '👟👟 Par completo',
                    'left_only': '👟← Pie Izquierdo',
                    'right_only': '👟→ Pie Derecho'
                }.get(tr.inventory_type, tr.inventory_type)
                
                # Calcular tiempo desde aceptación
                time_diff = datetime.now() - tr.accepted_at if tr.accepted_at else timedelta(0)
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                time_since_accepted = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                # Determinar tipo de solicitud
                request_type = 'return' if tr.original_transfer_id else 'transfer'
                request_type_display = 'DEVOLUCIÓN' if request_type == 'return' else 'TRANSFERENCIA'
                
                # ✅ NUEVO: Información del corredor según el tipo de entrega
                courier_info = None
                if tr.pickup_type == 'corredor':
                    if tr.courier_id:
                        # Hay corredor asignado
                        courier_name = f"{row.courier_first_name} {row.courier_last_name}" if row.courier_first_name else "Corredor sin nombre"
                        courier_info = {
                            'id': tr.courier_id,
                            'name': courier_name,
                            'assigned': True,
                            'status': 'assigned'
                        }
                    else:
                        # No hay corredor asignado aún
                        courier_info = {
                            'id': None,
                            'name': None,
                            'assigned': False,
                            'status': 'waiting_assignment'
                        }
                # Si pickup_type es 'vendedor', courier_info queda como None (no es necesario)
                
                # Información de recogida
                pickup_info = self._get_pickup_info(tr)
                
                # Estado detallado
                status_info = self._get_warehouse_status_info(tr.status, tr.pickup_type)
                
                request = {
                    # Identificadores
                    'id': tr.id,
                    'status': tr.status,
                    'status_info': status_info,
                    'request_type': request_type,
                    'request_type_display': request_type_display,
                    
                    # Producto
                    'product': {
                        'reference_code': tr.sneaker_reference_code,
                        'brand': tr.brand,
                        'model': tr.model,
                        'size': tr.size,
                        'quantity': tr.quantity,
                        'inventory_type': tr.inventory_type,
                        'inventory_type_label': inventory_type_label,
                        'image_url': row.product_image,
                        'stock_available': row.stock_available
                    },
                    
                    # Propósito
                    'purpose': tr.purpose,
                    'purpose_display': 'Cliente esperando' if tr.purpose == 'cliente' else 'Restock',
                    'urgent_action': tr.purpose == 'cliente',
                    
                    # Información de recogida
                    'pickup_type': tr.pickup_type,
                    'pickup_info': pickup_info,
                    
                    'courier_info': courier_info,
                    
                    # Participantes
                    'requester_info': {
                        'id': tr.requester_id,
                        'name': f"{row.requester_first_name} {row.requester_last_name}",
                        'role': tr.requester.role if tr.requester else None
                    },
                    
                    # Ubicación
                    'location': {
                        'source_id': tr.source_location_id,
                        'source_name': row.source_location_name
                    },
                    
                    # Timestamps
                    'requested_at': tr.requested_at.isoformat() if tr.requested_at else None,
                    'accepted_at': tr.accepted_at.isoformat() if tr.accepted_at else None,
                    'time_since_accepted': time_since_accepted,
                    
                    # Notas
                    'notes': tr.notes,
                    'warehouse_notes': tr.notes
                }
                
                requests.append(request)
            
            logger.info(f"✅ {len(requests)} solicitudes formateadas correctamente")
            return requests
            
        except Exception as e:
            logger.exception("❌ Error obteniendo solicitudes aceptadas")
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
                    'courier_assigned': True,
                    'courier_id': transfer.courier_id
                }
            else:
                return {
                    'type': 'corredor',
                    'type_display': 'Esperando Corredor',
                    'who': 'Pendiente de asignar',
                    'description': 'Esperando que un corredor acepte la solicitud',
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

    def _get_product_image(self, reference_code: str, source_location_id: int, company_id: int) -> str:
        """
        Obtener imagen del producto - FILTRADO POR COMPANY_ID
        """
        try:
            source_location = self.db.query(Location).filter(
                and_(
                    Location.id == source_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            if not source_location:
                return self._get_placeholder_image(reference_code)
            
            # Buscar producto con imagen
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == reference_code,
                    Product.location_name == source_location.name,
                    Product.company_id == company_id
                )
            ).first()
            
            # Si no existe o no tiene imagen, buscar global
            if not product or not product.image_url:
                product = self.db.query(Product).filter(
                    and_(
                        Product.reference_code == reference_code,
                        Product.company_id == company_id
                    )
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
    
    def get_inventory_by_location(self, location_id: int, company_id: int) -> List[Dict[str, Any]]:
        """BG006: Consultar inventario por ubicación - FILTRADO POR COMPANY_ID"""
        try:
            logger.info(f"📊 Obteniendo inventario de ubicación {location_id}")
            
            # Obtener nombre real de ubicación
            location = self.db.query(Location).filter(
                and_(
                    Location.id == location_id,
                    Location.company_id == company_id
                )
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
                and_(
                    ProductSize.location_name == location_name,
                    Product.company_id == company_id,
                    ProductSize.company_id == company_id
                )
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
        delivery_data: Dict[str, Any],
        company_id: int
    ) -> Dict[str, Any]:
        """
        BG003: Entregar producto a corredor con descuento automático de inventario - FILTRADO POR COMPANY_ID
        
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
            and_(
                TransferRequest.id == request_id,
                TransferRequest.company_id == company_id
            )
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
            and_(
                Location.id == transfer.source_location_id,
                Location.company_id == company_id
            )
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
                ProductSize.location_name == source_location_name,  # ✅ NOMBRE REAL
                Product.company_id == company_id,
                ProductSize.company_id == company_id,
                ProductSize.inventory_type == transfer.inventory_type
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
            company_id=company_id,
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
        delivery_data: Dict[str, Any],
        company_id: int
    ) -> Dict[str, Any]:
        """
        Entregar producto directamente al vendedor (self-pickup) - FILTRADO POR COMPANY_ID
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
            and_(
                TransferRequest.id == transfer_id,
                TransferRequest.company_id == company_id
            )
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
            and_(
                Location.id == transfer.source_location_id,
                Location.company_id == company_id
            )
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
                ProductSize.location_name == source_location_name,
                Product.company_id == company_id,
                ProductSize.company_id == company_id,
                ProductSize.inventory_type == transfer.inventory_type
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
            company_id=company_id,
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
        managed_location_ids: List[int],
        company_id: int
    ) -> Dict[str, Any]:
        """
        🆕 ACTUALIZADO: BG010 - Confirmar recepción de devolución con soporte para pies individuales
        
        FLUJO ACTUALIZADO:
        1. Validar que el return existe y está en estado 'delivered'
        2. Validar permisos del bodeguero
        3. Buscar producto (GLOBAL, sin location_name)
        4. 🆕 Buscar/crear ProductSize según inventory_type correcto
        5. SUMAR cantidad recibida (RESTAURACIÓN de inventario)
        6. Registrar en InventoryChange
        7. Actualizar estado del return a 'completed'
        
        Args:
            return_id: ID de la devolución
            reception_data: Datos de recepción {
                'received_quantity': int,
                'condition': str ('good', 'damaged', 'unusable'),
                'notes': Optional[str]
            }
            warehouse_keeper_id: ID del bodeguero que confirma
            managed_location_ids: IDs de ubicaciones que gestiona el bodeguero
            company_id: ID de la compañía
        
        Returns:
            Dict con resultado de la operación
        
        Raises:
            ValueError: Si hay problemas de validación
            Exception: Cualquier otro error
        """
        
        try:
            logger.info(f"📦 Procesando recepción de devolución #{return_id}")
            
            # ========== 1. OBTENER Y VALIDAR RETURN ==========
            return_transfer = self.db.query(TransferRequest).filter(
                and_(
                    TransferRequest.id == return_id,
                    TransferRequest.company_id == company_id
                )
            ).first()
            
            if not return_transfer:
                raise ValueError(f"Devolución #{return_id} no encontrada")
            
            # Validar que es un return
            if not return_transfer.original_transfer_id:
                raise ValueError("Esta transferencia no es una devolución")
            
            logger.info(f"   ✅ Return encontrado")
            logger.info(f"      Producto: {return_transfer.sneaker_reference_code}")
            logger.info(f"      Talla: {return_transfer.size}")
            logger.info(f"      Cantidad: {return_transfer.quantity}")
            logger.info(f"      Tipo: {return_transfer.inventory_type or 'pair'}")
            
            # ========== 2. VALIDAR PERMISOS ==========
            if return_transfer.destination_location_id not in managed_location_ids:
                raise ValueError(
                    "No tienes permisos para gestionar la ubicación destino (bodega)"
                )
            
            logger.info(f"   ✅ Permisos validados")
            
            # ========== 3. VALIDAR ESTADO ==========
            if return_transfer.status != 'delivered':
                raise ValueError(
                    f"Devolución debe estar en estado 'delivered'. "
                    f"Estado actual: {return_transfer.status}"
                )
            
            logger.info(f"   ✅ Estado validado: delivered")
            
            # ========== 4. OBTENER UBICACIÓN DESTINO ==========
            destination_location = self.db.query(Location).filter(
                and_(
                    Location.id == return_transfer.destination_location_id,
                    Location.company_id == company_id
                )
            ).first()
            
            if not destination_location:
                raise ValueError("Ubicación destino no encontrada")
            
            destination_location_name = destination_location.name
            logger.info(f"   📍 Ubicación destino: {destination_location_name}")
            
            # ========== 5. BUSCAR PRODUCTO (GLOBAL) ==========
            # ⚠️ IMPORTANTE: Product NO tiene location_name
            product = self.db.query(Product).filter(
                and_(
                    Product.reference_code == return_transfer.sneaker_reference_code,
                    Product.company_id == company_id
                )
            ).first()
            
            if not product:
                raise ValueError(
                    f"Producto {return_transfer.sneaker_reference_code} no encontrado. "
                    "Debe estar registrado en el sistema antes de procesar devoluciones."
                )
            
            logger.info(f"   ✅ Producto encontrado - ID: {product.id}")
            
            # ========== 6. 🆕 DETERMINAR INVENTORY_TYPE CORRECTO ==========
            inventory_type = return_transfer.inventory_type or 'pair'
            logger.info(f"   📋 Tipo de inventario: {inventory_type}")
            
            # ========== 7. 🆕 BUSCAR/CREAR PRODUCTSIZE SEGÚN TIPO ==========
            product_size = self.db.query(ProductSize).filter(
                and_(
                    ProductSize.product_id == product.id,
                    ProductSize.size == return_transfer.size,
                    ProductSize.location_name == destination_location_name,
                    ProductSize.inventory_type == inventory_type,  # 🆕 Filtrar por tipo correcto
                    ProductSize.company_id == company_id
                )
            ).with_for_update().first()  # ⚠️ LOCK para evitar race conditions
            
            quantity_before = 0
            
            if product_size:
                # ========== CASO A: YA EXISTE - SUMAR CANTIDAD (RESTAURACIÓN) ==========
                quantity_before = product_size.quantity
                product_size.quantity += reception_data['received_quantity']
                product_size.updated_at = datetime.now()
                
                logger.info(
                    f"   ✅ Stock restaurado en ProductSize existente (ID: {product_size.id})"
                )
                logger.info(
                    f"      Antes: {quantity_before} | "
                    f"Después: {product_size.quantity} | "
                    f"Incremento: +{reception_data['received_quantity']}"
                )
                
            else:
                # ========== CASO B: NO EXISTE - CREAR PRODUCTSIZE ==========
                product_size = ProductSize(
                    product_id=product.id,
                    size=return_transfer.size,
                    quantity=reception_data['received_quantity'],
                    quantity_exhibition=0,
                    inventory_type=inventory_type,  # 🆕 Crear con tipo correcto
                    location_name=destination_location_name,
                    company_id=company_id,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                self.db.add(product_size)
                self.db.flush()  # Para obtener el ID
                
                logger.info(
                    f"   ✅ Nuevo ProductSize creado (ID: {product_size.id})"
                )
                logger.info(
                    f"      Tipo: {inventory_type} | "
                    f"Cantidad: {reception_data['received_quantity']} | "
                    f"Ubicación: {destination_location_name}"
                )
            
            # ========== 8. REGISTRAR EN INVENTORYCHANGE ==========
            foot_type_desc = ""
            if inventory_type == 'left_only':
                foot_type_desc = " (pies izquierdos)"
            elif inventory_type == 'right_only':
                foot_type_desc = " (pies derechos)"
            elif inventory_type == 'pair':
                foot_type_desc = " (pares)"
            
            notes = (
                f"Devolución recibida y confirmada{foot_type_desc}. "
                f"Cantidad: {reception_data['received_quantity']}. "
                f"Condición: {reception_data.get('condition', 'good')}."
            )
            
            if reception_data.get('notes'):
                notes += f" Notas: {reception_data['notes']}"
            
            inventory_change = InventoryChange(
                product_id=product.id,
                change_type='return_reception',
                size=return_transfer.size,
                quantity_before=quantity_before,
                quantity_after=product_size.quantity,
                user_id=warehouse_keeper_id,
                reference_id=return_id,
                notes=notes,
                created_at=datetime.now(),
                company_id=company_id
            )
            self.db.add(inventory_change)
            
            logger.info(f"   📝 Cambio registrado en InventoryChange")
            
            # ========== 9. ACTUALIZAR ESTADO DEL RETURN ==========
            return_transfer.status = 'completed'
            return_transfer.completed_at = datetime.now()
            return_transfer.reception_notes = reception_data.get('notes', 'Recibido correctamente')
            return_transfer.delivered_at = datetime.now()  # Asegurar que tenga fecha
            
            logger.info(f"   ✅ Estado actualizado: completed")
            
            # ========== 10. COMMIT ==========
            self.db.commit()
            
            logger.info(f"✅ Devolución #{return_id} procesada exitosamente")
            
            # ========== 11. CONSTRUIR RESPUESTA ==========
            return {
                "success": True,
                "message": "Devolución recibida y procesada correctamente",
                "return_id": return_id,
                "status": "completed",
                "inventory_restored": {
                    "product_reference": return_transfer.sneaker_reference_code,
                    "brand": return_transfer.brand,
                    "model": return_transfer.model,
                    "size": return_transfer.size,
                    "inventory_type": inventory_type,
                    "quantity_restored": reception_data['received_quantity'],
                    "quantity_before": quantity_before,
                    "quantity_after": product_size.quantity,
                    "location": destination_location_name
                },
                "reception_info": {
                    "received_by": warehouse_keeper_id,
                    "condition": reception_data.get('condition', 'good'),
                    "notes": reception_data.get('notes'),
                    "timestamp": datetime.now().isoformat()
                },
                "original_transfer_id": return_transfer.original_transfer_id,
                "timeline": {
                    "requested_at": return_transfer.requested_at.isoformat() if return_transfer.requested_at else None,
                    "accepted_at": return_transfer.accepted_at.isoformat() if return_transfer.accepted_at else None,
                    "delivered_at": return_transfer.delivered_at.isoformat() if return_transfer.delivered_at else None,
                    "completed_at": return_transfer.completed_at.isoformat()
                }
            }
            
        except ValueError as ve:
            # Errores de validación - no hacer rollback
            logger.error(f"❌ Error de validación: {str(ve)}")
            raise
            
        except Exception as e:
            # Errores inesperados - hacer rollback
            self.db.rollback()
            logger.exception(f"❌ Error crítico procesando recepción: {str(e)}")
            raise Exception(f"Error procesando recepción de devolución: {str(e)}")