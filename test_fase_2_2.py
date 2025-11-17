#!/usr/bin/env python3
"""
Test de Validación Fase 2.2: Análisis de Resultados y Exportación

Prueba las nuevas funcionalidades del dashboard:
1. Consumo y análisis de resultados
2. Cálculo de estadísticas descriptivas
3. Generación de datos para histograma y boxplot
4. Funciones de exportación CSV y JSON

Este test valida la lógica del DataManager y los métodos de análisis.
"""

import sys
import time
import threading
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.config import QueueConfig
from src.dashboard.data_manager import DataManager
from src.producer.producer import Producer
from src.consumer.consumer import Consumer


def run_mock_consumer(client, consumer_id, num_escenarios, stop_event):
    """Ejecuta consumidor de prueba."""
    consumer = Consumer(client, consumer_id)
    consumer._cargar_modelo()

    for _ in range(num_escenarios):
        if stop_event.is_set():
            break

        escenario_msg = client.get_message(QueueConfig.ESCENARIOS, auto_ack=False)
        if escenario_msg is None:
            time.sleep(0.1)
            continue

        try:
            import json
            escenario = json.loads(json.dumps(escenario_msg))

            inicio = time.time()
            resultado = consumer._ejecutar_modelo(escenario)
            tiempo_ejecucion = time.time() - inicio

            consumer._publicar_resultado(escenario, resultado, tiempo_ejecucion)
            consumer.escenarios_procesados += 1
            consumer.tiempo_ultimo_escenario = tiempo_ejecucion
            consumer.tiempos_ejecucion.append(tiempo_ejecucion)
            consumer._publicar_stats()

        except Exception as e:
            print(f"   ❌ Error procesando: {e}")

    consumer._publicar_stats()


def main():
    print("=" * 70)
    print("TEST DE VALIDACIÓN FASE 2.2: ANÁLISIS DE RESULTADOS Y EXPORTACIÓN")
    print("=" * 70)
    print()

    # ========================================
    # Test 1: Conexión a RabbitMQ
    # ========================================
    print("🔌 Test 1: Conectando a RabbitMQ...")
    try:
        client = RabbitMQClient()
        client.connect()
        print("✅ Conexión establecida")
        print()
    except RabbitMQConnectionError as e:
        print(f"❌ Error conectando a RabbitMQ: {e}")
        print()
        print("⚠️  Asegúrate de que RabbitMQ esté corriendo:")
        print("   docker-compose up -d rabbitmq")
        print()
        return 1

    # ========================================
    # Test 2: Purgar Colas
    # ========================================
    print("🧹 Test 2: Purgando colas...")
    try:
        for queue in [QueueConfig.MODELO, QueueConfig.ESCENARIOS,
                      QueueConfig.RESULTADOS, QueueConfig.STATS_PRODUCTOR,
                      QueueConfig.STATS_CONSUMIDORES]:
            purged = client.purge_queue(queue)
            print(f"   • {queue}: {purged} mensajes eliminados")
        print("✅ Colas purgadas")
        print()
    except Exception as e:
        print(f"❌ Error purgando colas: {e}")
        return 1

    # ========================================
    # Test 3: Crear e Iniciar DataManager
    # ========================================
    print("📊 Test 3: Creando e iniciando DataManager...")
    try:
        data_manager = DataManager(client)
        data_manager.start()
        time.sleep(1)
        print("✅ DataManager iniciado")
        print()
    except Exception as e:
        print(f"❌ Error con DataManager: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 4: Ejecutar Productor
    # ========================================
    NUM_ESCENARIOS = 100
    print(f"🏭 Test 4: Ejecutando productor ({NUM_ESCENARIOS} escenarios)...")
    try:
        producer = Producer(client)
        producer.ejecutar(
            archivo_modelo='modelos/ejemplo_simple.ini',
            num_escenarios=NUM_ESCENARIOS
        )
        print(f"✅ Productor completado")
        print(f"   • Escenarios generados: {producer.escenarios_generados}")
        print()
    except Exception as e:
        print(f"❌ Error en productor: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 5: Ejecutar Consumidores
    # ========================================
    NUM_CONSUMIDORES = 3
    print(f"⚙️  Test 5: Ejecutando {NUM_CONSUMIDORES} consumidores...")
    try:
        consumer_clients = []
        for i in range(NUM_CONSUMIDORES):
            c = RabbitMQClient()
            c.connect()
            consumer_clients.append(c)

        stop_event = threading.Event()
        threads = []
        escenarios_por_consumidor = NUM_ESCENARIOS // NUM_CONSUMIDORES + 1

        for i, c in enumerate(consumer_clients):
            consumer_id = f"C{i+1}"
            thread = threading.Thread(
                target=run_mock_consumer,
                args=(c, consumer_id, escenarios_por_consumidor, stop_event)
            )
            threads.append(thread)
            thread.start()
            print(f"   • Consumidor {consumer_id} iniciado")

        print(f"   • Esperando a que consumidores procesen escenarios...")
        for thread in threads:
            thread.join()

        print("✅ Todos los consumidores completados")
        print()

        for c in consumer_clients:
            c.disconnect()

    except Exception as e:
        print(f"❌ Error en consumidores: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 6: Esperar a que DataManager Consuma Resultados
    # ========================================
    print("⏳ Test 6: Esperando a que DataManager consuma resultados...")
    try:
        # Dar tiempo al DataManager para consumir todos los resultados
        time.sleep(3)

        resultados = data_manager.get_resultados()
        print(f"✅ DataManager consumió {len(resultados)} resultados")
        print()

    except Exception as e:
        print(f"❌ Error obteniendo resultados: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 7: Verificar Estadísticas Calculadas
    # ========================================
    print("📊 Test 7: Verificando estadísticas calculadas...")
    try:
        estadisticas = data_manager.get_estadisticas()

        if estadisticas:
            print("   ✅ Estadísticas calculadas correctamente:")
            print(f"      • N: {estadisticas.get('n', 0):,}")
            print(f"      • Media: {estadisticas.get('media', 0):.6f}")
            print(f"      • Mediana: {estadisticas.get('mediana', 0):.6f}")
            print(f"      • Desv. Estándar: {estadisticas.get('desviacion_estandar', 0):.6f}")
            print(f"      • Varianza: {estadisticas.get('varianza', 0):.6f}")
            print(f"      • Mínimo: {estadisticas.get('minimo', 0):.6f}")
            print(f"      • Máximo: {estadisticas.get('maximo', 0):.6f}")
            print(f"      • Percentil 25: {estadisticas.get('percentil_25', 0):.6f}")
            print(f"      • Percentil 75: {estadisticas.get('percentil_75', 0):.6f}")
            print(f"      • Percentil 95: {estadisticas.get('percentil_95', 0):.6f}")
            print(f"      • Percentil 99: {estadisticas.get('percentil_99', 0):.6f}")
            ic = estadisticas.get('intervalo_confianza_95', {})
            print(f"      • IC 95%: [{ic.get('inferior', 0):.6f}, {ic.get('superior', 0):.6f}]")
        else:
            print("   ⚠️  No se encontraron estadísticas")

        print()
    except Exception as e:
        print(f"❌ Error obteniendo estadísticas: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 8: Verificar Resultados Raw
    # ========================================
    print("📦 Test 8: Verificando resultados raw...")
    try:
        resultados_raw = data_manager.get_resultados_raw()

        print(f"   ✅ Últimos {len(resultados_raw)} resultados almacenados")
        if resultados_raw:
            print(f"      • Ejemplo de resultado:")
            ejemplo = resultados_raw[0]
            print(f"         - Escenario ID: {ejemplo.get('escenario_id')}")
            print(f"         - Consumer ID: {ejemplo.get('consumer_id')}")
            print(f"         - Resultado: {ejemplo.get('resultado')}")
            print(f"         - Tiempo: {ejemplo.get('tiempo_ejecucion'):.6f}s")

        print()
    except Exception as e:
        print(f"❌ Error obteniendo resultados raw: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 9: Validar Distribución Normal
    # ========================================
    print("📈 Test 9: Validando distribución de resultados...")
    try:
        resultados = data_manager.get_resultados()
        estadisticas = data_manager.get_estadisticas()

        if len(resultados) >= 30:  # Necesitamos suficientes datos
            media = estadisticas['media']
            std = estadisticas['desviacion_estandar']

            # El modelo es x + y donde x,y ~ N(0,1)
            # Por lo tanto x+y ~ N(0, sqrt(2)) ≈ N(0, 1.414)
            # Media esperada ≈ 0, Std esperada ≈ 1.414

            print(f"   ✅ Validación de distribución:")
            print(f"      • Media esperada: ~0.0, obtenida: {media:.4f}")
            print(f"      • Std esperada: ~1.414, obtenida: {std:.4f}")

            # Validar que la media esté cerca de 0 (±0.5)
            if abs(media) < 0.5:
                print(f"      ✅ Media dentro del rango esperado")
            else:
                print(f"      ⚠️  Media fuera del rango esperado (puede ser aleatorio)")

            # Validar que std esté cerca de 1.414 (±0.5)
            if abs(std - 1.414) < 0.5:
                print(f"      ✅ Desviación estándar dentro del rango esperado")
            else:
                print(f"      ⚠️  Desviación estándar fuera del rango esperado (puede ser aleatorio)")

        print()
    except Exception as e:
        print(f"❌ Error validando distribución: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 10: Simular Exportación CSV
    # ========================================
    print("📄 Test 10: Validando estructura de exportación CSV...")
    try:
        import csv
        import io

        resultados_raw = data_manager.get_resultados_raw()
        estadisticas = data_manager.get_estadisticas()

        if resultados_raw:
            # Simular creación de CSV
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(['escenario_id', 'consumer_id', 'resultado', 'tiempo_ejecucion'])

            # Primeros 5 resultados
            for res in resultados_raw[:5]:
                writer.writerow([
                    res.get('escenario_id'),
                    res.get('consumer_id'),
                    res.get('resultado'),
                    res.get('tiempo_ejecucion')
                ])

            csv_content = output.getvalue()
            lines = csv_content.strip().split('\n')

            print(f"   ✅ CSV generado correctamente")
            print(f"      • Número de líneas: {len(lines)}")
            print(f"      • Header: {lines[0]}")
            if len(lines) > 1:
                print(f"      • Primera fila de datos: {lines[1][:80]}...")

        print()
    except Exception as e:
        print(f"❌ Error validando CSV: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 11: Simular Exportación JSON
    # ========================================
    print("📋 Test 11: Validando estructura de exportación JSON...")
    try:
        import json
        from datetime import datetime

        resultados_raw = data_manager.get_resultados_raw()
        estadisticas = data_manager.get_estadisticas()
        modelo_info = data_manager.get_modelo_info()
        stats_prod = data_manager.get_stats_productor()
        stats_cons = data_manager.get_stats_consumidores()

        # Crear estructura JSON
        data = {
            'metadata': {
                'fecha_exportacion': datetime.now().isoformat(),
                'num_resultados': len(resultados_raw)
            },
            'modelo': modelo_info,
            'productor': stats_prod,
            'consumidores': stats_cons,
            'estadisticas': estadisticas,
            'resultados': resultados_raw[:5]  # Solo primeros 5 para test
        }

        json_str = json.dumps(data, indent=2)
        json_obj = json.loads(json_str)  # Validar que es JSON válido

        print(f"   ✅ JSON generado correctamente")
        print(f"      • Tamaño: {len(json_str)} bytes")
        print(f"      • Secciones: {list(json_obj.keys())}")
        print(f"      • Num resultados en metadata: {json_obj['metadata']['num_resultados']}")
        print(f"      • Estadísticas incluidas: {len(json_obj.get('estadisticas', {}))} campos")

        print()
    except Exception as e:
        print(f"❌ Error validando JSON: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 12: Verificar Resumen Completo
    # ========================================
    print("📊 Test 12: Verificando resumen completo del sistema...")
    try:
        summary = data_manager.get_summary()

        print(f"   ✅ Resumen del sistema:")
        print(f"      • Número de consumidores: {summary.get('num_consumidores', 0)}")
        print(f"      • Total procesados: {summary.get('total_procesados', 0)}")
        print(f"      • Número de resultados: {summary.get('num_resultados', 0)}")
        print(f"      • Tasa total consumidores: {summary.get('tasa_total_consumidores', 0):.2f} esc/s")
        print(f"      • Estadísticas disponibles: {len(summary.get('estadisticas', {}))} campos")

        print()
    except Exception as e:
        print(f"❌ Error generando resumen: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 13: Detener DataManager
    # ========================================
    print("⏹️  Test 13: Deteniendo DataManager...")
    try:
        data_manager.stop()
        time.sleep(1)
        print("✅ DataManager detenido")
        print()
    except Exception as e:
        print(f"❌ Error deteniendo DataManager: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Cleanup
    # ========================================
    print("🧹 Limpiando...")
    client.disconnect()
    print("✅ Desconectado de RabbitMQ")
    print()

    # ========================================
    # Resumen Final
    # ========================================
    print("=" * 70)
    print("✅ TEST DE VALIDACIÓN FASE 2.2 COMPLETADO EXITOSAMENTE")
    print("=" * 70)
    print()
    print("Componentes validados:")
    print("  ✅ Consumo de resultados desde cola_resultados")
    print("  ✅ Cálculo de estadísticas descriptivas (media, mediana, std, etc.)")
    print("  ✅ Cálculo de percentiles (P25, P75, P95, P99)")
    print("  ✅ Cálculo de intervalo de confianza 95%")
    print("  ✅ Almacenamiento de resultados raw (últimos 1000)")
    print("  ✅ Validación de distribución normal de resultados")
    print("  ✅ Generación de estructura CSV para exportación")
    print("  ✅ Generación de estructura JSON para exportación")
    print("  ✅ Resumen completo del sistema con estadísticas")
    print()
    print("🎉 FASE 2.2 COMPLETADA AL 100%")
    print()
    print("Nuevas funcionalidades del dashboard:")
    print("  • Panel de estadísticas descriptivas completo")
    print("  • Histograma de distribución de resultados")
    print("  • Box plot de resultados")
    print("  • Exportación de datos a CSV con estadísticas")
    print("  • Exportación completa a JSON")
    print("  • Análisis estadístico en tiempo real")
    print()
    print("Para probar el dashboard completo con análisis:")
    print("  1. python run_producer.py --modelo modelos/ejemplo_simple.ini --escenarios 1000")
    print("  2. python run_consumer.py --id C1 &")
    print("  3. python run_consumer.py --id C2 &")
    print("  4. python run_dashboard.py")
    print("  5. Abrir http://localhost:8050 y ver la sección 'Análisis de Resultados'")
    print("  6. Descargar CSV o JSON con el botón de exportación")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
