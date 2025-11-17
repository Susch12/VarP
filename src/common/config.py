"""
Configuración centralizada del sistema de simulación Monte Carlo.
Lee variables de entorno desde .env y proporciona valores por defecto.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / '.env')


class RabbitMQConfig:
    """Configuración de RabbitMQ."""

    HOST = os.getenv('RABBITMQ_HOST', 'localhost')
    PORT = int(os.getenv('RABBITMQ_PORT', '5672'))
    USER = os.getenv('RABBITMQ_USER', 'admin')
    PASS = os.getenv('RABBITMQ_PASS', 'password')
    VHOST = os.getenv('RABBITMQ_VHOST', '/')
    MGMT_PORT = int(os.getenv('RABBITMQ_MGMT_PORT', '15672'))

    # Fase 4.2: Configuración óptima de conexión
    HEARTBEAT = int(os.getenv('RABBITMQ_HEARTBEAT', '60'))  # segundos
    CONNECTION_TIMEOUT = int(os.getenv('RABBITMQ_CONNECTION_TIMEOUT', '10'))  # segundos
    BLOCKED_CONNECTION_TIMEOUT = int(os.getenv('RABBITMQ_BLOCKED_TIMEOUT', '300'))  # segundos
    SOCKET_TIMEOUT = int(os.getenv('RABBITMQ_SOCKET_TIMEOUT', '10'))  # segundos
    STACK_TIMEOUT = int(os.getenv('RABBITMQ_STACK_TIMEOUT', '15'))  # segundos

    # Connection pooling (Fase 4.2)
    POOL_SIZE = int(os.getenv('RABBITMQ_POOL_SIZE', '10'))  # Número de conexiones en pool
    POOL_MAX_OVERFLOW = int(os.getenv('RABBITMQ_POOL_MAX_OVERFLOW', '5'))  # Conexiones adicionales si pool lleno
    POOL_TIMEOUT = int(os.getenv('RABBITMQ_POOL_TIMEOUT', '30'))  # Tiempo de espera para obtener conexión
    POOL_RECYCLE = int(os.getenv('RABBITMQ_POOL_RECYCLE', '3600'))  # Reciclar conexiones después de N segundos

    @classmethod
    def get_connection_url(cls) -> str:
        """Retorna URL de conexión para pika."""
        return f'amqp://{cls.USER}:{cls.PASS}@{cls.HOST}:{cls.PORT}{cls.VHOST}'


class QueueConfig:
    """Nombres de las colas."""

    MODELO = os.getenv('QUEUE_MODELO', 'cola_modelo')
    ESCENARIOS = os.getenv('QUEUE_ESCENARIOS', 'cola_escenarios')
    RESULTADOS = os.getenv('QUEUE_RESULTADOS', 'cola_resultados')
    STATS_PRODUCTOR = os.getenv('QUEUE_STATS_PRODUCTOR', 'cola_stats_productor')
    STATS_CONSUMIDORES = os.getenv('QUEUE_STATS_CONSUMIDORES', 'cola_stats_consumidores')

    # Dead Letter Queue (Fase 4.1)
    DLQ_ESCENARIOS = os.getenv('QUEUE_DLQ_ESCENARIOS', 'cola_dlq_escenarios')
    DLQ_RESULTADOS = os.getenv('QUEUE_DLQ_RESULTADOS', 'cola_dlq_resultados')


class ProducerConfig:
    """Configuración del productor."""

    # Optimización Fase 4: Intervalo de stats aumentado de 1s a 5s
    # Reduce mensajes de stats en 80% sin afectar monitoreo
    STATS_INTERVAL = int(os.getenv('PRODUCER_STATS_INTERVAL', '5'))


class ConsumerConfig:
    """Configuración del consumidor."""

    # Optimización Fase 4: Intervalo de stats aumentado de 2s a 5s
    # Reduce mensajes de stats en 60% sin afectar monitoreo
    STATS_INTERVAL = int(os.getenv('CONSUMER_STATS_INTERVAL', '5'))
    PREFETCH_COUNT = int(os.getenv('CONSUMER_PREFETCH_COUNT', '1'))
    TIMEOUT = int(os.getenv('CONSUMER_TIMEOUT', '30'))

    # Manejo de errores (Fase 4.1)
    MAX_RETRIES = int(os.getenv('CONSUMER_MAX_RETRIES', '3'))
    RETRY_DELAY = int(os.getenv('CONSUMER_RETRY_DELAY', '5'))  # segundos


class DashboardConfig:
    """Configuración del dashboard."""

    HOST = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    PORT = int(os.getenv('DASHBOARD_PORT', '8050'))
    REFRESH_INTERVAL = int(os.getenv('DASHBOARD_REFRESH_INTERVAL', '2000'))


class SimulationConfig:
    """Configuración de simulación."""

    DEFAULT_NUM_ESCENARIOS = int(os.getenv('DEFAULT_NUM_ESCENARIOS', '1000'))
    DEFAULT_RANDOM_SEED = int(os.getenv('DEFAULT_RANDOM_SEED', '42'))


class LogConfig:
    """Configuración de logging."""

    LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    FORMAT = os.getenv('LOG_FORMAT', 'colored')


# Exportar configuraciones
__all__ = [
    'RabbitMQConfig',
    'QueueConfig',
    'ProducerConfig',
    'ConsumerConfig',
    'DashboardConfig',
    'SimulationConfig',
    'LogConfig',
    'BASE_DIR'
]
