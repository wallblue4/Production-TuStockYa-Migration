# app/modules/superadmin/__init__.py
"""
Módulo Superadmin - Administración Global del Sistema SaaS

Este módulo maneja la administración completa del sistema multitenant:
- SU001: Crear y configurar cuentas empresariales
- SU002: Gestionar suscripciones y facturación automática
- SU003: Monitorear métricas globales de todos los clientes
- SU004: Configurar notificaciones de vencimiento de suscripciones
- SU005: Suspender/activar servicios por incumplimiento de pago
- SU006: Generar reportes financieros consolidados

Características:
- Gestión de empresas (Companies/Tenants)
- Administración de planes de suscripción
- Control de facturación y pagos
- Monitoreo de métricas globales
- Activación/suspensión de servicios

Arquitectura:
- router.py: Endpoints exclusivos para superadmin
- service.py: Lógica de negocio de administración global
- repository.py: Acceso a datos de todas las empresas
- schemas.py: Modelos de request/response

Seguridad:
- Solo accesible por usuarios con rol 'superadmin'
- No requiere company_id (opera globalmente)
- Auditoría completa de todas las acciones
"""

from .router import router
from .service import SuperadminService
from .repository import SuperadminRepository

__all__ = [
    "router",
    "SuperadminService", 
    "SuperadminRepository"
]