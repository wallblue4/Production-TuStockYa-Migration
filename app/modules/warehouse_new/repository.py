from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class WarehouseRepository:
    
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
        
        # ==================== VALIDACIÓN 2: PRODUCTO EXISTE ====================
        logger.info(f"🔍 Buscando producto en inventario")
        
        # Construir nombre de ubicación
        location_name = f"Local #{transfer.source_location_id}"
        
        product_size = self.db.query(ProductSize).join(Product).filter(
            and_(
                Product.reference_code == transfer.sneaker_reference_code,
                ProductSize.size == transfer.size,
                ProductSize.location_name == location_name
            )
        ).with_for_update().first()  # ← LOCK: Evita descuento simultáneo
        
        if not product_size:
            logger.error(
                f"❌ Producto no encontrado: {transfer.sneaker_reference_code} "
                f"talla {transfer.size} en {location_name}"
            )
            raise ValueError(
                f"El producto {transfer.sneaker_reference_code} "
                f"talla {transfer.size} no existe en {location_name}. "
                f"Verifica que el producto esté correctamente registrado en el inventario."
            )
        
        logger.info(
            f"✅ Producto encontrado: stock actual = {product_size.quantity}"
        )
        
        # ==================== VALIDACIÓN 3: STOCK SUFICIENTE ====================
        logger.info(f"🔍 Validando stock suficiente")
        
        if product_size.quantity < transfer.quantity:
            logger.error(
                f"❌ Stock insuficiente: disponible={product_size.quantity}, "
                f"solicitado={transfer.quantity}"
            )
            raise ValueError(
                f"Stock insuficiente en {location_name}. "
                f"Solicitado: {transfer.quantity} unidades, "
                f"Disponible: {product_size.quantity} unidades. "
                f"Faltan: {transfer.quantity - product_size.quantity} unidades."
            )
        
        logger.info(f"✅ Stock suficiente para procesar")
        
        # ==================== VALIDACIÓN 4: CONCURRENCIA (SQL-LEVEL) ====================
        # Los locks with_for_update() ya previenen esto, pero agregamos
        # validación adicional a nivel SQL para máxima seguridad
        
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
                # Esto solo puede pasar si otra transacción modificó el stock
                # entre nuestra SELECT y UPDATE
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
            )
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
                "location": location_name
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