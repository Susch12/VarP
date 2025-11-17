"""
Cliente de RabbitMQ para el sistema de simulación Monte Carlo.

Proporciona funcionalidad para conectar, declarar colas y publicar/consumir mensajes.
"""

import pika
import json
import logging
from typing import Dict, Any, Optional, Callable
from src.common.config import RabbitMQConfig, QueueConfig

logger = logging.getLogger(__name__)


class RabbitMQConnectionError(Exception):
    """Excepción para errores de conexión a RabbitMQ."""
    pass


class RabbitMQClient:
    """
    Cliente para interactuar con RabbitMQ.

    Maneja conexiones, declaración de colas y operaciones de pub/sub.
    """

    def __init__(self, host: str = None, port: int = None,
                 user: str = None, password: str = None):
        """
        Inicializa el cliente de RabbitMQ.

        Args:
            host: Host de RabbitMQ (default: desde config)
            port: Puerto de RabbitMQ (default: desde config)
            user: Usuario de RabbitMQ (default: desde config)
            password: Contraseña de RabbitMQ (default: desde config)
        """
        self.host = host or RabbitMQConfig.HOST
        self.port = port or RabbitMQConfig.PORT
        self.user = user or RabbitMQConfig.USER
        self.password = password or RabbitMQConfig.PASS

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

    def connect(self) -> None:
        """
        Establece conexión con RabbitMQ.

        FASE 4.2: Configuración óptima con:
        - Heartbeat configurable para detección de conexiones muertas
        - Connection timeout para evitar cuelgues
        - Blocked connection timeout para flow control
        - Socket timeout para operaciones de red

        Raises:
            RabbitMQConnectionError: Si falla la conexión
        """
        try:
            credentials = pika.PlainCredentials(self.user, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                credentials=credentials,
                # FASE 4.2: Configuración óptima de timeouts
                heartbeat=RabbitMQConfig.HEARTBEAT,
                connection_attempts=3,
                retry_delay=2,
                socket_timeout=RabbitMQConfig.SOCKET_TIMEOUT,
                stack_timeout=RabbitMQConfig.STACK_TIMEOUT,
                blocked_connection_timeout=RabbitMQConfig.BLOCKED_CONNECTION_TIMEOUT,
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()

            logger.info(
                f"Conectado a RabbitMQ en {self.host}:{self.port} "
                f"(heartbeat={RabbitMQConfig.HEARTBEAT}s)"
            )

        except pika.exceptions.AMQPConnectionError as e:
            raise RabbitMQConnectionError(
                f"Error conectando a RabbitMQ en {self.host}:{self.port}: {e}"
            )

    def disconnect(self) -> None:
        """Cierra la conexión con RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("Desconectado de RabbitMQ")

    def declare_queues(self) -> None:
        """
        Declara todas las colas necesarias para el sistema.

        Colas:
        - cola_modelo: Modelo a ejecutar (max 1 mensaje)
        - cola_escenarios: Escenarios a procesar (con DLQ)
        - cola_resultados: Resultados de ejecución
        - cola_stats_productor: Estadísticas del productor
        - cola_stats_consumidores: Estadísticas de consumidores
        - cola_dlq_escenarios: Dead Letter Queue para escenarios fallidos
        - cola_dlq_resultados: Dead Letter Queue para resultados fallidos
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo. Llame a connect() primero")

        # FASE 4.1: Declarar Dead Letter Queues primero
        # DLQ para escenarios fallidos (persistente, sin límite de mensajes)
        self.channel.queue_declare(
            queue=QueueConfig.DLQ_ESCENARIOS,
            durable=True,
            arguments={
                'x-max-length': 10000,  # Capacidad de mensajes fallidos
            }
        )
        logger.debug(f"DLQ declarada: {QueueConfig.DLQ_ESCENARIOS}")

        # DLQ para resultados fallidos (persistente)
        self.channel.queue_declare(
            queue=QueueConfig.DLQ_RESULTADOS,
            durable=True,
            arguments={
                'x-max-length': 10000,
            }
        )
        logger.debug(f"DLQ declarada: {QueueConfig.DLQ_RESULTADOS}")

        # Cola de modelo (solo 1 mensaje, persistente)
        self.channel.queue_declare(
            queue=QueueConfig.MODELO,
            durable=True,
            arguments={
                'x-max-length': 1,  # Solo 1 modelo activo
            }
        )
        logger.debug(f"Cola declarada: {QueueConfig.MODELO}")

        # FASE 4.1: Cola de escenarios con DLQ configurada
        # Los mensajes rechazados (NACK con requeue=False) van a DLQ
        self.channel.queue_declare(
            queue=QueueConfig.ESCENARIOS,
            durable=True,
            arguments={
                'x-max-length': 100000,  # Capacidad máxima
                'x-dead-letter-exchange': '',  # Exchange por defecto
                'x-dead-letter-routing-key': QueueConfig.DLQ_ESCENARIOS
            }
        )
        logger.debug(f"Cola declarada: {QueueConfig.ESCENARIOS} (con DLQ: {QueueConfig.DLQ_ESCENARIOS})")

        # FASE 4.1: Cola de resultados con DLQ configurada
        self.channel.queue_declare(
            queue=QueueConfig.RESULTADOS,
            durable=True,
            arguments={
                'x-dead-letter-exchange': '',
                'x-dead-letter-routing-key': QueueConfig.DLQ_RESULTADOS
            }
        )
        logger.debug(f"Cola declarada: {QueueConfig.RESULTADOS} (con DLQ: {QueueConfig.DLQ_RESULTADOS})")

        # Cola de estadísticas del productor (no persistente, TTL 60s)
        self.channel.queue_declare(
            queue=QueueConfig.STATS_PRODUCTOR,
            durable=False,
            arguments={
                'x-max-length': 100,
                'x-message-ttl': 60000  # 60 segundos
            }
        )
        logger.debug(f"Cola declarada: {QueueConfig.STATS_PRODUCTOR}")

        # Cola de estadísticas de consumidores (no persistente, TTL 60s)
        self.channel.queue_declare(
            queue=QueueConfig.STATS_CONSUMIDORES,
            durable=False,
            arguments={
                'x-max-length': 1000,
                'x-message-ttl': 60000
            }
        )
        logger.debug(f"Cola declarada: {QueueConfig.STATS_CONSUMIDORES}")

        logger.info("Todas las colas declaradas exitosamente (incluyendo DLQs)")

    def purge_queue(self, queue_name: str) -> int:
        """
        Purga (elimina todos los mensajes de) una cola.

        Args:
            queue_name: Nombre de la cola a purgar

        Returns:
            Número de mensajes eliminados
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo")

        result = self.channel.queue_purge(queue_name)
        logger.info(f"Cola '{queue_name}' purgada: {result} mensajes eliminados")
        return result

    def publish(self, queue_name: str, message: Dict[str, Any],
                persistent: bool = True) -> None:
        """
        Publica un mensaje en una cola.

        Args:
            queue_name: Nombre de la cola
            message: Mensaje a publicar (será serializado a JSON)
            persistent: Si el mensaje debe ser persistente (default: True)
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo")

        properties = pika.BasicProperties(
            delivery_mode=2 if persistent else 1,
            content_type='application/json'
        )

        body = json.dumps(message, ensure_ascii=False)

        self.channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=body,
            properties=properties
        )

        logger.debug(f"Mensaje publicado en '{queue_name}'")

    def consume(self, queue_name: str, callback: Callable,
                auto_ack: bool = False, prefetch_count: int = 1) -> None:
        """
        Consume mensajes de una cola.

        Args:
            queue_name: Nombre de la cola
            callback: Función callback(ch, method, properties, body)
            auto_ack: Si auto-acknowledge (default: False)
            prefetch_count: Número de mensajes a prefetch (default: 1)
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo")

        self.channel.basic_qos(prefetch_count=prefetch_count)
        self.channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=auto_ack
        )

        logger.info(f"Consumiendo mensajes de '{queue_name}'...")
        self.channel.start_consuming()

    def get_message(self, queue_name: str, auto_ack: bool = False) -> Optional[Dict[str, Any]]:
        """
        Obtiene un solo mensaje de una cola (no bloqueante).

        Args:
            queue_name: Nombre de la cola
            auto_ack: Si auto-acknowledge (default: False)

        Returns:
            Diccionario con el mensaje parseado o None si no hay mensajes
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo")

        method, properties, body = self.channel.basic_get(
            queue=queue_name,
            auto_ack=auto_ack
        )

        if body is None:
            return None

        message = json.loads(body)

        # Si no es auto_ack, hacer ack manualmente
        if not auto_ack:
            self.channel.basic_ack(delivery_tag=method.delivery_tag)

        return message

    def get_queue_size(self, queue_name: str) -> int:
        """
        Obtiene el número de mensajes en una cola.

        Args:
            queue_name: Nombre de la cola

        Returns:
            Número de mensajes en la cola
        """
        if not self.channel:
            raise RabbitMQConnectionError("No hay canal activo")

        queue = self.channel.queue_declare(
            queue=queue_name,
            passive=True  # No crear si no existe
        )
        return queue.method.message_count

    def __enter__(self):
        """Context manager: conectar al entrar."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: desconectar al salir."""
        self.disconnect()


# Factory function para conveniencia
def create_rabbitmq_client(**kwargs) -> RabbitMQClient:
    """
    Crea y conecta un cliente de RabbitMQ.

    Args:
        **kwargs: Argumentos para RabbitMQClient

    Returns:
        Cliente conectado de RabbitMQ
    """
    client = RabbitMQClient(**kwargs)
    client.connect()
    return client


__all__ = [
    'RabbitMQClient',
    'RabbitMQConnectionError',
    'create_rabbitmq_client'
]
