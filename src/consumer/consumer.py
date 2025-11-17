"""
Consumidor de simulación Monte Carlo.

Lee el modelo, consume escenarios y ejecuta el modelo publicando resultados.
"""

import time
import logging
import uuid
from typing import Dict, Any, Optional

from src.common.config import QueueConfig, ConsumerConfig
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.expression_evaluator import SafeExpressionEvaluator, ExpressionEvaluationError

logger = logging.getLogger(__name__)


class ConsumerError(Exception):
    """Excepción para errores del consumidor."""
    pass


class Consumer:
    """
    Consumidor de escenarios para simulación Monte Carlo.

    Responsabilidades:
    1. Leer modelo de cola_modelo (una sola vez al iniciar)
    2. Cargar y compilar expresión del modelo
    3. Consumir escenarios de cola_escenarios
    4. Ejecutar modelo con valores del escenario
    5. Publicar resultado en cola_resultados
    6. Publicar estadísticas en cola_stats_consumidores
    """

    def __init__(self, rabbitmq_client: RabbitMQClient, consumer_id: Optional[str] = None):
        """
        Inicializa el consumidor.

        Args:
            rabbitmq_client: Cliente conectado de RabbitMQ
            consumer_id: ID único del consumidor (se genera si no se provee)
        """
        self.client = rabbitmq_client
        self.consumer_id = consumer_id or f"C-{uuid.uuid4().hex[:8]}"

        # Modelo
        self.modelo_cargado = False
        self.modelo_msg: Optional[Dict[str, Any]] = None
        self.evaluator: Optional[SafeExpressionEvaluator] = None
        self.expresion: Optional[str] = None

        # Estadísticas
        self.escenarios_procesados = 0
        self.tiempo_inicio: Optional[float] = None
        self.tiempo_ultimo_escenario: Optional[float] = None
        self.tiempos_ejecucion = []

    def ejecutar(self, max_escenarios: Optional[int] = None) -> None:
        """
        Ejecuta el flujo completo del consumidor.

        Args:
            max_escenarios: Número máximo de escenarios a procesar (None = infinito)

        Raises:
            ConsumerError: Si hay errores en la ejecución
        """
        try:
            self.tiempo_inicio = time.time()

            logger.info(f"Consumidor {self.consumer_id} iniciando...")

            # 1. Cargar modelo (una sola vez)
            if not self.modelo_cargado:
                self._cargar_modelo()

            # 2. Configurar callback y comenzar a consumir
            logger.info(f"Consumidor {self.consumer_id} esperando escenarios...")

            self.client.channel.basic_qos(prefetch_count=ConsumerConfig.PREFETCH_COUNT)
            self.client.channel.basic_consume(
                queue=QueueConfig.ESCENARIOS,
                on_message_callback=self._procesar_escenario_callback,
                auto_ack=False
            )

            # Comenzar consumo
            self.client.channel.start_consuming()

        except KeyboardInterrupt:
            logger.warning(f"Consumidor {self.consumer_id} interrumpido por usuario")
            self._finalizar()

        except Exception as e:
            logger.error(f"Error en consumidor {self.consumer_id}: {e}", exc_info=True)
            raise ConsumerError(f"Error ejecutando consumidor: {e}")

    def _cargar_modelo(self) -> None:
        """
        Lee el modelo de la cola (una sola vez al iniciar).

        Raises:
            ConsumerError: Si no hay modelo o hay error cargándolo
        """
        logger.info(f"Consumidor {self.consumer_id}: Cargando modelo...")

        # Intentar obtener modelo de la cola
        max_intentos = 5
        for intento in range(max_intentos):
            self.modelo_msg = self.client.get_message(
                queue_name=QueueConfig.MODELO,
                auto_ack=False  # No hacer ACK, dejar para otros consumidores
            )

            if self.modelo_msg:
                break

            if intento < max_intentos - 1:
                logger.warning(
                    f"Consumidor {self.consumer_id}: No hay modelo en cola, "
                    f"reintentando en 2s... ({intento + 1}/{max_intentos})"
                )
                time.sleep(2)
        else:
            raise ConsumerError("No se encontró modelo en la cola después de varios intentos")

        # Volver a publicar el modelo para otros consumidores
        self.client.publish(
            queue_name=QueueConfig.MODELO,
            message=self.modelo_msg,
            persistent=True
        )

        # Extraer expresión del modelo
        funcion_tipo = self.modelo_msg['funcion']['tipo']

        if funcion_tipo != 'expresion':
            raise ConsumerError(
                f"Tipo de función '{funcion_tipo}' no soportado en Fase 1. "
                f"Use tipo='expresion'"
            )

        self.expresion = self.modelo_msg['funcion']['expresion']

        # Crear evaluador
        self.evaluator = SafeExpressionEvaluator()

        self.modelo_cargado = True

        logger.info(
            f"Consumidor {self.consumer_id}: Modelo cargado exitosamente\n"
            f"  Modelo ID: {self.modelo_msg['modelo_id']}\n"
            f"  Versión: {self.modelo_msg['version']}\n"
            f"  Expresión: {self.expresion}"
        )

    def _procesar_escenario_callback(self, ch, method, properties, body) -> None:
        """
        Callback para procesar cada escenario.

        Args:
            ch: Canal
            method: Método
            properties: Propiedades del mensaje
            body: Cuerpo del mensaje (JSON)
        """
        import json

        try:
            inicio = time.time()

            # Parsear escenario
            escenario = json.loads(body)

            # Ejecutar modelo
            resultado = self._ejecutar_modelo(escenario)

            # Calcular tiempo de ejecución
            tiempo_ejecucion = time.time() - inicio
            self.tiempos_ejecucion.append(tiempo_ejecucion)
            self.tiempo_ultimo_escenario = tiempo_ejecucion

            # Publicar resultado
            self._publicar_resultado(escenario, resultado, tiempo_ejecucion)

            # Actualizar estadísticas
            self.escenarios_procesados += 1

            # Publicar estadísticas cada N escenarios
            if self.escenarios_procesados % 10 == 0:
                self._publicar_stats()

            # Log de progreso cada 100
            if self.escenarios_procesados % 100 == 0:
                logger.info(
                    f"Consumidor {self.consumer_id}: "
                    f"{self.escenarios_procesados} escenarios procesados"
                )

            # ACK del mensaje
            ch.basic_ack(delivery_tag=method.delivery_tag)

        except ExpressionEvaluationError as e:
            logger.error(
                f"Consumidor {self.consumer_id}: Error evaluando expresión: {e}"
            )
            # NACK con requeue=False (enviar a DLQ si existe)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        except Exception as e:
            logger.error(
                f"Consumidor {self.consumer_id}: Error procesando escenario: {e}",
                exc_info=True
            )
            # NACK con requeue (reintentar)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def _ejecutar_modelo(self, escenario: Dict[str, Any]) -> Any:
        """
        Ejecuta la expresión del modelo con los valores del escenario.

        Args:
            escenario: Escenario con valores de variables

        Returns:
            Resultado de evaluar la expresión

        Raises:
            ExpressionEvaluationError: Si hay error evaluando
        """
        valores = escenario['valores']

        # Evaluar expresión con valores del escenario
        resultado = self.evaluator.evaluate(self.expresion, valores)

        return resultado

    def _publicar_resultado(self, escenario: Dict[str, Any],
                           resultado: Any, tiempo_ejecucion: float) -> None:
        """
        Publica el resultado en la cola de resultados.

        Args:
            escenario: Escenario procesado
            resultado: Resultado de la ejecución
            tiempo_ejecucion: Tiempo que tomó ejecutar el modelo
        """
        mensaje = {
            'escenario_id': escenario['escenario_id'],
            'consumer_id': self.consumer_id,
            'resultado': resultado,
            'tiempo_ejecucion': tiempo_ejecucion,
            'timestamp': time.time(),
            'metadata': {
                'version_modelo': self.modelo_msg['version']
            }
        }

        self.client.publish(
            queue_name=QueueConfig.RESULTADOS,
            message=mensaje,
            persistent=True
        )

    def _publicar_stats(self) -> None:
        """
        Publica estadísticas del consumidor en la cola de stats.

        Incluye:
        - Consumer ID
        - Escenarios procesados
        - Tiempo del último escenario
        - Tiempo promedio de ejecución
        - Tasa de procesamiento
        - Estado
        """
        if not self.tiempo_inicio:
            return

        tiempo_actual = time.time()
        tiempo_transcurrido = tiempo_actual - self.tiempo_inicio

        # Calcular tasa de procesamiento
        if tiempo_transcurrido > 0:
            tasa = self.escenarios_procesados / tiempo_transcurrido
        else:
            tasa = 0

        # Calcular tiempo promedio
        if self.tiempos_ejecucion:
            tiempo_promedio = sum(self.tiempos_ejecucion) / len(self.tiempos_ejecucion)
        else:
            tiempo_promedio = 0

        stats = {
            'consumer_id': self.consumer_id,
            'timestamp': tiempo_actual,
            'escenarios_procesados': self.escenarios_procesados,
            'tiempo_ultimo_escenario': self.tiempo_ultimo_escenario or 0,
            'tiempo_promedio': tiempo_promedio,
            'tasa_procesamiento': tasa,
            'estado': 'activo',
            'tiempo_activo': tiempo_transcurrido
        }

        self.client.publish(
            queue_name=QueueConfig.STATS_CONSUMIDORES,
            message=stats,
            persistent=False  # Stats no necesitan persistencia
        )

        logger.debug(
            f"Consumidor {self.consumer_id}: Stats publicadas - "
            f"{self.escenarios_procesados} procesados, "
            f"tasa={tasa:.2f} esc/s"
        )

    def _finalizar(self) -> None:
        """Finaliza el consumidor publicando estadísticas finales."""
        if self.escenarios_procesados > 0:
            self._publicar_stats()

            logger.info("=" * 60)
            logger.info(f"CONSUMIDOR {self.consumer_id} FINALIZADO")
            logger.info("=" * 60)
            logger.info(f"Escenarios procesados: {self.escenarios_procesados}")
            if self.tiempo_inicio:
                tiempo_total = time.time() - self.tiempo_inicio
                logger.info(f"Tiempo total: {tiempo_total:.2f}s")
                logger.info(f"Tasa promedio: {self.escenarios_procesados / tiempo_total:.2f} esc/s")
            logger.info("=" * 60)


def run_consumer(consumer_id: Optional[str] = None,
                rabbitmq_host: str = None, rabbitmq_port: int = None,
                max_escenarios: Optional[int] = None) -> None:
    """
    Función de conveniencia para ejecutar el consumidor.

    Args:
        consumer_id: ID único del consumidor
        rabbitmq_host: Host de RabbitMQ (default: desde config)
        rabbitmq_port: Puerto de RabbitMQ (default: desde config)
        max_escenarios: Número máximo de escenarios a procesar

    Raises:
        ConsumerError: Si hay errores en la ejecución
    """
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Crear cliente y consumidor
    try:
        with RabbitMQClient(host=rabbitmq_host, port=rabbitmq_port) as client:
            client.connect()
            consumer = Consumer(client, consumer_id)
            consumer.ejecutar(max_escenarios)

    except RabbitMQConnectionError as e:
        logger.error(f"Error de conexión a RabbitMQ: {e}")
        raise ConsumerError(f"No se pudo conectar a RabbitMQ: {e}")

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        raise


__all__ = [
    'Consumer',
    'ConsumerError',
    'run_consumer'
]
