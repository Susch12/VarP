"""
Tests para Fase 4.1: Manejo de errores avanzado.

Prueba:
- Dead Letter Queue (DLQ) configuradas correctamente
- Reintentos automáticos (máx 3 intentos)
- Logging estructurado
- Manejo de excepciones
- Estadísticas de errores
"""

import unittest
import time
import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from typing import Dict, Any

from src.common.config import QueueConfig, ConsumerConfig
from src.common.rabbitmq_client import RabbitMQClient
from src.consumer.consumer import Consumer, ConsumerError
from src.common.logging_config import setup_logging, StructuredFormatter, ColoredFormatter
from src.common.expression_evaluator import ExpressionEvaluationError
from src.common.python_executor import TimeoutException, SecurityException


class TestDLQConfiguration(unittest.TestCase):
    """Tests para configuración de Dead Letter Queues."""

    def setUp(self):
        """Setup con mock de RabbitMQ client."""
        self.mock_channel = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.is_closed = False

        # Create mock client
        self.client = RabbitMQClient()
        self.client.connection = self.mock_connection
        self.client.channel = self.mock_channel

    def test_dlq_queues_declared(self):
        """Test que las DLQ se declaran correctamente."""
        self.client.declare_queues()

        # Verificar que se llamó queue_declare para las DLQs
        calls = self.mock_channel.queue_declare.call_args_list

        # Buscar llamadas para DLQ
        dlq_escenarios_found = False
        dlq_resultados_found = False

        for call_args, call_kwargs in calls:
            queue = call_kwargs.get('queue') or (call_args[0] if call_args else None)
            if queue == QueueConfig.DLQ_ESCENARIOS:
                dlq_escenarios_found = True
                # Verificar que es durable
                self.assertTrue(call_kwargs.get('durable', False))
            elif queue == QueueConfig.DLQ_RESULTADOS:
                dlq_resultados_found = True
                self.assertTrue(call_kwargs.get('durable', False))

        self.assertTrue(dlq_escenarios_found, "DLQ de escenarios no fue declarada")
        self.assertTrue(dlq_resultados_found, "DLQ de resultados no fue declarada")

    def test_escenarios_queue_configured_with_dlq(self):
        """Test que cola de escenarios está configurada con DLQ."""
        self.client.declare_queues()

        # Buscar la declaración de cola_escenarios
        calls = self.mock_channel.queue_declare.call_args_list

        escenarios_config = None
        for call_args, call_kwargs in calls:
            queue = call_kwargs.get('queue') or (call_args[0] if call_args else None)
            if queue == QueueConfig.ESCENARIOS:
                escenarios_config = call_kwargs
                break

        self.assertIsNotNone(escenarios_config, "Cola de escenarios no fue declarada")

        # Verificar argumentos de DLQ
        arguments = escenarios_config.get('arguments', {})
        self.assertEqual(
            arguments.get('x-dead-letter-exchange'),
            '',
            "Dead letter exchange no configurado correctamente"
        )
        self.assertEqual(
            arguments.get('x-dead-letter-routing-key'),
            QueueConfig.DLQ_ESCENARIOS,
            "Dead letter routing key no configurado correctamente"
        )

    def test_resultados_queue_configured_with_dlq(self):
        """Test que cola de resultados está configurada con DLQ."""
        self.client.declare_queues()

        calls = self.mock_channel.queue_declare.call_args_list

        resultados_config = None
        for call_args, call_kwargs in calls:
            queue = call_kwargs.get('queue') or (call_args[0] if call_args else None)
            if queue == QueueConfig.RESULTADOS:
                resultados_config = call_kwargs
                break

        self.assertIsNotNone(resultados_config, "Cola de resultados no fue declarada")

        arguments = resultados_config.get('arguments', {})
        self.assertEqual(arguments.get('x-dead-letter-exchange'), '')
        self.assertEqual(
            arguments.get('x-dead-letter-routing-key'),
            QueueConfig.DLQ_RESULTADOS
        )


class TestRetryMechanism(unittest.TestCase):
    """Tests para sistema de reintentos automáticos."""

    def setUp(self):
        """Setup con consumer mockeado."""
        self.mock_channel = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.is_closed = False

        self.client = RabbitMQClient()
        self.client.connection = self.mock_connection
        self.client.channel = self.mock_channel

        self.consumer = Consumer(self.client, consumer_id='TEST-CONSUMER')

        # Mock del modelo cargado
        self.consumer.modelo_cargado = True
        self.consumer.tipo_funcion = 'expresion'
        self.consumer.expresion = 'x + y'
        self.consumer.evaluator = MagicMock()
        self.consumer.modelo_msg = {
            'modelo_id': 'test_model',
            'version': '1.0'
        }

    def test_retry_count_increments(self):
        """Test que el contador de reintentos se incrementa."""
        # Configurar evaluator para fallar
        self.consumer.evaluator.evaluate.side_effect = ValueError("Test error")

        # Crear mensaje y properties mock
        escenario = {'escenario_id': 'ESC-001', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-1'

        # Primera vez: sin reintentos
        properties = MagicMock()
        properties.headers = {}

        # Procesar mensaje
        self.consumer._procesar_escenario_callback(
            ch=self.mock_channel,
            method=method,
            properties=properties,
            body=body
        )

        # Verificar que se republicó el mensaje
        self.mock_channel.basic_publish.assert_called_once()

        # Verificar que el header x-retry-count se incrementó
        publish_call = self.mock_channel.basic_publish.call_args
        published_properties = publish_call[1]['properties']
        self.assertEqual(published_properties.headers['x-retry-count'], 1)
        self.assertEqual(published_properties.headers['x-last-error'], 'ValueError')

    def test_max_retries_exceeded_sends_to_dlq(self):
        """Test que después de MAX_RETRIES el mensaje va a DLQ."""
        # Configurar evaluator para fallar
        self.consumer.evaluator.evaluate.side_effect = ValueError("Test error")

        escenario = {'escenario_id': 'ESC-002', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-2'

        # Simular que ya se intentó MAX_RETRIES veces
        properties = MagicMock()
        properties.headers = {'x-retry-count': ConsumerConfig.MAX_RETRIES}

        # Procesar mensaje
        self.consumer._procesar_escenario_callback(
            ch=self.mock_channel,
            method=method,
            properties=properties,
            body=body
        )

        # Verificar que NO se republicó (no más reintentos)
        self.mock_channel.basic_publish.assert_not_called()

        # Verificar que se hizo NACK con requeue=False (enviar a DLQ)
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag='test-tag-2',
            requeue=False
        )

        # Verificar estadísticas
        self.assertEqual(self.consumer.mensajes_a_dlq, 1)

    def test_non_recoverable_error_goes_to_dlq_directly(self):
        """Test que errores no recuperables van directo a DLQ."""
        # Configurar evaluator para lanzar error no recuperable
        self.consumer.evaluator.evaluate.side_effect = ExpressionEvaluationError("Syntax error")

        escenario = {'escenario_id': 'ESC-003', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-3'

        properties = MagicMock()
        properties.headers = {}  # Sin reintentos previos

        # Procesar mensaje
        self.consumer._procesar_escenario_callback(
            ch=self.mock_channel,
            method=method,
            properties=properties,
            body=body
        )

        # Verificar que NO se republicó (error no recuperable)
        self.mock_channel.basic_publish.assert_not_called()

        # Verificar que se envió a DLQ directamente
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag='test-tag-3',
            requeue=False
        )

        self.assertEqual(self.consumer.mensajes_a_dlq, 1)

    def test_timeout_exception_goes_to_dlq(self):
        """Test que TimeoutException va directo a DLQ."""
        # Configurar para código Python
        self.consumer.tipo_funcion = 'codigo'
        self.consumer.codigo = 'resultado = x + y'
        self.consumer.python_executor = MagicMock()
        self.consumer.python_executor.execute.side_effect = TimeoutException("Timeout after 30s")

        escenario = {'escenario_id': 'ESC-004', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-4'

        properties = MagicMock()
        properties.headers = {}

        self.consumer._procesar_escenario_callback(
            ch=self.mock_channel,
            method=method,
            properties=properties,
            body=body
        )

        # Timeout no es recuperable, debe ir directo a DLQ
        self.mock_channel.basic_publish.assert_not_called()
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag='test-tag-4',
            requeue=False
        )

    def test_security_exception_goes_to_dlq(self):
        """Test que SecurityException va directo a DLQ."""
        self.consumer.tipo_funcion = 'codigo'
        self.consumer.codigo = 'resultado = x + y'
        self.consumer.python_executor = MagicMock()
        self.consumer.python_executor.execute.side_effect = SecurityException("Blocked import: os")

        escenario = {'escenario_id': 'ESC-005', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-5'

        properties = MagicMock()
        properties.headers = {}

        self.consumer._procesar_escenario_callback(
            ch=self.mock_channel,
            method=method,
            properties=properties,
            body=body
        )

        # Security violation no es recuperable
        self.mock_channel.basic_publish.assert_not_called()
        self.mock_channel.basic_nack.assert_called_once_with(
            delivery_tag='test-tag-5',
            requeue=False
        )

    def test_successful_retry_logs_correctly(self):
        """Test que un reintento exitoso se loggea correctamente."""
        # Simular un mensaje que ya fue reintentado una vez y ahora tiene éxito
        escenario = {'escenario_id': 'ESC-006', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        method.delivery_tag = 'test-tag-6'

        # Simular que es el segundo intento (exitoso)
        properties = MagicMock()
        properties.headers = {'x-retry-count': 1}

        # Configurar evaluator para tener éxito esta vez (sin side_effect)
        self.consumer.evaluator.evaluate.return_value = 3
        self.consumer.evaluator.evaluate.side_effect = None

        with self.assertLogs(level='INFO') as log_context:
            self.consumer._procesar_escenario_callback(
                ch=self.mock_channel,
                method=method,
                properties=properties,
                body=body
            )

            # Verificar que se loggeó el éxito después de reintentos
            log_output = '\n'.join(log_context.output)
            self.assertIn('después de 1 reintentos', log_output)

        # Verificar que se hizo ACK
        self.mock_channel.basic_ack.assert_called_once()


class TestErrorStatistics(unittest.TestCase):
    """Tests para estadísticas de errores."""

    def setUp(self):
        """Setup con consumer mockeado."""
        self.mock_channel = MagicMock()
        self.mock_connection = MagicMock()
        self.mock_connection.is_closed = False

        self.client = RabbitMQClient()
        self.client.connection = self.mock_connection
        self.client.channel = self.mock_channel

        self.consumer = Consumer(self.client, consumer_id='STATS-TEST')

        self.consumer.modelo_cargado = True
        self.consumer.tipo_funcion = 'expresion'
        self.consumer.expresion = 'x + y'
        self.consumer.evaluator = MagicMock()
        self.consumer.modelo_msg = {
            'modelo_id': 'test_model',
            'version': '1.0'
        }
        self.consumer.tiempo_inicio = time.time()

    def test_error_statistics_tracking(self):
        """Test que las estadísticas de errores se rastrean correctamente."""
        # Simular varios errores
        self.consumer.evaluator.evaluate.side_effect = ValueError("Test error")

        escenario = {'escenario_id': 'ESC-007', 'valores': {'x': 1, 'y': 2}}
        body = json.dumps(escenario).encode('utf-8')

        method = MagicMock()
        properties = MagicMock()
        properties.headers = {}

        # Procesar 3 mensajes con error
        for i in range(3):
            method.delivery_tag = f'test-tag-{i}'
            self.consumer._procesar_escenario_callback(
                ch=self.mock_channel,
                method=method,
                properties=properties,
                body=body
            )

        # Verificar estadísticas
        self.assertEqual(self.consumer.errores_totales, 3)
        self.assertEqual(self.consumer.reintentos_totales, 3)
        self.assertEqual(self.consumer.errores_por_tipo.get('ValueError', 0), 3)

    def test_stats_published_with_error_info(self):
        """Test que las stats publicadas incluyen info de errores."""
        # Simular algunos errores y reintentos
        self.consumer.errores_totales = 5
        self.consumer.reintentos_totales = 10
        self.consumer.mensajes_a_dlq = 2
        self.consumer.errores_por_tipo = {
            'ValueError': 3,
            'TimeoutException': 2
        }

        # Publicar stats
        self.consumer._publicar_stats()

        # Verificar que se llamó publish
        self.mock_channel.basic_publish.assert_called_once()

        # Extraer el mensaje publicado
        publish_call = self.mock_channel.basic_publish.call_args
        body = publish_call[1]['body']
        stats = json.loads(body)

        # Verificar que incluye estadísticas de errores
        self.assertEqual(stats['errores_totales'], 5)
        self.assertEqual(stats['reintentos_totales'], 10)
        self.assertEqual(stats['mensajes_a_dlq'], 2)
        self.assertEqual(stats['errores_por_tipo']['ValueError'], 3)
        self.assertEqual(stats['errores_por_tipo']['TimeoutException'], 2)

    def test_finalizar_displays_error_stats(self):
        """Test que _finalizar() muestra estadísticas de errores."""
        self.consumer.escenarios_procesados = 100
        self.consumer.errores_totales = 10
        self.consumer.reintentos_totales = 15
        self.consumer.mensajes_a_dlq = 3
        self.consumer.errores_por_tipo = {
            'ValueError': 7,
            'TimeoutException': 3
        }

        with self.assertLogs(level='INFO') as log_context:
            self.consumer._finalizar()

            log_output = '\n'.join(log_context.output)

            # Verificar que se muestran las estadísticas de errores
            self.assertIn('ESTADÍSTICAS DE ERRORES', log_output)
            self.assertIn('Total errores: 10', log_output)
            self.assertIn('Reintentos: 15', log_output)
            self.assertIn('Mensajes a DLQ: 3', log_output)
            self.assertIn('ValueError: 7', log_output)
            self.assertIn('TimeoutException: 3', log_output)


class TestLoggingConfiguration(unittest.TestCase):
    """Tests para configuración de logging estructurado."""

    def test_structured_formatter_creates_json(self):
        """Test que StructuredFormatter crea JSON válido."""
        formatter = StructuredFormatter()

        # Crear un LogRecord de prueba
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='/test/path.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )

        # Formatear
        formatted = formatter.format(record)

        # Verificar que es JSON válido
        data = json.loads(formatted)

        self.assertEqual(data['level'], 'INFO')
        self.assertEqual(data['logger'], 'test_logger')
        self.assertEqual(data['message'], 'Test message')
        self.assertEqual(data['line'], 42)
        self.assertIn('timestamp', data)

    def test_structured_formatter_includes_exception(self):
        """Test que StructuredFormatter incluye información de excepciones."""
        formatter = StructuredFormatter()

        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='/test/path.py',
            lineno=42,
            msg='Error occurred',
            args=(),
            exc_info=exc_info
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        self.assertIn('exception', data)
        self.assertEqual(data['exception']['type'], 'ValueError')
        self.assertIn('Test exception', data['exception']['message'])
        self.assertIsNotNone(data['exception']['traceback'])

    def test_colored_formatter_adds_colors(self):
        """Test que ColoredFormatter añade códigos ANSI."""
        formatter = ColoredFormatter(fmt='%(levelname)s - %(message)s')

        record = logging.LogRecord(
            name='test_logger',
            level=logging.ERROR,
            pathname='/test/path.py',
            lineno=42,
            msg='Error message',
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)

        # Verificar que contiene códigos ANSI
        self.assertIn('\033[', formatted)  # Código de escape ANSI
        self.assertIn('ERROR', formatted)
        self.assertIn('Error message', formatted)

    def test_setup_logging_creates_log_files(self):
        """Test que setup_logging crea archivos de log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = 'test.log'

            # Configurar logging con directorio temporal
            with patch('src.common.logging_config.BASE_DIR', Path(tmpdir)):
                setup_logging(
                    log_level='INFO',
                    log_format='json',
                    log_file=log_file,
                    enable_console=False
                )

                # Verificar que se creó el directorio de logs
                logs_dir = Path(tmpdir) / 'logs'
                self.assertTrue(logs_dir.exists())

                # Hacer un log de prueba
                logger = logging.getLogger('test')
                logger.info('Test log message')

                # Forzar flush de handlers
                for handler in logger.handlers:
                    handler.flush()

                # Verificar que se creó el archivo
                log_path = logs_dir / log_file
                self.assertTrue(log_path.exists())

                # Leer y verificar contenido (puede haber múltiples líneas)
                with open(log_path, 'r') as f:
                    lines = f.read().strip().split('\n')
                    # Buscar nuestra línea de test
                    found = False
                    for line in lines:
                        if line.strip():
                            log_data = json.loads(line)
                            if log_data.get('message') == 'Test log message':
                                found = True
                                break
                    self.assertTrue(found, "No se encontró el mensaje de test en el log")


class TestConfigurationValues(unittest.TestCase):
    """Tests para valores de configuración de Fase 4.1."""

    def test_max_retries_config_exists(self):
        """Test que MAX_RETRIES está configurado."""
        self.assertIsInstance(ConsumerConfig.MAX_RETRIES, int)
        self.assertGreater(ConsumerConfig.MAX_RETRIES, 0)
        self.assertEqual(ConsumerConfig.MAX_RETRIES, 3)

    def test_retry_delay_config_exists(self):
        """Test que RETRY_DELAY está configurado."""
        self.assertIsInstance(ConsumerConfig.RETRY_DELAY, int)
        self.assertGreaterEqual(ConsumerConfig.RETRY_DELAY, 0)

    def test_dlq_queue_names_configured(self):
        """Test que nombres de DLQ están configurados."""
        self.assertIsNotNone(QueueConfig.DLQ_ESCENARIOS)
        self.assertIsNotNone(QueueConfig.DLQ_RESULTADOS)
        self.assertIsInstance(QueueConfig.DLQ_ESCENARIOS, str)
        self.assertIsInstance(QueueConfig.DLQ_RESULTADOS, str)


def run_tests():
    """Ejecuta todos los tests de Fase 4.1."""
    # Configurar logging para tests
    logging.basicConfig(level=logging.WARNING)

    # Crear test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Añadir todos los test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDLQConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestRetryMechanism))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorStatistics))
    suite.addTests(loader.loadTestsFromTestCase(TestLoggingConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestConfigurationValues))

    # Ejecutar tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Imprimir resumen
    print("\n" + "=" * 70)
    print("RESUMEN DE TESTS - FASE 4.1")
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
