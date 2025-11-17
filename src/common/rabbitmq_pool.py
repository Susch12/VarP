"""
Connection Pool para RabbitMQ (Fase 4.2).

Implementa un pool de conexiones reutilizables para mejorar el rendimiento
y reducir overhead de creación/destrucción de conexiones.

Features:
- Pool size configurable
- Max overflow para picos de demanda
- Timeout configurable
- Reciclado automático de conexiones viejas
- Thread-safe
"""

import time
import threading
import logging
from typing import Optional, List
from contextlib import contextmanager
from queue import Queue, Empty, Full

import pika

from src.common.config import RabbitMQConfig
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError

logger = logging.getLogger(__name__)


class PooledConnection:
    """
    Wrapper para una conexión en el pool.

    Trackea cuándo fue creada para permitir reciclado automático.
    """

    def __init__(self, client: RabbitMQClient):
        """
        Inicializa una conexión pooled.

        Args:
            client: Cliente RabbitMQ conectado
        """
        self.client = client
        self.created_at = time.time()
        self.last_used = time.time()
        self.use_count = 0

    def should_recycle(self, max_age: int) -> bool:
        """
        Determina si la conexión debe ser reciclada.

        Args:
            max_age: Edad máxima en segundos

        Returns:
            True si debe ser reciclada
        """
        age = time.time() - self.created_at
        return age > max_age

    def is_healthy(self) -> bool:
        """
        Verifica si la conexión está sana.

        Returns:
            True si la conexión está abierta y funcional
        """
        try:
            if self.client.connection is None:
                return False
            return not self.client.connection.is_closed
        except Exception:
            return False

    def mark_used(self) -> None:
        """Marca la conexión como usada recientemente."""
        self.last_used = time.time()
        self.use_count += 1


class RabbitMQConnectionPool:
    """
    Pool de conexiones para RabbitMQ.

    Implementa un pool thread-safe con las siguientes características:
    - Tamaño de pool configurable
    - Overflow para picos de demanda
    - Timeout al obtener conexión
    - Reciclado automático de conexiones viejas
    - Health checks
    """

    def __init__(
        self,
        pool_size: Optional[int] = None,
        max_overflow: Optional[int] = None,
        pool_timeout: Optional[int] = None,
        recycle: Optional[int] = None,
        **connection_kwargs
    ):
        """
        Inicializa el pool de conexiones.

        Args:
            pool_size: Número de conexiones a mantener (default: desde config)
            max_overflow: Conexiones adicionales permitidas (default: desde config)
            pool_timeout: Timeout para obtener conexión (default: desde config)
            recycle: Tiempo en segundos para reciclar conexiones (default: desde config)
            **connection_kwargs: Argumentos adicionales para RabbitMQClient
        """
        self.pool_size = pool_size or RabbitMQConfig.POOL_SIZE
        self.max_overflow = max_overflow or RabbitMQConfig.POOL_MAX_OVERFLOW
        self.pool_timeout = pool_timeout or RabbitMQConfig.POOL_TIMEOUT
        self.recycle = recycle or RabbitMQConfig.POOL_RECYCLE
        self.connection_kwargs = connection_kwargs

        # Pool de conexiones disponibles
        self._pool: Queue[PooledConnection] = Queue(maxsize=self.pool_size)

        # Contador de conexiones overflow actualmente en uso
        self._overflow_lock = threading.Lock()
        self._overflow_count = 0

        # Estadísticas
        self.stats_created = 0
        self.stats_reused = 0
        self.stats_recycled = 0
        self.stats_health_checks_failed = 0

        # Inicializar pool con conexiones
        self._initialize_pool()

        logger.info(
            f"Connection pool inicializado: size={self.pool_size}, "
            f"max_overflow={self.max_overflow}, recycle={self.recycle}s"
        )

    def _initialize_pool(self) -> None:
        """Inicializa el pool con conexiones."""
        for i in range(self.pool_size):
            try:
                conn = self._create_connection()
                self._pool.put_nowait(conn)
                logger.debug(f"Conexión inicial {i+1}/{self.pool_size} creada")
            except Exception as e:
                logger.warning(
                    f"No se pudo crear conexión inicial {i+1}: {e}. "
                    f"Pool continuará con {i} conexiones"
                )
                break

    def _create_connection(self) -> PooledConnection:
        """
        Crea una nueva conexión al pool.

        Returns:
            PooledConnection nueva

        Raises:
            RabbitMQConnectionError: Si falla la creación
        """
        client = RabbitMQClient(**self.connection_kwargs)
        client.connect()

        self.stats_created += 1
        logger.debug(f"Nueva conexión creada (total creadas: {self.stats_created})")

        return PooledConnection(client)

    def _get_connection_from_pool(self) -> Optional[PooledConnection]:
        """
        Intenta obtener una conexión del pool.

        Returns:
            PooledConnection si está disponible, None si no hay
        """
        try:
            conn = self._pool.get(block=False)
            return conn
        except Empty:
            return None

    def _return_connection_to_pool(self, conn: PooledConnection) -> None:
        """
        Retorna una conexión al pool.

        Args:
            conn: Conexión a retornar
        """
        try:
            self._pool.put(conn, block=False)
        except Full:
            # Pool lleno, cerrar la conexión
            logger.debug("Pool lleno, cerrando conexión overflow")
            try:
                conn.client.disconnect()
            except Exception as e:
                logger.warning(f"Error cerrando conexión overflow: {e}")

    @contextmanager
    def connection(self):
        """
        Context manager para obtener una conexión del pool.

        Usage:
            with pool.connection() as client:
                client.publish(...)

        Yields:
            RabbitMQClient de la conexión pooled

        Raises:
            RabbitMQConnectionError: Si no se puede obtener conexión
        """
        conn = None
        is_overflow = False

        try:
            # Intentar obtener conexión del pool
            conn = self._get_connection_from_pool()

            if conn is None:
                # Pool vacío, intentar crear overflow
                with self._overflow_lock:
                    if self._overflow_count < self.max_overflow:
                        # Permitir overflow
                        self._overflow_count += 1
                        is_overflow = True
                        logger.debug(
                            f"Creando conexión overflow "
                            f"({self._overflow_count}/{self.max_overflow})"
                        )
                        conn = self._create_connection()
                    else:
                        # Overflow agotado, esperar por conexión
                        logger.debug(
                            f"Pool y overflow agotados, esperando hasta {self.pool_timeout}s"
                        )
                        try:
                            conn = self._pool.get(timeout=self.pool_timeout)
                        except Empty:
                            raise RabbitMQConnectionError(
                                f"Timeout esperando conexión del pool "
                                f"({self.pool_timeout}s)"
                            )

            # Verificar si debe ser reciclada
            if conn.should_recycle(self.recycle):
                logger.debug("Reciclando conexión vieja")
                try:
                    conn.client.disconnect()
                except Exception:
                    pass
                conn = self._create_connection()
                self.stats_recycled += 1

            # Health check
            if not conn.is_healthy():
                logger.warning("Conexión no saludable, recreando")
                self.stats_health_checks_failed += 1
                try:
                    conn.client.disconnect()
                except Exception:
                    pass
                conn = self._create_connection()

            # Marcar como usada
            conn.mark_used()
            self.stats_reused += 1

            # Yield la conexión
            yield conn.client

        finally:
            # Retornar conexión al pool
            if conn is not None:
                if is_overflow:
                    # Conexión overflow, liberar contador y cerrar
                    with self._overflow_lock:
                        self._overflow_count -= 1
                    try:
                        conn.client.disconnect()
                    except Exception as e:
                        logger.warning(f"Error cerrando conexión overflow: {e}")
                else:
                    # Conexión normal, retornar al pool
                    self._return_connection_to_pool(conn)

    def close_all(self) -> None:
        """
        Cierra todas las conexiones en el pool.

        Útil para cleanup al finalizar la aplicación.
        """
        logger.info("Cerrando todas las conexiones del pool...")
        closed = 0

        # Vaciar el pool
        while True:
            try:
                conn = self._pool.get(block=False)
                try:
                    conn.client.disconnect()
                    closed += 1
                except Exception as e:
                    logger.warning(f"Error cerrando conexión: {e}")
            except Empty:
                break

        logger.info(f"Pool cerrado: {closed} conexiones cerradas")

    def get_stats(self) -> dict:
        """
        Obtiene estadísticas del pool.

        Returns:
            Diccionario con estadísticas
        """
        return {
            'pool_size': self.pool_size,
            'max_overflow': self.max_overflow,
            'pool_timeout': self.pool_timeout,
            'recycle_time': self.recycle,
            'available_connections': self._pool.qsize(),
            'overflow_count': self._overflow_count,
            'total_created': self.stats_created,
            'total_reused': self.stats_reused,
            'total_recycled': self.stats_recycled,
            'health_checks_failed': self.stats_health_checks_failed
        }

    def __enter__(self):
        """Context manager: no-op, el pool ya está inicializado."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager: cerrar todas las conexiones."""
        self.close_all()


# Singleton global del pool (opcional)
_global_pool: Optional[RabbitMQConnectionPool] = None
_pool_lock = threading.Lock()


def get_global_pool(**kwargs) -> RabbitMQConnectionPool:
    """
    Obtiene o crea el pool global de conexiones.

    Thread-safe singleton pattern.

    Args:
        **kwargs: Argumentos para inicializar el pool (solo primera vez)

    Returns:
        Instancia global del pool
    """
    global _global_pool

    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                _global_pool = RabbitMQConnectionPool(**kwargs)
                logger.info("Pool global de conexiones creado")

    return _global_pool


def close_global_pool() -> None:
    """
    Cierra el pool global de conexiones.

    Útil para cleanup en shutdown de aplicación.
    """
    global _global_pool

    if _global_pool is not None:
        with _pool_lock:
            if _global_pool is not None:
                _global_pool.close_all()
                _global_pool = None
                logger.info("Pool global de conexiones cerrado")


__all__ = [
    'PooledConnection',
    'RabbitMQConnectionPool',
    'get_global_pool',
    'close_global_pool'
]
