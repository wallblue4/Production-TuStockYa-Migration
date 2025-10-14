# app/modules/boss/__init__.py
"""
Módulo Boss - Funcionalidades del Director Ejecutivo

Este módulo implementa las funcionalidades específicas del rol BOSS:

- BS001: Visualizar dashboard ejecutivo con KPIs principales ✅
- BS002: Acceder a reportes de ventas consolidados (diario/mensual) ✅
- BS003: Consultar inventario total por categorías ✅
- BS004: Revisar costos operativos y márgenes de ganancia ✅
- BS005: Gestionar estructura organizacional (HEREDADO DE ADMIN) ✅
- BS008: Crear nuevos locales de venta ✅
- BS009: Crear nuevas bodegas ✅
- BS011: Asignar administradores (HEREDADO DE ADMIN) ✅

Arquitectura:
- router.py: Endpoints FastAPI específicos de Boss
- service.py: Lógica de negocio ejecutiva
- repository.py: Consultas consolidadas y agregaciones
- schemas.py: Modelos Pydantic de respuesta
"""

from .router import router as boss_router
from .service import BossService
from .repository import BossRepository

__all__ = [
    "boss_router",
    "BossService",
    "BossRepository"
]