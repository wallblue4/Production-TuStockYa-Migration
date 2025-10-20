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

    async def scan_product(
        self, 
        image: UploadFile, 
        current_user: Any, 
        include_transfer_options: bool = True
    ) -> Dict[str, Any]:
        """
        Procesar escaneo de producto con IA
        
        ACTUALIZADO: Ahora incluye información de pies separados
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
                    
                    # 🆕 USAR SERVICIO DE INVENTARIO MEJORADO
                    inventory_service = InventoryService(self.db, self.company_id)
                    
                    # Obtener disponibilidad mejorada
                    # Asumir que queremos la primera talla disponible
                    product_sizes = self.repository.get_product_sizes(product['id'], self.company_id)
                    
                    if product_sizes:
                        # Tomar primera talla como ejemplo (en producción, el vendedor podría seleccionar)
                        first_size = product_sizes[0].size
                        
                        enhanced_availability = await inventory_service.get_enhanced_availability(
                            reference_code=product['reference_code'],
                            size=first_size,
                            user_location_id=current_user.location_id,
                            user_id=current_user.id
                        )
                        
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
                            "classification": {
                                "confidence_score": best_match.get('similarity_score', 0),
                                "confidence_percentage": best_match.get('confidence_percentage', 0),
                                "model_detected": model_name,
                                "brand_detected": brand
                            },
                            "product": enhanced_availability.get('product'),
                            "local_availability": enhanced_availability.get('local_availability'),
                            "global_distribution": enhanced_availability.get('global_distribution'),
                            "formation_opportunities": enhanced_availability.get('formation_opportunities', []),
                            "suggestions": enhanced_availability.get('suggestions', []),
                            "all_sizes": [
                                {
                                    "size": ps.size,
                                    "inventory_type": ps.inventory_type,
                                    "quantity": ps.quantity
                                }
                                for ps in product_sizes
                            ],
                            "processing_time_ms": round(processing_time, 2)
                        }
                
                # Si no se encuentra en inventario, respuesta básica de clasificación
                return await self._classification_fallback(current_user, classification_result)
            
            # Fallback si microservicio no disponible
            return await self._classification_fallback(current_user)
        
        except Exception as e:
            logger.error(f"Error en scan_product: {str(e)}")
            logger.exception(e)
            raise HTTPException(500, f"Error al procesar escaneo: {str(e)}")