"""
Gestor de datos para el dashboard.

Consume estadísticas de RabbitMQ en un thread separado y mantiene
el estado actualizado para el dashboard.
"""

import threading
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.common.rabbitmq_client import RabbitMQClient
from src.common.config import QueueConfig

logger = logging.getLogger(__name__)


class DataManager:
    """
    Gestor de datos del dashboard.

    Consume estadísticas de RabbitMQ en background y mantiene
    estado actualizado accesible para el dashboard.
    """

    def __init__(self, rabbitmq_client: RabbitMQClient):
        """
        Inicializa el gestor de datos.

        Args:
            rabbitmq_client: Cliente conectado de RabbitMQ
        """
        self.client = rabbitmq_client

        # Estado del sistema
        self.stats_productor: Dict[str, Any] = {}
        self.stats_consumidores: Dict[str, Dict[str, Any]] = {}  # {consumer_id: stats}
        self.modelo_info: Dict[str, Any] = {}

        # Históricos para gráficas (últimos 100 puntos)
        self.historico_productor: List[Dict[str, Any]] = []
        self.historico_consumidores: Dict[str, List[Dict[str, Any]]] = {}

        # Estado de colas
        self.queue_sizes: Dict[str, int] = {}

        # Thread control
        self._stop_event = threading.Event()
        self._consumer_thread: Optional[threading.Thread] = None

        # Lock para acceso thread-safe
        self._lock = threading.Lock()

        # Última actualización
        self.last_update = None

    def start(self) -> None:
        """Inicia el consumo de estadísticas en background."""
        if self._consumer_thread is not None and self._consumer_thread.is_alive():
            logger.warning("DataManager ya está corriendo")
            return

        logger.info("Iniciando DataManager...")
        self._stop_event.clear()
        self._consumer_thread = threading.Thread(
            target=self._consume_stats_loop,
            daemon=True
        )
        self._consumer_thread.start()
        logger.info("DataManager iniciado")

    def stop(self) -> None:
        """Detiene el consumo de estadísticas."""
        logger.info("Deteniendo DataManager...")
        self._stop_event.set()
        if self._consumer_thread:
            self._consumer_thread.join(timeout=5)
        logger.info("DataManager detenido")

    def _consume_stats_loop(self) -> None:
        """Loop principal que consume estadísticas de RabbitMQ."""
        logger.info("Loop de consumo de stats iniciado")

        while not self._stop_event.is_set():
            try:
                # Consumir stats del productor
                self._consume_stats_productor()

                # Consumir stats de consumidores
                self._consume_stats_consumidores()

                # Actualizar tamaños de colas
                self._update_queue_sizes()

                # Actualizar modelo info (solo si no lo tenemos)
                if not self.modelo_info:
                    self._update_modelo_info()

                # Actualizar timestamp
                with self._lock:
                    self.last_update = datetime.now()

                # Esperar un poco antes de siguiente ciclo
                time.sleep(0.5)  # Consumir cada 0.5s

            except Exception as e:
                logger.error(f"Error en loop de consumo: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Loop de consumo de stats finalizado")

    def _consume_stats_productor(self) -> None:
        """Consume estadísticas del productor."""
        try:
            # Obtener un mensaje sin hacer ACK (para que otros también lo lean)
            stats_msg = self.client.get_message(
                QueueConfig.STATS_PRODUCTOR,
                auto_ack=True
            )

            if stats_msg:
                with self._lock:
                    self.stats_productor = stats_msg

                    # Agregar a histórico
                    self.historico_productor.append(stats_msg.copy())

                    # Mantener solo últimos 100 puntos
                    if len(self.historico_productor) > 100:
                        self.historico_productor.pop(0)

                logger.debug(f"Stats productor actualizadas: {stats_msg.get('progreso', 0)*100:.1f}%")

        except Exception as e:
            logger.error(f"Error consumiendo stats productor: {e}")

    def _consume_stats_consumidores(self) -> None:
        """Consume estadísticas de consumidores."""
        try:
            # Consumir todos los mensajes disponibles
            while True:
                stats_msg = self.client.get_message(
                    QueueConfig.STATS_CONSUMIDORES,
                    auto_ack=True
                )

                if not stats_msg:
                    break

                consumer_id = stats_msg.get('consumer_id')
                if not consumer_id:
                    continue

                with self._lock:
                    # Actualizar stats del consumidor
                    self.stats_consumidores[consumer_id] = stats_msg

                    # Agregar a histórico del consumidor
                    if consumer_id not in self.historico_consumidores:
                        self.historico_consumidores[consumer_id] = []

                    self.historico_consumidores[consumer_id].append(stats_msg.copy())

                    # Mantener solo últimos 100 puntos
                    if len(self.historico_consumidores[consumer_id]) > 100:
                        self.historico_consumidores[consumer_id].pop(0)

                logger.debug(f"Stats consumidor {consumer_id} actualizadas: {stats_msg.get('escenarios_procesados', 0)} procesados")

                # Pequeña pausa entre mensajes
                time.sleep(0.01)

        except Exception as e:
            logger.error(f"Error consumiendo stats consumidores: {e}")

    def _update_queue_sizes(self) -> None:
        """Actualiza los tamaños de las colas."""
        try:
            queues = [
                QueueConfig.MODELO,
                QueueConfig.ESCENARIOS,
                QueueConfig.RESULTADOS,
                QueueConfig.STATS_PRODUCTOR,
                QueueConfig.STATS_CONSUMIDORES
            ]

            sizes = {}
            for queue in queues:
                try:
                    sizes[queue] = self.client.get_queue_size(queue)
                except Exception as e:
                    logger.warning(f"Error obteniendo tamaño de {queue}: {e}")
                    sizes[queue] = 0

            with self._lock:
                self.queue_sizes = sizes

        except Exception as e:
            logger.error(f"Error actualizando tamaños de colas: {e}")

    def _update_modelo_info(self) -> None:
        """Actualiza información del modelo."""
        try:
            modelo_msg = self.client.get_message(
                QueueConfig.MODELO,
                auto_ack=False
            )

            if modelo_msg:
                # Volver a publicar para no consumir
                self.client.publish(
                    QueueConfig.MODELO,
                    modelo_msg,
                    persistent=True
                )

                with self._lock:
                    self.modelo_info = {
                        'modelo_id': modelo_msg.get('modelo_id'),
                        'version': modelo_msg.get('version'),
                        'nombre': modelo_msg.get('metadata', {}).get('nombre'),
                        'descripcion': modelo_msg.get('metadata', {}).get('descripcion'),
                        'num_variables': len(modelo_msg.get('variables', [])),
                        'tipo_funcion': modelo_msg.get('funcion', {}).get('tipo'),
                        'expresion': modelo_msg.get('funcion', {}).get('expresion'),
                    }

                logger.info(f"Modelo info cargada: {self.modelo_info.get('nombre')}")

        except Exception as e:
            logger.error(f"Error actualizando modelo info: {e}")

    # Métodos para acceder a los datos (thread-safe)

    def get_stats_productor(self) -> Dict[str, Any]:
        """Retorna estadísticas actuales del productor."""
        with self._lock:
            return self.stats_productor.copy()

    def get_stats_consumidores(self) -> Dict[str, Dict[str, Any]]:
        """Retorna estadísticas actuales de todos los consumidores."""
        with self._lock:
            return self.stats_consumidores.copy()

    def get_modelo_info(self) -> Dict[str, Any]:
        """Retorna información del modelo actual."""
        with self._lock:
            return self.modelo_info.copy()

    def get_queue_sizes(self) -> Dict[str, int]:
        """Retorna tamaños actuales de las colas."""
        with self._lock:
            return self.queue_sizes.copy()

    def get_historico_productor(self) -> List[Dict[str, Any]]:
        """Retorna histórico de stats del productor."""
        with self._lock:
            return self.historico_productor.copy()

    def get_historico_consumidores(self) -> Dict[str, List[Dict[str, Any]]]:
        """Retorna histórico de stats de consumidores."""
        with self._lock:
            return self.historico_consumidores.copy()

    def get_last_update(self) -> Optional[datetime]:
        """Retorna timestamp de última actualización."""
        with self._lock:
            return self.last_update

    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna resumen del estado del sistema.

        Returns:
            Diccionario con resumen completo
        """
        with self._lock:
            stats_prod = self.stats_productor.copy()
            stats_cons = self.stats_consumidores.copy()
            modelo = self.modelo_info.copy()
            queues = self.queue_sizes.copy()

        # Calcular totales de consumidores
        total_procesados = sum(
            c.get('escenarios_procesados', 0)
            for c in stats_cons.values()
        )

        tasa_total_consumidores = sum(
            c.get('tasa_procesamiento', 0)
            for c in stats_cons.values()
        )

        return {
            'productor': stats_prod,
            'consumidores': stats_cons,
            'modelo': modelo,
            'queues': queues,
            'num_consumidores': len(stats_cons),
            'total_procesados': total_procesados,
            'tasa_total_consumidores': tasa_total_consumidores,
            'last_update': self.last_update
        }


__all__ = ['DataManager']
