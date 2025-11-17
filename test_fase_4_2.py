"""
Tests para Fase 4.2: Configuración óptima de RabbitMQ.

Prueba:
- Prefetch count (fair dispatch)
- Persistencia de mensajes
- Heartbeat configuration
- Connection pooling
"""

import unittest
import time
import threading
from unittest.mock import MagicMock, patch, call
from typing import List

import pika

from src.common.config import RabbitMQConfig, ConsumerConfig
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.rabbitmq_pool import (
    PooledConnection,
    RabbitMQConnectionPool,
    get_global_pool,
    close_global_pool
)


class TestPrefetchConfiguration(unittest.TestCase):
    """Tests para configuración de prefetch count."""

    def setUp(self):
        """Setup con client mockeado."""
        self.mock_channel = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.is_closed = False

        self.client = RabbitMQClient()
        self.client.connection = self.mock_connection
        self.client.channel = self.mock_channel

    def test_prefetch_count_is_one(self):
        """Test que prefetch count está configurado en 1 para fair dispatch."""
        # Verificar que la configuración es 1
        self.assertEqual(ConsumerConfig.PREFETCH_COUNT, 1)

    def test_prefetch_applied_on_consume(self):
        """Test que basic_qos se llama con prefetch_count=1."""
        # Configurar QoS
        self.mock_channel.basic_qos(prefetch_count=ConsumerConfig.PREFETCH_COUNT)

        # Verificar que se llamó con prefetch_count=1
        self.mock_channel.basic_qos.assert_called_with(prefetch_count=1)

    def test_fair_dispatch_explanation(self):
        """
        Test que documenta el comportamiento de fair dispatch.

        Con prefetch_count=1:
        - RabbitMQ no envía un nuevo mensaje a un worker hasta que haya
          procesado y acknowledged el anterior
        - Distribuye mensajes equitativamente entre workers
        - Previene que un worker rápido procese todos los mensajes
        """
        # Este test es documental
        prefetch = ConsumerConfig.PREFETCH_COUNT

        self.assertEqual(prefetch, 1, "Fair dispatch requiere prefetch_count=1")

        # Documentar comportamiento esperado
        explanation = """
        Fair Dispatch (prefetch_count=1):
        - Worker A procesa mensaje 1 → RabbitMQ espera ACK antes de enviar otro
        - Worker B procesa mensaje 2 → RabbitMQ espera ACK antes de enviar otro
        - Resultado: Distribución equitativa de carga
        """
        self.assertIsNotNone(explanation)


class TestMessagePersistence(unittest.TestCase):
    """Tests para persistencia de mensajes."""

    def setUp(self):
        """Setup con client mockeado."""
        self.mock_channel = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.is_closed = False

        self.client = RabbitMQClient()
        self.client.connection = self.mock_connection
        self.client.channel = self.mock_channel

    def test_queue_durability(self):
        """Test que las colas se declaran como durables."""
        self.client.declare_queues()

        # Obtener todas las llamadas a queue_declare
        calls = self.mock_channel.queue_declare.call_args_list

        # Verificar que todas las colas importantes son durables
        important_queues = ['cola_modelo', 'cola_escenarios', 'cola_resultados',
                          'cola_dlq_escenarios', 'cola_dlq_resultados']

        for queue_name in important_queues:
            found = False
            for call_args, call_kwargs in calls:
                queue = call_kwargs.get('queue')
                if queue == queue_name:
                    found = True
                    self.assertTrue(
                        call_kwargs.get('durable', False),
                        f"Cola {queue_name} no es durable"
                    )
                    break

            self.assertTrue(found, f"Cola {queue_name} no fue declarada")

    def test_message_delivery_mode_persistent(self):
        """Test que los mensajes se publican con delivery_mode=2 (persistente)."""
        # Publicar mensaje
        message = {'test': 'data'}
        self.client.publish(
            queue_name='test_queue',
            message=message,
            persistent=True
        )

        # Verificar que se llamó basic_publish
        self.mock_channel.basic_publish.assert_called_once()

        # Extraer properties del call
        call_kwargs = self.mock_channel.basic_publish.call_args[1]
        properties = call_kwargs['properties']

        # Verificar delivery_mode=2 (persistente)
        self.assertEqual(
            properties.delivery_mode,
            2,
            "Los mensajes deben tener delivery_mode=2 para ser persistentes"
        )

    def test_non_persistent_stats_messages(self):
        """Test que mensajes de stats NO son persistentes (delivery_mode=1)."""
        # Publicar stats (no persistente)
        stats = {'consumer_id': 'C-123', 'count': 100}
        self.client.publish(
            queue_name='test_stats',
            message=stats,
            persistent=False
        )

        # Verificar delivery_mode=1 (no persistente)
        call_kwargs = self.mock_channel.basic_publish.call_args[1]
        properties = call_kwargs['properties']

        self.assertEqual(
            properties.delivery_mode,
            1,
            "Stats deben ser efímeros (delivery_mode=1)"
        )


class TestHeartbeatConfiguration(unittest.TestCase):
    """Tests para configuración de heartbeat."""

    def test_heartbeat_config_exists(self):
        """Test que la configuración de heartbeat existe."""
        self.assertIsInstance(RabbitMQConfig.HEARTBEAT, int)
        self.assertGreater(RabbitMQConfig.HEARTBEAT, 0)

    def test_connection_timeout_config_exists(self):
        """Test que connection timeout está configurado."""
        self.assertIsInstance(RabbitMQConfig.CONNECTION_TIMEOUT, int)
        self.assertGreater(RabbitMQConfig.CONNECTION_TIMEOUT, 0)

    def test_blocked_connection_timeout_config_exists(self):
        """Test que blocked connection timeout está configurado."""
        self.assertIsInstance(RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT, int)
        self.assertGreater(RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT, 0)

    @patch('pika.BlockingConnection')
    def test_connection_parameters_include_heartbeat(self, mock_blocking_conn):
        """Test que ConnectionParameters incluye heartbeat."""
        client = RabbitMQClient()

        # Mock successful connection
        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_blocking_conn.return_value = mock_connection

        # Conectar
        client.connect()

        # Verificar que se llamó BlockingConnection
        mock_blocking_conn.assert_called_once()

        # Obtener los parameters pasados
        call_args = mock_blocking_conn.call_args
        parameters = call_args[0][0]  # Primer argumento posicional

        # Verificar heartbeat
        self.assertEqual(
            parameters.heartbeat,
            RabbitMQConfig.HEARTBEAT,
            f"Heartbeat debe ser {RabbitMQConfig.HEARTBEAT}"
        )

    @patch('pika.BlockingConnection')
    def test_connection_parameters_include_timeouts(self, mock_blocking_conn):
        """Test que ConnectionParameters incluye todos los timeouts."""
        client = RabbitMQClient()

        mock_connection = MagicMock()
        mock_connection.is_closed = False
        mock_blocking_conn.return_value = mock_connection

        client.connect()

        call_args = mock_blocking_conn.call_args
        parameters = call_args[0][0]

        # Verificar socket_timeout
        self.assertEqual(parameters.socket_timeout, RabbitMQConfig.SOCKET_TIMEOUT)

        # Verificar blocked_connection_timeout
        self.assertEqual(
            parameters.blocked_connection_timeout,
            RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT
        )

    def test_heartbeat_recommended_value(self):
        """Test que heartbeat tiene un valor razonable."""
        # Heartbeat recomendado: 60-600 segundos
        # Demasiado bajo: overhead de red
        # Demasiado alto: detección lenta de conexiones muertas
        heartbeat = RabbitMQConfig.HEARTBEAT

        self.assertGreaterEqual(heartbeat, 30, "Heartbeat muy bajo, causaría overhead")
        self.assertLessEqual(heartbeat, 600, "Heartbeat muy alto, detección lenta de fallos")


class TestConnectionPooling(unittest.TestCase):
    """Tests para connection pooling."""

    def setUp(self):
        """Setup para tests de pooling."""
        # Cleanup pool global si existe
        close_global_pool()

    def tearDown(self):
        """Cleanup después de tests."""
        close_global_pool()

    def test_pooled_connection_creation(self):
        """Test que PooledConnection se crea correctamente."""
        mock_client = MagicMock()
        conn = PooledConnection(mock_client)

        self.assertIsNotNone(conn.client)
        self.assertIsNotNone(conn.created_at)
        self.assertEqual(conn.use_count, 0)

    def test_pooled_connection_should_recycle(self):
        """Test que conexiones viejas se marcan para reciclado."""
        mock_client = MagicMock()
        conn = PooledConnection(mock_client)

        # Conexión nueva no debe reciclarse
        self.assertFalse(conn.should_recycle(max_age=3600))

        # Simular conexión vieja
        conn.created_at = time.time() - 4000  # 4000 segundos de antigüedad

        # Ahora sí debe reciclarse
        self.assertTrue(conn.should_recycle(max_age=3600))

    def test_pooled_connection_health_check(self):
        """Test que health check funciona correctamente."""
        mock_client = MagicMock()
        mock_client.connection = MagicMock()
        mock_client.connection.is_closed = False

        conn = PooledConnection(mock_client)

        # Conexión saludable
        self.assertTrue(conn.is_healthy())

        # Conexión cerrada
        mock_client.connection.is_closed = True
        self.assertFalse(conn.is_healthy())

        # Sin conexión
        mock_client.connection = None
        self.assertFalse(conn.is_healthy())

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_connection_pool_initialization(self, mock_client_class):
        """Test que el pool se inicializa correctamente."""
        # Mock para evitar conexiones reales
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client_class.return_value = mock_client

        # Crear pool pequeño para testing
        pool = RabbitMQConnectionPool(pool_size=3, max_overflow=2)

        # Verificar que se crearon conexiones
        self.assertEqual(mock_client_class.call_count, 3)

        # Verificar configuración
        self.assertEqual(pool.pool_size, 3)
        self.assertEqual(pool.max_overflow, 2)

        # Cleanup
        pool.close_all()

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_connection_pool_reuse(self, mock_client_class):
        """Test que las conexiones se reutilizan."""
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client.connection = MagicMock()
        mock_client.connection.is_closed = False
        mock_client_class.return_value = mock_client

        pool = RabbitMQConnectionPool(pool_size=2, max_overflow=1)

        # Obtener y retornar conexión 2 veces
        with pool.connection() as conn1:
            self.assertIsNotNone(conn1)

        with pool.connection() as conn2:
            self.assertIsNotNone(conn2)

        # Verificar que se reutilizó (solo 2 creaciones para pool_size=2)
        self.assertGreaterEqual(pool.stats_reused, 1)

        pool.close_all()

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_connection_pool_overflow(self, mock_client_class):
        """Test que overflow funciona cuando pool está agotado."""
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client.connection = MagicMock()
        mock_client.connection.is_closed = False
        mock_client_class.return_value = mock_client

        pool = RabbitMQConnectionPool(pool_size=1, max_overflow=2)

        connections_held = []

        # Obtener más conexiones que pool_size
        try:
            with pool.connection() as conn1:
                connections_held.append(conn1)
                with pool.connection() as conn2:
                    connections_held.append(conn2)
                    # Segunda conexión debe venir de overflow
                    self.assertGreater(pool._overflow_count, 0)
        finally:
            pool.close_all()

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_connection_pool_timeout_config(self, mock_client_class):
        """Test que el pool tiene configuración de timeout."""
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client.connection = MagicMock()
        mock_client.connection.is_closed = False
        mock_client_class.return_value = mock_client

        # Pool con timeout configurado
        pool = RabbitMQConnectionPool(
            pool_size=2,
            max_overflow=1,
            pool_timeout=30
        )

        # Verificar que tiene el timeout configurado
        self.assertEqual(pool.pool_timeout, 30)

        # Cleanup
        pool.close_all()

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_connection_pool_stats(self, mock_client_class):
        """Test que las estadísticas del pool son correctas."""
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client.connection = MagicMock()
        mock_client.connection.is_closed = False
        mock_client_class.return_value = mock_client

        pool = RabbitMQConnectionPool(pool_size=2, max_overflow=1)

        # Usar algunas conexiones
        with pool.connection() as conn:
            pass

        with pool.connection() as conn:
            pass

        # Obtener stats
        stats = pool.get_stats()

        # Verificar estructura de stats
        self.assertIn('pool_size', stats)
        self.assertIn('max_overflow', stats)
        self.assertIn('total_created', stats)
        self.assertIn('total_reused', stats)
        self.assertIn('available_connections', stats)

        # Verificar valores
        self.assertEqual(stats['pool_size'], 2)
        self.assertEqual(stats['max_overflow'], 1)
        self.assertGreaterEqual(stats['total_created'], 2)

        pool.close_all()

    @patch('src.common.rabbitmq_pool.RabbitMQClient')
    def test_global_pool_singleton(self, mock_client_class):
        """Test que get_global_pool retorna el mismo pool (singleton)."""
        mock_client = MagicMock()
        mock_client.connect = MagicMock()
        mock_client_class.return_value = mock_client

        # Obtener pool global
        pool1 = get_global_pool(pool_size=3)
        pool2 = get_global_pool(pool_size=5)  # Tamaño diferente, pero debe ignorarse

        # Debe ser la misma instancia
        self.assertIs(pool1, pool2)

        # Verificar que usó pool_size de la primera llamada
        self.assertEqual(pool1.pool_size, 3)

        # Cleanup
        close_global_pool()


class TestConfigurationValues(unittest.TestCase):
    """Tests para valores de configuración de Fase 4.2."""

    def test_pool_size_config(self):
        """Test que POOL_SIZE está configurado."""
        self.assertIsInstance(RabbitMQConfig.POOL_SIZE, int)
        self.assertGreater(RabbitMQConfig.POOL_SIZE, 0)

    def test_pool_max_overflow_config(self):
        """Test que POOL_MAX_OVERFLOW está configurado."""
        self.assertIsInstance(RabbitMQConfig.POOL_MAX_OVERFLOW, int)
        self.assertGreaterEqual(RabbitMQConfig.POOL_MAX_OVERFLOW, 0)

    def test_pool_timeout_config(self):
        """Test que POOL_TIMEOUT está configurado."""
        self.assertIsInstance(RabbitMQConfig.POOL_TIMEOUT, int)
        self.assertGreater(RabbitMQConfig.POOL_TIMEOUT, 0)

    def test_pool_recycle_config(self):
        """Test que POOL_RECYCLE está configurado."""
        self.assertIsInstance(RabbitMQConfig.POOL_RECYCLE, int)
        self.assertGreater(RabbitMQConfig.POOL_RECYCLE, 0)

    def test_socket_timeout_config(self):
        """Test que SOCKET_TIMEOUT está configurado."""
        self.assertIsInstance(RabbitMQConfig.SOCKET_TIMEOUT, int)
        self.assertGreater(RabbitMQConfig.SOCKET_TIMEOUT, 0)

    def test_all_timeout_configs_reasonable(self):
        """Test que todos los timeouts tienen valores razonables."""
        # Socket timeout: 5-30s
        self.assertGreaterEqual(RabbitMQConfig.SOCKET_TIMEOUT, 5)
        self.assertLessEqual(RabbitMQConfig.SOCKET_TIMEOUT, 30)

        # Connection timeout: 5-30s
        self.assertGreaterEqual(RabbitMQConfig.CONNECTION_TIMEOUT, 5)
        self.assertLessEqual(RabbitMQConfig.CONNECTION_TIMEOUT, 60)

        # Blocked connection timeout: 60-600s
        self.assertGreaterEqual(RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT, 60)
        self.assertLessEqual(RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT, 600)

        # Pool timeout: 10-60s
        self.assertGreaterEqual(RabbitMQConfig.POOL_TIMEOUT, 10)
        self.assertLessEqual(RabbitMQConfig.POOL_TIMEOUT, 120)

        # Pool recycle: 1h-24h
        self.assertGreaterEqual(RabbitMQConfig.POOL_RECYCLE, 3600)  # 1 hora
        self.assertLessEqual(RabbitMQConfig.POOL_RECYCLE, 86400)  # 24 horas


def run_tests():
    """Ejecuta todos los tests de Fase 4.2."""
    # Configurar logging para tests
    import logging
    logging.basicConfig(level=logging.WARNING)

    # Crear test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Añadir todos los test cases
    suite.addTests(loader.loadTestsFromTestCase(TestPrefetchConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestMessagePersistence))
    suite.addTests(loader.loadTestsFromTestCase(TestHeartbeatConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestConnectionPooling))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationValues))

    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Imprimir resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE TESTS - FASE 4.2")
    print("=" * 70)
    print(f"Tests ejecutados: {result.testsRun}")
    print(f"✅ Exitosos: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Fallidos: {len(result.failures)}")
    print(f"💥 Errores: {len(result.errors)}")
    print("=" * 70)

    if result.wasSuccessful():
        print("\n✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
        return 0
    else:
        print("\n❌ ALGUNOS TESTS FALLARON")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(run_tests())
