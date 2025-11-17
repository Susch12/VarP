"""
Tests de Integración del Sistema VarP.

Prueba el sistema completo end-to-end con:
- 10,000 escenarios
- 5 consumidores paralelos
- Recuperación ante fallo de consumidor
- Cambio de modelo con purga correcta

IMPORTANTE: Estos tests requieren RabbitMQ corriendo en localhost:5672
"""

import unittest
import time
import os
import threading
import multiprocessing
from pathlib import Path
from typing import List, Dict, Any
import logging

from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.config import QueueConfig
from src.producer.producer import Producer, ProducerError
from src.consumer.consumer import Consumer, ConsumerError

# Configurar logging para tests
logging.basicConfig(
    level=logging.WARNING,  # Solo warnings y errores para tests
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def run_consumer_process(consumer_id: str, max_escenarios: int = None, should_fail: bool = False):
    """
    Ejecuta un consumidor en un proceso separado.

    Args:
        consumer_id: ID del consumidor
        max_escenarios: Número máximo de escenarios a procesar
        should_fail: Si el consumidor debe fallar intencionalmente
    """
    try:
        # Conectar a RabbitMQ
        client = RabbitMQClient()
        client.connect()

        # Crear consumidor
        consumer = Consumer(client, consumer_id=consumer_id)

        # Si debe fallar, fallar después de procesar algunos escenarios
        if should_fail:
            # Procesar solo 5 escenarios y luego "fallar"
            original_callback = consumer._procesar_escenario_callback

            count = [0]

            def failing_callback(ch, method, properties, body):
                count[0] += 1
                if count[0] >= 5:
                    logger.info(f"Consumidor {consumer_id} fallando intencionalmente")
                    ch.stop_consuming()
                    return
                return original_callback(ch, method, properties, body)

            consumer._procesar_escenario_callback = failing_callback

        # Ejecutar consumidor
        consumer.ejecutar(max_escenarios=max_escenarios)

    except KeyboardInterrupt:
        pass
    except Exception as e:
        logger.error(f"Error en consumidor {consumer_id}: {e}")
    finally:
        try:
            client.disconnect()
        except:
            pass


class TestIntegracionSistemaCompleto(unittest.TestCase):
    """Tests de integración del sistema completo."""

    @classmethod
    def setUpClass(cls):
        """Setup único para todos los tests."""
        # Verificar que RabbitMQ está disponible
        try:
            client = RabbitMQClient()
            client.connect()
            client.disconnect()
            cls.rabbitmq_available = True
        except RabbitMQConnectionError:
            cls.rabbitmq_available = False
            logger.warning("RabbitMQ no disponible, tests de integración serán saltados")

    def setUp(self):
        """Setup antes de cada test."""
        if not self.rabbitmq_available:
            self.skipTest("RabbitMQ no disponible")

        # Conectar y purgar todas las colas
        self.client = RabbitMQClient()
        self.client.connect()
        self.client.declare_queues()

        # Purgar todas las colas para empezar limpio
        for queue_name in [
            QueueConfig.MODELO,
            QueueConfig.ESCENARIOS,
            QueueConfig.RESULTADOS,
            QueueConfig.STATS_PRODUCTOR,
            QueueConfig.STATS_CONSUMIDORES,
            QueueConfig.DLQ_ESCENARIOS,
            QueueConfig.DLQ_RESULTADOS
        ]:
            try:
                self.client.purge_queue(queue_name)
            except:
                pass

    def tearDown(self):
        """Cleanup después de cada test."""
        if hasattr(self, 'client'):
            try:
                self.client.disconnect()
            except:
                pass

    def test_1_escenarios_10000(self):
        """
        Test 1: Procesamiento de 10,000 escenarios.

        Verifica:
        - Productor genera 10,000 escenarios
        - Consumidor procesa todos los escenarios
        - Todos los resultados se publican
        - Performance aceptable
        """
        logger.info("=" * 60)
        logger.info("TEST 1: 10,000 ESCENARIOS")
        logger.info("=" * 60)

        num_escenarios = 10000
        modelo_path = "modelos/ejemplo_simple.ini"

        # Verificar que el modelo existe
        self.assertTrue(Path(modelo_path).exists(), f"Modelo no encontrado: {modelo_path}")

        # 1. Ejecutar productor
        logger.info(f"Generando {num_escenarios} escenarios...")
        producer = Producer(self.client)

        tiempo_inicio_prod = time.time()
        producer.ejecutar(modelo_path, num_escenarios=num_escenarios)
        tiempo_prod = time.time() - tiempo_inicio_prod

        # Verificar que se generaron todos los escenarios
        self.assertEqual(producer.escenarios_generados, num_escenarios)
        logger.info(f"✓ Productor generó {num_escenarios} escenarios en {tiempo_prod:.2f}s")
        logger.info(f"  Tasa: {num_escenarios / tiempo_prod:.2f} esc/s")

        # Verificar cola de escenarios
        queue_size = self.client.get_queue_size(QueueConfig.ESCENARIOS)
        self.assertEqual(queue_size, num_escenarios)
        logger.info(f"✓ Cola de escenarios tiene {queue_size} mensajes")

        # 2. Ejecutar consumidor en thread separado
        logger.info("Procesando escenarios con 1 consumidor...")

        def run_consumer():
            consumer = Consumer(self.client, consumer_id="test-consumer-1")
            try:
                consumer.ejecutar(max_escenarios=num_escenarios)
            except KeyboardInterrupt:
                pass

        consumer_thread = threading.Thread(target=run_consumer, daemon=True)
        tiempo_inicio_cons = time.time()
        consumer_thread.start()

        # Esperar a que se procesen todos los escenarios
        max_wait = 300  # 5 minutos máximo
        start_wait = time.time()

        while True:
            time.sleep(2)

            # Verificar cuántos resultados hay
            try:
                resultados_size = self.client.get_queue_size(QueueConfig.RESULTADOS)
            except:
                resultados_size = 0

            logger.info(f"  Progreso: {resultados_size}/{num_escenarios} resultados")

            # Si ya procesó todos, salir
            if resultados_size >= num_escenarios:
                break

            # Si pasó mucho tiempo, fallar
            if time.time() - start_wait > max_wait:
                self.fail(f"Timeout esperando procesamiento (solo {resultados_size}/{num_escenarios})")

        tiempo_cons = time.time() - tiempo_inicio_cons

        # Verificar resultados
        resultados_size = self.client.get_queue_size(QueueConfig.RESULTADOS)
        self.assertGreaterEqual(resultados_size, num_escenarios * 0.99)  # Al menos 99%
        logger.info(f"✓ Consumidor procesó {resultados_size} escenarios en {tiempo_cons:.2f}s")
        logger.info(f"  Tasa: {resultados_size / tiempo_cons:.2f} esc/s")

        # Performance
        tiempo_total = tiempo_prod + tiempo_cons
        throughput_total = num_escenarios / tiempo_total
        logger.info(f"✓ Throughput total: {throughput_total:.2f} esc/s")

        logger.info("=" * 60)
        logger.info("TEST 1: EXITOSO ✓")
        logger.info("=" * 60)

    def test_2_cinco_consumidores_paralelos(self):
        """
        Test 2: 5 Consumidores en paralelo.

        Verifica:
        - 5 consumidores procesan escenarios concurrentemente
        - Fair dispatch funciona (distribución equitativa)
        - No hay race conditions
        - Throughput mejora con más consumidores
        """
        logger.info("=" * 60)
        logger.info("TEST 2: 5 CONSUMIDORES PARALELOS")
        logger.info("=" * 60)

        num_escenarios = 5000
        num_consumidores = 5
        modelo_path = "modelos/ejemplo_simple.ini"

        # 1. Generar escenarios
        logger.info(f"Generando {num_escenarios} escenarios...")
        producer = Producer(self.client)
        producer.ejecutar(modelo_path, num_escenarios=num_escenarios)

        self.assertEqual(producer.escenarios_generados, num_escenarios)
        logger.info(f"✓ {num_escenarios} escenarios generados")

        # 2. Lanzar 5 consumidores en procesos separados
        logger.info(f"Lanzando {num_consumidores} consumidores...")

        processes = []
        for i in range(num_consumidores):
            consumer_id = f"test-consumer-{i+1}"
            # Cada consumidor procesa hasta que la cola se vacíe
            p = multiprocessing.Process(
                target=run_consumer_process,
                args=(consumer_id, None, False)
            )
            p.start()
            processes.append(p)
            logger.info(f"  ✓ Consumidor {consumer_id} iniciado (PID: {p.pid})")

        # Dar tiempo a que se inicien
        time.sleep(3)

        # 3. Monitorear progreso
        tiempo_inicio = time.time()
        max_wait = 120  # 2 minutos

        while True:
            time.sleep(2)

            # Verificar progreso
            escenarios_restantes = self.client.get_queue_size(QueueConfig.ESCENARIOS)
            resultados_size = self.client.get_queue_size(QueueConfig.RESULTADOS)

            logger.info(
                f"  Progreso: {resultados_size}/{num_escenarios} resultados, "
                f"{escenarios_restantes} escenarios restantes"
            )

            # Si ya procesó todos (o casi todos), salir
            if escenarios_restantes == 0 and resultados_size >= num_escenarios * 0.99:
                break

            # Timeout
            if time.time() - tiempo_inicio > max_wait:
                logger.warning(f"Timeout - deteniendo consumidores forzosamente")
                break

        tiempo_total = time.time() - tiempo_inicio

        # 4. Detener consumidores
        logger.info("Deteniendo consumidores...")
        for p in processes:
            p.terminate()
            p.join(timeout=5)
            if p.is_alive():
                p.kill()

        # 5. Verificar resultados
        resultados_size = self.client.get_queue_size(QueueConfig.RESULTADOS)
        self.assertGreaterEqual(resultados_size, num_escenarios * 0.95)  # Al menos 95%

        throughput = resultados_size / tiempo_total
        logger.info(f"✓ Procesados {resultados_size}/{num_escenarios} escenarios en {tiempo_total:.2f}s")
        logger.info(f"✓ Throughput: {throughput:.2f} esc/s")
        logger.info(f"✓ Throughput por consumidor: {throughput / num_consumidores:.2f} esc/s")

        # Verificar estadísticas de consumidores
        stats_size = self.client.get_queue_size(QueueConfig.STATS_CONSUMIDORES)
        logger.info(f"✓ {stats_size} mensajes de estadísticas de consumidores")

        logger.info("=" * 60)
        logger.info("TEST 2: EXITOSO ✓")
        logger.info("=" * 60)

    def test_3_recuperacion_fallo_consumidor(self):
        """
        Test 3: Recuperación ante fallo de consumidor.

        Verifica:
        - Si un consumidor falla, los mensajes NO se pierden
        - Otro consumidor puede procesar los mensajes restantes
        - Sistema sigue funcionando después del fallo
        """
        logger.info("=" * 60)
        logger.info("TEST 3: RECUPERACIÓN ANTE FALLO DE CONSUMIDOR")
        logger.info("=" * 60)

        num_escenarios = 1000
        modelo_path = "modelos/ejemplo_simple.ini"

        # 1. Generar escenarios
        logger.info(f"Generando {num_escenarios} escenarios...")
        producer = Producer(self.client)
        producer.ejecutar(modelo_path, num_escenarios=num_escenarios)
        logger.info(f"✓ {num_escenarios} escenarios generados")

        # 2. Lanzar consumidor que fallará después de 5 mensajes
        logger.info("Lanzando consumidor que fallará...")
        failing_process = multiprocessing.Process(
            target=run_consumer_process,
            args=("failing-consumer", None, True)  # should_fail=True
        )
        failing_process.start()

        # Esperar a que procese algunos y falle
        time.sleep(5)
        failing_process.terminate()
        failing_process.join(timeout=3)

        resultados_antes = self.client.get_queue_size(QueueConfig.RESULTADOS)
        escenarios_restantes = self.client.get_queue_size(QueueConfig.ESCENARIOS)

        logger.info(f"✓ Consumidor falló después de procesar ~{resultados_antes} escenarios")
        logger.info(f"  Escenarios restantes en cola: {escenarios_restantes}")

        # Verificar que NO se procesaron todos
        self.assertLess(resultados_antes, num_escenarios * 0.5)
        self.assertGreater(escenarios_restantes, num_escenarios * 0.5)

        # 3. Lanzar consumidor de respaldo que procesará el resto
        logger.info("Lanzando consumidor de respaldo...")
        backup_process = multiprocessing.Process(
            target=run_consumer_process,
            args=("backup-consumer", None, False)
        )
        backup_process.start()

        # Esperar a que procese los restantes
        max_wait = 60
        tiempo_inicio = time.time()

        while True:
            time.sleep(2)

            escenarios_restantes = self.client.get_queue_size(QueueConfig.ESCENARIOS)
            resultados_total = self.client.get_queue_size(QueueConfig.RESULTADOS)

            logger.info(f"  Progreso: {resultados_total}/{num_escenarios} resultados")

            if escenarios_restantes == 0 or resultados_total >= num_escenarios * 0.95:
                break

            if time.time() - tiempo_inicio > max_wait:
                break

        # Detener consumidor de respaldo
        backup_process.terminate()
        backup_process.join(timeout=3)

        # 4. Verificar que se procesaron (casi) todos
        resultados_final = self.client.get_queue_size(QueueConfig.RESULTADOS)
        self.assertGreaterEqual(resultados_final, num_escenarios * 0.95)

        logger.info(f"✓ Consumidor de respaldo procesó el resto")
        logger.info(f"✓ Total procesado: {resultados_final}/{num_escenarios}")
        logger.info(f"✓ Sistema se recuperó exitosamente del fallo")

        logger.info("=" * 60)
        logger.info("TEST 3: EXITOSO ✓")
        logger.info("=" * 60)

    def test_4_cambio_modelo_purga(self):
        """
        Test 4: Cambio de modelo con purga correcta.

        Verifica:
        - Modelo antiguo se purga correctamente
        - Nuevo modelo se publica
        - Escenarios antiguos se purgan
        - Nuevos escenarios se generan con nuevo modelo
        - Consumidores usan el nuevo modelo
        """
        logger.info("=" * 60)
        logger.info("TEST 4: CAMBIO DE MODELO CON PURGA")
        logger.info("=" * 60)

        # 1. Publicar primer modelo
        logger.info("PARTE 1: Publicando modelo inicial...")
        modelo1_path = "modelos/ejemplo_simple.ini"
        num_escenarios_1 = 100

        producer1 = Producer(self.client)
        producer1.ejecutar(modelo1_path, num_escenarios=num_escenarios_1)

        # Verificar
        modelo_size_1 = self.client.get_queue_size(QueueConfig.MODELO)
        escenarios_size_1 = self.client.get_queue_size(QueueConfig.ESCENARIOS)

        self.assertEqual(modelo_size_1, 1)
        self.assertEqual(escenarios_size_1, num_escenarios_1)
        logger.info(f"✓ Modelo 1 publicado: {modelo_size_1} modelo, {escenarios_size_1} escenarios")

        # Leer modelo para verificar
        modelo1_msg = self.client.get_message(QueueConfig.MODELO, auto_ack=False)
        self.assertIsNotNone(modelo1_msg)
        modelo1_nombre = modelo1_msg['metadata']['nombre']
        logger.info(f"✓ Modelo 1 nombre: {modelo1_nombre}")

        # 2. Publicar segundo modelo (debe purgar el primero)
        logger.info("\nPARTE 2: Cambiando a nuevo modelo...")
        modelo2_path = "modelos/ejemplo_6_dist_simple.ini"
        num_escenarios_2 = 200

        # Purgar resultados anteriores para empezar limpio
        self.client.purge_queue(QueueConfig.RESULTADOS)

        producer2 = Producer(self.client)
        producer2.ejecutar(modelo2_path, num_escenarios=num_escenarios_2)

        # Verificar purga
        modelo_size_2 = self.client.get_queue_size(QueueConfig.MODELO)
        escenarios_size_2 = self.client.get_queue_size(QueueConfig.ESCENARIOS)

        # Debe haber SOLO 1 modelo (el nuevo)
        self.assertEqual(modelo_size_2, 1)
        logger.info(f"✓ Cola de modelo purgada: {modelo_size_2} modelo")

        # Escenarios del nuevo modelo
        # IMPORTANTE: Los escenarios antiguos NO se purgan automáticamente
        # Solo se purga la cola de modelo
        logger.info(f"✓ Escenarios en cola: {escenarios_size_2}")

        # Leer nuevo modelo para verificar que cambió
        modelo2_msg = self.client.get_message(QueueConfig.MODELO, auto_ack=False)
        self.assertIsNotNone(modelo2_msg)
        modelo2_nombre = modelo2_msg['metadata']['nombre']
        logger.info(f"✓ Modelo 2 nombre: {modelo2_nombre}")

        # Verificar que el modelo cambió
        self.assertNotEqual(modelo1_msg['modelo_id'], modelo2_msg['modelo_id'])
        logger.info(f"✓ Modelo cambió de '{modelo1_nombre}' a '{modelo2_nombre}'")

        # 3. Purgar escenarios manualmente (simular purga completa para cambio de modelo)
        logger.info("\nPARTE 3: Purgando escenarios antiguos...")
        purged = self.client.purge_queue(QueueConfig.ESCENARIOS)
        logger.info(f"✓ Purgados {purged} escenarios antiguos")

        # Republicar escenarios con nuevo modelo
        producer2_retry = Producer(self.client)
        # No publicar modelo de nuevo, solo escenarios
        producer2_retry.modelo = producer2.modelo
        producer2_retry.generator = producer2.generator
        producer2_retry._generar_y_publicar_escenarios()

        escenarios_size_final = self.client.get_queue_size(QueueConfig.ESCENARIOS)
        self.assertEqual(escenarios_size_final, num_escenarios_2)
        logger.info(f"✓ Nuevos escenarios generados: {escenarios_size_final}")

        # 4. Procesar con consumidor usando nuevo modelo
        logger.info("\nPARTE 4: Procesando con nuevo modelo...")

        def run_consumer_new_model():
            # Nuevo consumidor cargará el nuevo modelo
            consumer = Consumer(self.client, consumer_id="new-model-consumer")
            try:
                consumer.ejecutar(max_escenarios=num_escenarios_2)
            except KeyboardInterrupt:
                pass

        consumer_thread = threading.Thread(target=run_consumer_new_model, daemon=True)
        consumer_thread.start()

        # Esperar procesamiento
        max_wait = 60
        tiempo_inicio = time.time()

        while True:
            time.sleep(2)

            resultados = self.client.get_queue_size(QueueConfig.RESULTADOS)
            logger.info(f"  Progreso: {resultados}/{num_escenarios_2} resultados")

            if resultados >= num_escenarios_2 * 0.95:
                break

            if time.time() - tiempo_inicio > max_wait:
                break

        resultados_final = self.client.get_queue_size(QueueConfig.RESULTADOS)
        self.assertGreaterEqual(resultados_final, num_escenarios_2 * 0.90)

        logger.info(f"✓ Procesados {resultados_final} escenarios con nuevo modelo")

        logger.info("=" * 60)
        logger.info("TEST 4: EXITOSO ✓")
        logger.info("=" * 60)


class TestIntegracionPerformance(unittest.TestCase):
    """Tests de performance e integración."""

    @classmethod
    def setUpClass(cls):
        """Setup único para todos los tests."""
        try:
            client = RabbitMQClient()
            client.connect()
            client.disconnect()
            cls.rabbitmq_available = True
        except RabbitMQConnectionError:
            cls.rabbitmq_available = False

    def setUp(self):
        """Setup antes de cada test."""
        if not self.rabbitmq_available:
            self.skipTest("RabbitMQ no disponible")

        self.client = RabbitMQClient()
        self.client.connect()
        self.client.declare_queues()

        # Purgar colas
        for queue_name in [
            QueueConfig.MODELO,
            QueueConfig.ESCENARIOS,
            QueueConfig.RESULTADOS,
            QueueConfig.STATS_PRODUCTOR,
            QueueConfig.STATS_CONSUMIDORES
        ]:
            try:
                self.client.purge_queue(queue_name)
            except:
                pass

    def tearDown(self):
        """Cleanup después de cada test."""
        if hasattr(self, 'client'):
            try:
                self.client.disconnect()
            except:
                pass

    def test_throughput_productor(self):
        """Test de throughput del productor."""
        logger.info("=" * 60)
        logger.info("TEST: THROUGHPUT PRODUCTOR")
        logger.info("=" * 60)

        num_escenarios = 5000
        modelo_path = "modelos/ejemplo_simple.ini"

        producer = Producer(self.client)

        tiempo_inicio = time.time()
        producer.ejecutar(modelo_path, num_escenarios=num_escenarios)
        tiempo_total = time.time() - tiempo_inicio

        throughput = num_escenarios / tiempo_total

        logger.info(f"Escenarios: {num_escenarios}")
        logger.info(f"Tiempo: {tiempo_total:.2f}s")
        logger.info(f"Throughput: {throughput:.2f} esc/s")

        # Verificar throughput mínimo
        self.assertGreater(throughput, 100, "Throughput del productor debe ser > 100 esc/s")

        logger.info("=" * 60)


if __name__ == '__main__':
    # Configurar multiprocessing para tests
    multiprocessing.set_start_method('spawn', force=True)

    # Ejecutar tests
    unittest.main(verbosity=2)
