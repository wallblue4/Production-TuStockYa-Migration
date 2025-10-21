# app/modules/classification/service.py
import httpx
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from .repository import ClassificationRepository
from .schemas import ProductMatch
from app.modules.inventory.service import InventoryService
import logging

logger = logging.getLogger(__name__)

class ClassificationService:
    def __init__(self, db: Session, company_id: int):
        self.db = db
        self.company_id = company_id
        self.repository = ClassificationRepository(db)
        self.microservice_url = "https://sneaker-api-v2.onrender.com"
    
    async def scan_product(
        self, 
        image: UploadFile, 
        current_user: Any, 
        include_transfer_options: bool = True
    ) -> Dict[str, Any]:
        """Procesar escaneo de producto con IA"""
        start_time = datetime.now()
        
        try:
            # Leer contenido de imagen
            content = await image.read()
            await image.seek(0)  # Reset file pointer
            
            # Intentar clasificación con microservicio
            classification_result = await self._call_classification_microservice(content)
            
            if classification_result:
                # Procesar resultados del microservicio
                processed_results = await self._process_classification_results(
                    classification_result, current_user, include_transfer_options
                )
            else:
                # Fallback si microservicio no disponible
                processed_results = await self._classification_fallback(current_user)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return {
                "success": True,
                "scan_timestamp": datetime.now().isoformat(),
                "scanned_by": {
                    "user_id": current_user.id,
                    "email": current_user.email,
                    "name": f"{current_user.first_name} {current_user.last_name}",
                    "role": current_user.role,
                    "location_id": current_user.location_id
                },
                "user_location": f"Local #{current_user.location_id}",
                "user_location_id": current_user.location_id,
                "results": processed_results,
                "availability_summary": self._calculate_availability_summary(processed_results),
                "processing_time_ms": round(processing_time, 2),
                "image_info": {
                    "filename": image.filename,
                    "size_bytes": len(content),
                    "content_type": image.content_type
                },
                "classification_service": {
                    "service": "microservice_integration",
                    "url": self.microservice_url,
                    "status": "available" if classification_result else "fallback"
                },
                "inventory_service": {
                    "source": "local_database",
                    "locations_searched": "all_active",
                    "include_transfer_options": include_transfer_options
                }
            }
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "Error procesando escaneo",
                    "details": str(e),
                    "processing_time_ms": round(processing_time, 2)
                }
            )
    
    async def _call_classification_microservice(self, image_content: bytes) -> Optional[Dict[str, Any]]:
        """Llamar al microservicio de clasificación"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                files = {"image": ("scan.jpg", image_content, "image/jpeg")}
                response = await client.post(
                    f"{self.microservice_url}/api/v2/classify",
                    files=files
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"Microservice error: {response.status_code}")
                    return None
                    
        except Exception as e:
            print(f"Error calling microservice: {e}")
            return None
    
    async def _process_classification_results(self, classification_result: Dict, current_user: Any, include_transfer_options: bool) -> Dict[str, Any]:
        """Procesar resultados de clasificación y agregar información de inventario"""
        results = classification_result.get('results', [])
        processed_matches = []
        
        for rank, result in enumerate(results[:5], 1):
            model_name = result.get('model_name', '')
            original_brand = result.get('brand', 'Unknown')
            
            # Extraer marca del model_name si es "Unknown"
            if original_brand == 'Unknown':
                final_brand = self._extract_brand_from_model(model_name)
            else:
                final_brand = original_brand
            
            # Buscar producto en inventario - FILTRADO POR COMPANY_ID
            local_products = self.repository.search_products_by_description(
                model_name=model_name,
                brand=final_brand,
                company_id=self.company_id
            )
            
            if local_products:
                # ✅ PRODUCTO ENCONTRADO EN INVENTARIO
                product = local_products[0]
                availability = self.repository.get_product_availability(
                    product['id'], f"Local #{current_user.location_id}", self.company_id
                )
                
                match = {
                    "rank": rank,
                    "similarity_score": result.get('similarity_score', 0.0),
                    "confidence_percentage": result.get('confidence_percentage', 0.0),
                    "confidence_level": result.get('confidence_level', 'low'),
                    "reference": {
                        "code": product['reference_code'],
                        "brand": product['brand'],
                        "model": product['model'],
                        "color": product['color_info'] or 'N/A',
                        "description": product['description'],
                        "photo": product['image_url'] or ""
                    },
                    "availability": self._format_availability(availability, include_transfer_options),
                    "locations": availability,
                    "pricing": {
                        "unit_price": product['unit_price'],
                        "box_price": product['box_price'],
                        "has_pricing": True
                    },
                    "classification_source": "microservice",
                    "inventory_source": "local_database",
                    "brand_extraction": {
                        "original_brand": original_brand,
                        "final_brand": product['brand'],
                        "extraction_method": "ai_classification"
                    },
                    "suggestions": self._get_product_suggestions(product),
                    "original_db_id": product['id'],
                    "image_path": product['image_url'] or ""
                }
            else:
                # ✅ PRODUCTO NO ENCONTRADO - CREAR RESULTADO BÁSICO DE CLASIFICACIÓN
                match = {
                    "rank": rank,
                    "similarity_score": result.get('similarity_score', 0.0),
                    "confidence_percentage": result.get('confidence_percentage', 0.0),
                    "confidence_level": result.get('confidence_level', 'low'),
                    "reference": {
                        "code": f"CLASSIFIED-{rank:03d}",
                        "brand": final_brand,
                        "model": model_name,
                        "color": result.get('color', 'Varios'),
                        "description": f"{final_brand} {model_name}",
                        "photo": result.get('image_url', f"https://via.placeholder.com/300x300?text={final_brand}+{model_name.replace(' ', '+')}")
                    },
                    "availability": {
                        "summary": {
                            "current_location": {"has_stock": False, "total_stock": 0},
                            "other_locations": {"has_stock": False, "total_stock": 0},
                            "total_system": {"total_stock": 0, "total_locations": 0}
                        },
                        "recommended_action": "Producto identificado - No disponible en inventario actual",
                        "can_sell_now": False,
                        "can_request_transfer": False
                    },
                    "locations": {
                        "current_location": [],
                        "other_locations": []
                    },
                    "pricing": {
                        "unit_price": 0.0,
                        "box_price": 0.0,
                        "has_pricing": False
                    },
                    "classification_source": "microservice",
                    "inventory_source": "not_in_current_inventory",
                    "brand_extraction": {
                        "original_brand": original_brand,
                        "final_brand": final_brand,
                        "extraction_method": "enhanced_analysis" if original_brand == "Unknown" else "microservice_direct"
                    },
                    "suggestions": {
                        "can_add_to_inventory": True,
                        "can_search_suppliers": True,
                        "similar_products_available": False
                    },
                    "original_db_id": result.get('original_db_id'),
                    "image_path": result.get('image_path', '')
                }
            
            processed_matches.append(match)  # ✅ SIEMPRE agregar, tenga o no inventario
        
        return {
            "best_match": processed_matches[0] if processed_matches else None,
            "alternative_matches": processed_matches[1:] if len(processed_matches) > 1 else [],
            "total_matches_found": len(processed_matches)
        }
    
    async def _classification_fallback(self, current_user: Any) -> Dict[str, Any]:
        """Fallback cuando microservicio no está disponible"""
        return {
            "best_match": None,
            "alternative_matches": [],
            "total_matches_found": 0
        }

    def _extract_brand_from_model(self, model_name: str) -> str:
        """Extraer marca del nombre del modelo"""
        known_brands = ['Nike', 'Adidas', 'Puma', 'Reebok', 'New Balance', 'Jordan', 'Converse']
        
        model_lower = model_name.lower()
        
        for brand in known_brands:
            if brand.lower() in model_lower:
                return brand
        
        # Si no encuentra marca conocida, buscar primera palabra
        first_word = model_name.split()[0] if model_name.split() else 'Unknown'
        return first_word.capitalize()
        
    def _format_availability(
        self, 
        availability: Dict, 
        include_transfer_options: bool
    ) -> Dict[str, Any]:
        """Formatear información de disponibilidad"""
        current_stock = sum(item['quantity'] for item in availability['current_location'])
        other_stock = sum(item['quantity'] for item in availability['other_locations'])
        
        return {
            "summary": {
                "current_location": {
                    "has_stock": current_stock > 0,
                    "total_stock": current_stock
                },
                "other_locations": {
                    "has_stock": other_stock > 0,
                    "total_stock": other_stock
                },
                "total_system": {
                    "total_stock": current_stock + other_stock,
                    "total_locations": len(set(
                        item['location'] for item in availability['other_locations']
                    )) + (1 if current_stock > 0 else 0)
                }
            },
            "recommended_action": (
                "Venta directa" if current_stock > 0 
                else ("Solicitar transferencia" if other_stock > 0 
                      else "Producto no disponible")
            ),
            "can_sell_now": current_stock > 0,
            "can_request_transfer": other_stock > 0 and include_transfer_options
        }
    
    def _get_product_suggestions(self, product: Dict) -> Dict[str, Any]:
        """Obtener sugerencias para el producto"""
        similar_products = self.repository.search_similar_products(
            product['brand'], 
            product['model'],
            company_id=self.company_id
        )
        
        return {
            "can_add_to_inventory": True,
            "can_search_suppliers": False,
            "similar_products_available": len(similar_products) > 0
        }
    
    def _calculate_availability_summary(self, results: Dict) -> Dict[str, Any]:
        """Calcular resumen de disponibilidad general"""
        if not results.get('best_match'):
            return {
                "products_available_locally": 0,
                "products_requiring_transfer": 0,
                "products_classified_only": 0,
                "can_sell_immediately": False,
                "transfer_options_available": False,
                "classification_successful": False
            }
        
        # Acceso directo a diccionario (ya convertido con model_dump())
        best_match = results['best_match']
        availability = best_match.get('availability', {})
        
        locally_available = 1 if availability.get('can_sell_now', False) else 0
        transfer_available = 1 if availability.get('can_request_transfer', False) else 0
        
        return {
            "products_available_locally": locally_available,
            "products_requiring_transfer": transfer_available,
            "products_classified_only": 1 if not locally_available and not transfer_available else 0,
            "can_sell_immediately": locally_available > 0,
            "transfer_options_available": transfer_available > 0,
            "classification_successful": True
        }
        
    def _extract_brand_from_model(self, model_name: str) -> str:
        """Extraer marca del nombre del modelo"""
        known_brands = ['Nike', 'Adidas', 'Puma', 'Reebok', 'New Balance', 'Jordan', 'Converse', 'Vans']
        
        model_lower = model_name.lower()
        
        for brand in known_brands:
            if brand.lower() in model_lower:
                return brand
        
        # Si no encuentra marca conocida, usar primera palabra
        first_word = model_name.split()[0] if model_name.split() else 'Unknown'
        return first_word.capitalize()

    async def scan_product_distributed(
        self, 
        image: UploadFile, 
        current_user: Any, 
        include_transfer_options: bool = True
    ) -> Dict[str, Any]:
        """
        Procesar escaneo de producto con IA incluyendo pies separados
        ✅ MEJORADO: Retorna información DETALLADA de TODAS las tallas
        """
        start_time = datetime.now()
        
        try:
            # Leer contenido de imagen
            content = await image.read()
            await image.seek(0)
            
            # Intentar clasificación con microservicio
            classification_result = await self._call_classification_microservice(content)
            
            if classification_result and classification_result.get('results'):
                # Procesar primer resultado (mejor match)
                best_match = classification_result['results'][0]
                model_name = best_match.get('model_name', '')
                brand = self._extract_brand_from_model(model_name) if best_match.get('brand') == 'Unknown' else best_match.get('brand')
                
                # Buscar producto en inventario
                local_products = self.repository.search_products_by_description(
                    model_name=model_name,
                    brand=brand,
                    company_id=self.company_id
                )
                
                if local_products:
                    product = local_products[0]
                    
                    # 🆕 OBTENER TODAS LAS TALLAS CON DISTRIBUCIÓN
                    product_sizes = self.repository.get_product_sizes(product['id'], self.company_id)
                    
                    if product_sizes:
                        # ✅ OBTENER TALLAS ÚNICAS
                        unique_sizes = sorted(list(set(ps['size'] for ps in product_sizes)))
                        
                        logger.info(f"📊 Procesando {len(unique_sizes)} tallas: {unique_sizes}")
                        
                        # ✅ OBTENER DISPONIBILIDAD DETALLADA DE CADA TALLA
                        inventory_service = InventoryService(self.db, self.company_id)
                        sizes_detailed = {}
                        
                        for size in unique_sizes:
                            logger.info(f"   🔍 Procesando talla {size}...")
                            
                            try:
                                size_info = await inventory_service.get_enhanced_availability(
                                    reference_code=product['reference_code'],
                                    size=size,
                                    user_location_id=current_user.location_id,
                                    user_id=current_user.id
                                )
                                sizes_detailed[size] = size_info
                                logger.info(f"   ✅ Talla {size} procesada")
                            except Exception as e:
                                logger.error(f"   ❌ Error procesando talla {size}: {str(e)}")
                                # Continuar con otras tallas si una falla
                                sizes_detailed[size] = {
                                    "error": str(e),
                                    "size": size
                                }
                        
                        # ✅ CALCULAR RESUMEN GLOBAL (TODAS LAS TALLAS)
                        global_summary = self._calculate_global_summary(sizes_detailed, current_user.location_id)
                        
                        processing_time = (datetime.now() - start_time).total_seconds() * 1000
                        
                        logger.info(f"✅ Scan completado en {processing_time:.2f}ms")
                        
                        # ✅ RESPUESTA COMPLETA CON TODAS LAS TALLAS
                        return {
                            "success": True,
                            "scan_timestamp": datetime.now().isoformat(),
                            "scanned_by": {
                                "user_id": current_user.id,
                                "email": current_user.email,
                                "name": f"{current_user.first_name} {current_user.last_name}",
                                "role": current_user.role,
                                "location_id": current_user.location_id
                            },
                            "classification": {
                                "confidence_score": best_match.get('similarity_score', 0),
                                "confidence_percentage": best_match.get('confidence_percentage', 0),
                                "model_detected": model_name,
                                "brand_detected": brand,
                                "classification_source": "microservice_ai"
                            },
                            "product": {
                                "product_id": product['id'],
                                "reference_code": product['reference_code'],
                                "brand": product['brand'],
                                "model": product['model'],
                                "description": product.get('description'),
                                "unit_price": product['unit_price'],
                                "box_price": product.get('box_price'),
                                "image_url": product.get('image_url')
                            },
                            
                            # ✅ INFORMACIÓN DETALLADA POR TALLA
                            "sizes": {
                                "available_sizes": unique_sizes,
                                "total_sizes": len(unique_sizes),
                                "detailed_by_size": sizes_detailed
                            },
                            
                            # ✅ RESUMEN GLOBAL (TODAS LAS TALLAS COMBINADAS)
                            "global_summary": global_summary,
                            
                            # ✅ DISTRIBUCIÓN COMPLETA (Para referencia rápida)
                            "distribution_matrix": product_sizes,
                            
                            "processing_time_ms": round(processing_time, 2)
                        }
            
            # Fallback si no se encuentra o microservicio no disponible
            return await self._classification_fallback(current_user)
        
        except Exception as e:
            logger.error(f"Error en scan_product: {str(e)}")
            logger.exception(e)
            raise HTTPException(500, f"Error al procesar escaneo: {str(e)}")


    # ✅ NUEVO MÉTODO: Calcular resumen global
    def _calculate_global_summary(
        self, 
        sizes_detailed: Dict[str, Any],
        user_location_id: int
    ) -> Dict[str, Any]:
        """
        Calcular resumen global combinando todas las tallas
        
        Args:
            sizes_detailed: Dict con información detallada de cada talla
            user_location_id: ID de ubicación del usuario
        
        Returns:
            Dict con resumen global combinado
        """
        
        # Inicializar contadores globales
        global_totals = {
            "pairs": 0,
            "left_feet": 0,
            "right_feet": 0,
            "formable_pairs": 0
        }
        
        local_totals = {
            "pairs": 0,
            "left_feet": 0,
            "right_feet": 0,
            "can_sell_pairs": 0
        }
        
        all_opportunities = []
        all_suggestions = []
        sizes_with_stock = []
        sizes_can_sell_now = []
        
        # Procesar cada talla
        for size, size_data in sizes_detailed.items():
            if 'error' in size_data:
                continue
            
            # Acumular totales globales
            if 'global_distribution' in size_data:
                dist = size_data['global_distribution']
                if 'totals' in dist:
                    totals = dist['totals']
                    global_totals['pairs'] += totals.get('pairs', 0)
                    global_totals['left_feet'] += totals.get('left_feet', 0)
                    global_totals['right_feet'] += totals.get('right_feet', 0)
                    global_totals['formable_pairs'] += totals.get('formable_pairs', 0)
            
            # Acumular disponibilidad local
            if 'local_availability' in size_data:
                local = size_data['local_availability']
                
                if 'pairs' in local and isinstance(local['pairs'], dict):
                    pairs_qty = local['pairs'].get('quantity', 0)
                    local_totals['pairs'] += pairs_qty
                    
                    if local['pairs'].get('can_sell', False):
                        local_totals['can_sell_pairs'] += pairs_qty
                        sizes_can_sell_now.append(size)
                
                if 'individual_feet' in local:
                    feet = local['individual_feet']
                    local_totals['left_feet'] += feet.get('left', {}).get('quantity', 0)
                    local_totals['right_feet'] += feet.get('right', {}).get('quantity', 0)
            
            # Recopilar oportunidades
            if 'formation_opportunities' in size_data:
                for opp in size_data['formation_opportunities']:
                    opp['size'] = size  # Agregar info de talla
                    all_opportunities.append(opp)
            
            # Recopilar sugerencias
            if 'suggestions' in size_data:
                for sugg in size_data['suggestions']:
                    if isinstance(sugg, dict):
                        sugg['size'] = size  # Agregar info de talla
                        all_suggestions.append(sugg)
            
            # Tallas con stock
            if global_totals['pairs'] > 0 or global_totals['left_feet'] > 0 or global_totals['right_feet'] > 0:
                sizes_with_stock.append(size)
        
        # Calcular eficiencia global
        total_potential_pairs = global_totals['pairs'] + global_totals['formable_pairs']
        efficiency = round((global_totals['pairs'] / total_potential_pairs * 100), 2) if total_potential_pairs > 0 else 100.0
        
        # Ordenar oportunidades por prioridad
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_opportunities.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))
        
        # Ordenar sugerencias por prioridad
        all_suggestions.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 3))
        
        return {
            "inventory_global": {
                "total_pairs": global_totals['pairs'],
                "total_left_feet": global_totals['left_feet'],
                "total_right_feet": global_totals['right_feet'],
                "formable_pairs": global_totals['formable_pairs'],
                "total_potential_pairs": total_potential_pairs,
                "efficiency_percentage": efficiency,
                "total_shoes": (global_totals['pairs'] * 2) + global_totals['left_feet'] + global_totals['right_feet']
            },
            
            "inventory_local": {
                "pairs_available": local_totals['pairs'],
                "pairs_can_sell": local_totals['can_sell_pairs'],
                "left_feet": local_totals['left_feet'],
                "right_feet": local_totals['right_feet'],
                "can_sell_immediately": local_totals['can_sell_pairs'] > 0
            },
            
            "sizes_summary": {
                "sizes_with_stock": sizes_with_stock,
                "sizes_can_sell_now": sizes_can_sell_now,
                "total_sizes_available": len(sizes_with_stock)
            },
            
            "all_formation_opportunities": all_opportunities,
            "total_opportunities": len(all_opportunities),
            
            "all_suggestions": all_suggestions[:10],  # Top 10 sugerencias
            "total_suggestions": len(all_suggestions)
        }