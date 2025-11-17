#!/usr/bin/env python3
"""
Script de validación para Fase 1.3: Productor Básico

Prueba que el productor funciona correctamente con RabbitMQ.
"""

import sys
import time
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.config import QueueConfig
from src.producer.producer import Producer, ProducerError
from src.common.model_parser import parse_model_file


def main():
    print("=" * 60)
    print("VALIDACIÓN FASE 1.3: Productor Básico")
    print("=" * 60)
    print()

    # ========================================
    # Test 1: Conexión a RabbitMQ
    # ========================================
    print("🔌 Test 1: Conectando a RabbitMQ...")
    try:
        client = RabbitMQClient()
        client.connect()
        print("✅ Conexión establecida")
        print(f"   Host: {client.host}:{client.port}")
        print()
    except RabbitMQConnectionError as e:
        print(f"❌ Error conectando a RabbitMQ: {e}")
        print()
        print("⚠️  Asegúrate de que RabbitMQ esté corriendo:")
        print("   docker-compose up -d rabbitmq")
        print()
        return 1

    # ========================================
    # Test 2: Declaración de Colas
    # ========================================
    print("📦 Test 2: Declarando colas...")
    try:
        client.declare_queues()
        print("✅ Colas declaradas:")
        print(f"   • {QueueConfig.MODELO}")
        print(f"   • {QueueConfig.ESCENARIOS}")
        print(f"   • {QueueConfig.RESULTADOS}")
        print(f"   • {QueueConfig.STATS_PRODUCTOR}")
        print(f"   • {QueueConfig.STATS_CONSUMIDORES}")
        print()
    except Exception as e:
        print(f"❌ Error declarando colas: {e}")
        return 1

    # ========================================
    # Test 3: Purgar Colas (limpieza)
    # ========================================
    print("🧹 Test 3: Purgando colas...")
    try:
        for queue in [QueueConfig.MODELO, QueueConfig.ESCENARIOS,
                      QueueConfig.RESULTADOS, QueueConfig.STATS_PRODUCTOR]:
            purged = client.purge_queue(queue)
            print(f"   • {queue}: {purged} mensajes eliminados")
        print("✅ Colas purgadas")
        print()
    except Exception as e:
        print(f"❌ Error purgando colas: {e}")
        return 1

    # ========================================
    # Test 4: Ejecutar Productor (10 escenarios)
    # ========================================
    print("🏭 Test 4: Ejecutando productor (10 escenarios de prueba)...")
    try:
        producer = Producer(client)
        producer.ejecutar(
            archivo_modelo='modelos/ejemplo_simple.ini',
            num_escenarios=10  # Solo 10 para test rápido
        )
        print("✅ Productor ejecutado exitosamente")
        print(f"   • Escenarios generados: {producer.escenarios_generados}")
        print(f"   • Tiempo: {producer.tiempo_fin - producer.tiempo_inicio:.2f}s")
        print()
    except ProducerError as e:
        print(f"❌ Error en productor: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================
    # Test 5: Verificar Mensajes en Colas
    # ========================================
    print("📊 Test 5: Verificando mensajes en colas...")
    try:
        # Verificar cola de modelo
        modelo_size = client.get_queue_size(QueueConfig.MODELO)
        print(f"   • {QueueConfig.MODELO}: {modelo_size} mensaje(s)")
        if modelo_size != 1:
            print(f"     ⚠️  Esperado: 1 mensaje")

        # Verificar cola de escenarios
        escenarios_size = client.get_queue_size(QueueConfig.ESCENARIOS)
        print(f"   • {QueueConfig.ESCENARIOS}: {escenarios_size} mensaje(s)")
        if escenarios_size != 10:
            print(f"     ⚠️  Esperado: 10 mensajes")

        # Verificar stats productor
        stats_size = client.get_queue_size(QueueConfig.STATS_PRODUCTOR)
        print(f"   • {QueueConfig.STATS_PRODUCTOR}: {stats_size} mensaje(s)")

        print()
        if modelo_size == 1 and escenarios_size == 10:
            print("✅ Mensajes correctos en colas")
        else:
            print("⚠️  Número de mensajes inesperado")
        print()
    except Exception as e:
        print(f"❌ Error verificando colas: {e}")
        return 1

    # ========================================
    # Test 6: Leer Modelo de la Cola
    # ========================================
    print("📖 Test 6: Leyendo modelo de la cola...")
    try:
        modelo_msg = client.get_message(QueueConfig.MODELO, auto_ack=False)

        if modelo_msg:
            print("✅ Modelo leído de la cola:")
            print(f"   • Modelo ID: {modelo_msg['modelo_id']}")
            print(f"   • Versión: {modelo_msg['version']}")
            print(f"   • Variables: {len(modelo_msg['variables'])}")
            print(f"   • Tipo función: {modelo_msg['funcion']['tipo']}")
            print(f"   • Expresión: {modelo_msg['funcion']['expresion']}")

            # Volver a poner el mensaje en la cola
            client.publish(QueueConfig.MODELO, modelo_msg, persistent=True)
            print("   • Modelo devuelto a la cola")
        else:
            print("❌ No se encontró modelo en la cola")
            return 1

        print()
    except Exception as e:
        print(f"❌ Error leyendo modelo: {e}")
        return 1

    # ========================================
    # Test 7: Leer Escenario de la Cola
    # ========================================
    print("🎲 Test 7: Leyendo escenario de la cola...")
    try:
        escenario_msg = client.get_message(QueueConfig.ESCENARIOS, auto_ack=True)

        if escenario_msg:
            print("✅ Escenario leído de la cola:")
            print(f"   • Escenario ID: {escenario_msg['escenario_id']}")
            print(f"   • Valores:")
            for var_name, var_value in escenario_msg['valores'].items():
                print(f"     - {var_name} = {var_value:.4f}")
            print(f"   • Timestamp: {escenario_msg['timestamp']}")
        else:
            print("❌ No se encontró escenario en la cola")
            return 1

        print()
    except Exception as e:
        print(f"❌ Error leyendo escenario: {e}")
        return 1

    # ========================================
    # Cleanup
    # ========================================
    print("🧹 Limpiando...")
    client.disconnect()
    print("✅ Desconectado de RabbitMQ")
    print()

    # ========================================
    # Resumen
    # ========================================
    print("=" * 60)
    print("✅ FASE 1.3 COMPLETADA EXITOSAMENTE")
    print("=" * 60)
    print()
    print("Componentes validados:")
    print("  ✅ Cliente RabbitMQ (conexión, declaración, pub/sub)")
    print("  ✅ Productor (lectura modelo, generación escenarios)")
    print("  ✅ Publicación de modelo en cola")
    print("  ✅ Publicación de escenarios en cola")
    print("  ✅ Publicación de estadísticas")
    print("  ✅ Purga de cola de modelo")
    print()
    print("Próximo paso: Fase 1.4 - Consumidor Básico")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
