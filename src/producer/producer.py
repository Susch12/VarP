"""
Productor de simulación Monte Carlo.

Genera escenarios únicos basados en un modelo y los publica en RabbitMQ.
"""

import time
import logging
from typing import Dict, Any, Optional
from pathlib import Path

from src.common.config import QueueConfig, ProducerConfig
from src.common.model_parser import parse_model_file, Modelo
from src.common.distributions import DistributionGenerator
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError

logger = logging.getLogger(__name__)


class ProducerError(Exception):
    """Excepción para errores del productor."""
    pass


class Producer:
    """
    Productor de escenarios para simulación Monte Carlo.

    Responsabilidades:
    1. Leer y parsear modelo desde archivo
    2. Publicar modelo en cola_modelo
    3. Generar N escenarios únicos
    4. Publicar escenarios en cola_escenarios
    5. Publicar estadísticas en cola_stats_productor
    """

    def __init__(self, rabbitmq_client: RabbitMQClient):
        """
        Inicializa el productor.

        Args:
            rabbitmq_client: Cliente conectado de RabbitMQ
        """
        self.client = rabbitmq_client
        self.modelo: Optional[Modelo] = None
        self.generator: Optional[DistributionGenerator] = None

        # Estadísticas
        self.escenarios_generados = 0
        self.tiempo_inicio: Optional[float] = None
        self.tiempo_fin: Optional[float] = None

    def ejecutar(self, archivo_modelo: str, num_escenarios: Optional[int] = None) -> None:
        """
        Ejecuta el flujo completo del productor.

        Args:
            archivo_modelo: Ruta al archivo .ini del modelo
            num_escenarios: Número de escenarios a generar (override del archivo)

        Raises:
            ProducerError: Si hay errores en la ejecución
        """
        try:
            self.tiempo_inicio = time.time()

            # 1. Leer modelo
            logger.info(f"Leyendo modelo desde {archivo_modelo}...")
            self.modelo = parse_model_file(archivo_modelo)
            logger.info(f"Modelo '{self.modelo.nombre}' v{self.modelo.version} cargado")

            # Override número de escenarios si se especifica
            if num_escenarios is not None:
                self.modelo.numero_escenarios = num_escenarios

            # 2. Inicializar generador de distribuciones
            self.generator = DistributionGenerator(seed=self.modelo.semilla_aleatoria)
            logger.info(f"Generador inicializado con semilla: {self.modelo.semilla_aleatoria}")

            # 3. Declarar colas
            logger.info("Declarando colas...")
            self.client.declare_queues()

            # 4. Purgar y publicar modelo
            logger.info("Publicando modelo...")
            self._publicar_modelo()

            # 5. Generar y publicar escenarios
            logger.info(f"Generando {self.modelo.numero_escenarios} escenarios...")
            self._generar_y_publicar_escenarios()

            self.tiempo_fin = time.time()
            tiempo_total = self.tiempo_fin - self.tiempo_inicio

            logger.info("=" * 60)
            logger.info("PRODUCTOR COMPLETADO EXITOSAMENTE")
            logger.info("=" * 60)
            logger.info(f"Modelo: {self.modelo.nombre} v{self.modelo.version}")
            logger.info(f"Escenarios generados: {self.escenarios_generados}")
            logger.info(f"Tiempo total: {tiempo_total:.2f}s")
            logger.info(f"Tasa: {self.escenarios_generados / tiempo_total:.2f} esc/s")
            logger.info("=" * 60)

        except Exception as e:
            logger.error(f"Error en productor: {e}", exc_info=True)
            raise ProducerError(f"Error ejecutando productor: {e}")

    def _publicar_modelo(self) -> None:
        """
        Purga cola de modelo y publica el nuevo modelo.

        El modelo incluye:
        - Metadata (nombre, version, etc.)
        - Variables con distribuciones
        - Función a ejecutar
        - Timestamp de publicación
        """
        # Purgar modelo anterior
        purged = self.client.purge_queue(QueueConfig.MODELO)
        if purged > 0:
            logger.info(f"Modelo anterior purgado ({purged} mensajes)")

        # Construir mensaje del modelo
        timestamp = time.time()
        modelo_msg = {
            'modelo_id': f"{self.modelo.nombre}_{int(timestamp)}",
            'version': self.modelo.version,
            'timestamp': timestamp,
            'metadata': {
                'nombre': self.modelo.nombre,
                'descripcion': self.modelo.descripcion,
                'autor': self.modelo.autor,
                'fecha_creacion': self.modelo.fecha_creacion
            },
            'variables': [
                {
                    'nombre': var.nombre,
                    'tipo': var.tipo,
                    'distribucion': var.distribucion,
                    'parametros': var.parametros
                }
                for var in self.modelo.variables
            ],
            'funcion': {
                'tipo': self.modelo.tipo_funcion,
                'expresion': self.modelo.expresion,
                'codigo': self.modelo.codigo
            },
            'simulacion': {
                'numero_escenarios': self.modelo.numero_escenarios,
                'semilla_aleatoria': self.modelo.semilla_aleatoria
            }
        }

        # Publicar modelo
        self.client.publish(
            queue_name=QueueConfig.MODELO,
            message=modelo_msg,
            persistent=True
        )

        logger.info(f"Modelo publicado: {modelo_msg['modelo_id']}")

    def _generar_y_publicar_escenarios(self) -> None:
        """
        Genera y publica N escenarios en la cola.

        Cada escenario incluye:
        - ID único
        - Valores de variables generados según distribuciones
        - Timestamp de generación

        Publica estadísticas cada cierto intervalo.
        """
        total = self.modelo.numero_escenarios
        stats_interval = ProducerConfig.STATS_INTERVAL  # segundos
        ultimo_stats_time = time.time()

        for i in range(total):
            # Generar escenario
            escenario = self._generar_escenario(i)

            # Publicar escenario
            self.client.publish(
                queue_name=QueueConfig.ESCENARIOS,
                message=escenario,
                persistent=True
            )

            self.escenarios_generados += 1

            # Publicar estadísticas periódicamente
            tiempo_actual = time.time()
            if tiempo_actual - ultimo_stats_time >= stats_interval:
                self._publicar_stats()
                ultimo_stats_time = tiempo_actual

            # Log de progreso cada 10%
            if (i + 1) % max(1, total // 10) == 0:
                progreso = (i + 1) / total * 100
                logger.info(f"Progreso: {i + 1}/{total} ({progreso:.1f}%)")

        # Publicar stats finales
        self._publicar_stats()

    def _generar_escenario(self, escenario_id: int) -> Dict[str, Any]:
        """
        Genera un escenario único con valores aleatorios para cada variable.

        Args:
            escenario_id: ID único del escenario

        Returns:
            Diccionario con el escenario
        """
        timestamp = time.time()
        valores = {}

        # Generar valor para cada variable según su distribución
        for var in self.modelo.variables:
            valor = self.generator.generate(
                distribution=var.distribucion,
                params=var.parametros,
                tipo=var.tipo
            )
            valores[var.nombre] = valor

        escenario = {
            'escenario_id': escenario_id,
            'timestamp': timestamp,
            'valores': valores
        }

        return escenario

    def _publicar_stats(self) -> None:
        """
        Publica estadísticas del productor en la cola de stats.

        Incluye:
        - Escenarios generados hasta ahora
        - Total de escenarios
        - Progreso (%)
        - Tasa de generación (esc/s)
        - Tiempo transcurrido
        - Tiempo estimado restante
        """
        if not self.tiempo_inicio:
            return

        tiempo_actual = time.time()
        tiempo_transcurrido = tiempo_actual - self.tiempo_inicio
        progreso = self.escenarios_generados / self.modelo.numero_escenarios

        # Calcular tasa de generación
        if tiempo_transcurrido > 0:
            tasa = self.escenarios_generados / tiempo_transcurrido
        else:
            tasa = 0

        # Calcular tiempo estimado restante
        escenarios_restantes = self.modelo.numero_escenarios - self.escenarios_generados
        if tasa > 0:
            tiempo_restante = escenarios_restantes / tasa
        else:
            tiempo_restante = 0

        stats = {
            'timestamp': tiempo_actual,
            'escenarios_generados': self.escenarios_generados,
            'escenarios_totales': self.modelo.numero_escenarios,
            'progreso': progreso,
            'tasa_generacion': tasa,
            'tiempo_transcurrido': tiempo_transcurrido,
            'tiempo_estimado_restante': tiempo_restante,
            'estado': 'activo' if progreso < 1.0 else 'completado'
        }

        self.client.publish(
            queue_name=QueueConfig.STATS_PRODUCTOR,
            message=stats,
            persistent=False  # Stats no necesitan persistencia
        )

        logger.debug(
            f"Stats publicadas: {self.escenarios_generados}/{self.modelo.numero_escenarios} "
            f"({progreso*100:.1f}%) - {tasa:.2f} esc/s"
        )


def run_producer(archivo_modelo: str, num_escenarios: Optional[int] = None,
                 rabbitmq_host: str = None, rabbitmq_port: int = None) -> None:
    """
    Función de conveniencia para ejecutar el productor.

    Args:
        archivo_modelo: Ruta al archivo .ini del modelo
        num_escenarios: Número de escenarios (override del archivo)
        rabbitmq_host: Host de RabbitMQ (default: desde config)
        rabbitmq_port: Puerto de RabbitMQ (default: desde config)

    Raises:
        ProducerError: Si hay errores en la ejecución
    """
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Crear cliente y productor
    try:
        with RabbitMQClient(host=rabbitmq_host, port=rabbitmq_port) as client:
            client.connect()
            producer = Producer(client)
            producer.ejecutar(archivo_modelo, num_escenarios)

    except RabbitMQConnectionError as e:
        logger.error(f"Error de conexión a RabbitMQ: {e}")
        raise ProducerError(f"No se pudo conectar a RabbitMQ: {e}")

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        raise


__all__ = [
    'Producer',
    'ProducerError',
    'run_producer'
]
