"""
Consumidor de simulación Monte Carlo.

Lee el modelo, consume escenarios y ejecuta el modelo publicando resultados.

Fase 4.1: Incluye manejo avanzado de errores:
- Dead Letter Queue (DLQ) para mensajes fallidos
- Reintentos automáticos (máximo 3 intentos)
- Logging estructurado con contexto
- Manejo detallado de excepciones
"""

import time
import logging
import uuid
import pika
from typing import Dict, Any, Optional

from src.common.config import QueueConfig, ConsumerConfig
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError
from src.common.expression_evaluator import SafeExpressionEvaluator, ExpressionEvaluationError
from src.common.python_executor import PythonExecutor, TimeoutException, SecurityException

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
        self.tipo_funcion: Optional[str] = None  # 'expresion' o 'codigo'

        # Para tipo='expresion'
        self.evaluator: Optional[SafeExpressionEvaluator] = None
        self.expresion: Optional[str] = None

        # Para tipo='codigo'
        self.python_executor: Optional[PythonExecutor] = None
        self.codigo: Optional[str] = None

        # Estadísticas
        self.escenarios_procesados = 0
        self.tiempo_inicio: Optional[float] = None
        self.tiempo_ultimo_escenario: Optional[float] = None
        self.tiempos_ejecucion = []

        # Estadísticas de errores (Fase 4.1)
        self.errores_totales = 0
        self.reintentos_totales = 0
        self.mensajes_a_dlq = 0
        self.errores_por_tipo: Dict[str, int] = {}

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

        # Extraer tipo de función del modelo
        self.tipo_funcion = self.modelo_msg['funcion']['tipo']

        if self.tipo_funcion not in ['expresion', 'codigo']:
            raise ConsumerError(
                f"Tipo de función '{self.tipo_funcion}' no soportado. "
                f"Válidos: 'expresion', 'codigo'"
            )

        # Configurar según el tipo
        if self.tipo_funcion == 'expresion':
            # Usar expression evaluator
            self.expresion = self.modelo_msg['funcion']['expresion']
            self.evaluator = SafeExpressionEvaluator()

            logger.info(
                f"Consumidor {self.consumer_id}: Modelo cargado exitosamente\n"
                f"  Modelo ID: {self.modelo_msg['modelo_id']}\n"
                f"  Versión: {self.modelo_msg['version']}\n"
                f"  Tipo: expresion\n"
                f"  Expresión: {self.expresion}"
            )

        elif self.tipo_funcion == 'codigo':
            # Usar Python executor (Fase 3)
            self.codigo = self.modelo_msg['funcion']['codigo']
            self.python_executor = PythonExecutor(timeout=30.0)

            # Log solo primeras 5 líneas del código
            codigo_preview = '\n'.join(self.codigo.split('\n')[:5])
            if len(self.codigo.split('\n')) > 5:
                codigo_preview += "\n..."

            logger.info(
                f"Consumidor {self.consumer_id}: Modelo cargado exitosamente\n"
                f"  Modelo ID: {self.modelo_msg['modelo_id']}\n"
                f"  Versión: {self.modelo_msg['version']}\n"
                f"  Tipo: codigo\n"
                f"  Código (preview):\n{codigo_preview}"
            )

        self.modelo_cargado = True

    def _procesar_escenario_callback(self, ch, method, properties, body) -> None:
        """
        Callback para procesar cada escenario.

        FASE 4.1: Incluye lógica de reintentos automáticos:
        - Verifica contador de reintentos en headers
        - Reintenta hasta MAX_RETRIES (3 intentos)
        - Envía a DLQ si excede reintentos
        - Tracking detallado de errores

        Args:
            ch: Canal
            method: Método
            properties: Propiedades del mensaje
            body: Cuerpo del mensaje (JSON)
        """
        import json

        # FASE 4.1: Obtener contador de reintentos del header
        retry_count = 0
        if properties.headers:
            retry_count = properties.headers.get('x-retry-count', 0)

        escenario_id = None

        try:
            inicio = time.time()

            # Parsear escenario
            escenario = json.loads(body)
            escenario_id = escenario.get('escenario_id', 'unknown')

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

            # ACK del mensaje (éxito)
            ch.basic_ack(delivery_tag=method.delivery_tag)

            # Si fue un reintento exitoso, loggear
            if retry_count > 0:
                logger.info(
                    f"Consumidor {self.consumer_id}: Escenario {escenario_id} "
                    f"procesado exitosamente después de {retry_count} reintentos"
                )

        # FASE 4.1: Excepciones NO recuperables (enviar directo a DLQ)
        except ExpressionEvaluationError as e:
            self._handle_error(
                error=e,
                error_type='ExpressionEvaluationError',
                escenario_id=escenario_id,
                retry_count=retry_count,
                recoverable=False,  # No recuperable, enviar a DLQ
                ch=ch,
                method=method,
                properties=properties,
                body=body
            )

        except TimeoutException as e:
            self._handle_error(
                error=e,
                error_type='TimeoutException',
                escenario_id=escenario_id,
                retry_count=retry_count,
                recoverable=False,  # Timeout no es recuperable
                ch=ch,
                method=method,
                properties=properties,
                body=body
            )

        except SecurityException as e:
            self._handle_error(
                error=e,
                error_type='SecurityException',
                escenario_id=escenario_id,
                retry_count=retry_count,
                recoverable=False,  # Violación de seguridad no es recuperable
                ch=ch,
                method=method,
                properties=properties,
                body=body
            )

        # FASE 4.1: Excepciones potencialmente recuperables (reintentar)
        except Exception as e:
            self._handle_error(
                error=e,
                error_type=type(e).__name__,
                escenario_id=escenario_id,
                retry_count=retry_count,
                recoverable=True,  # Reintentar
                ch=ch,
                method=method,
                properties=properties,
                body=body
            )

    def _handle_error(
        self,
        error: Exception,
        error_type: str,
        escenario_id: Optional[str],
        retry_count: int,
        recoverable: bool,
        ch,
        method,
        properties,
        body
    ) -> None:
        """
        FASE 4.1: Maneja errores con lógica de reintentos.

        Args:
            error: La excepción capturada
            error_type: Tipo de error (para estadísticas)
            escenario_id: ID del escenario que falló
            retry_count: Número de reintentos actuales
            recoverable: Si el error es potencialmente recuperable
            ch: Canal RabbitMQ
            method: Método del mensaje
            properties: Propiedades del mensaje
            body: Cuerpo del mensaje
        """
        # Actualizar estadísticas de errores
        self.errores_totales += 1
        self.errores_por_tipo[error_type] = self.errores_por_tipo.get(error_type, 0) + 1

        # Loggear error con contexto
        logger.error(
            f"Consumidor {self.consumer_id}: Error procesando escenario {escenario_id}",
            extra={
                'consumer_id': self.consumer_id,
                'escenario_id': escenario_id,
                'error_type': error_type,
                'retry_count': retry_count,
                'recoverable': recoverable
            },
            exc_info=True
        )

        # Decidir acción basado en recoverability y retry_count
        if not recoverable:
            # Error NO recuperable: enviar directo a DLQ
            logger.warning(
                f"Consumidor {self.consumer_id}: Error NO recuperable ({error_type}), "
                f"enviando escenario {escenario_id} a DLQ"
            )
            self.mensajes_a_dlq += 1
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        elif retry_count >= ConsumerConfig.MAX_RETRIES:
            # Agotados los reintentos: enviar a DLQ
            logger.warning(
                f"Consumidor {self.consumer_id}: Agotados {ConsumerConfig.MAX_RETRIES} reintentos "
                f"para escenario {escenario_id}, enviando a DLQ"
            )
            self.mensajes_a_dlq += 1
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

        else:
            # Reintentar: republicar mensaje con contador incrementado
            logger.info(
                f"Consumidor {self.consumer_id}: Reintentando escenario {escenario_id} "
                f"(intento {retry_count + 1}/{ConsumerConfig.MAX_RETRIES})"
            )
            self.reintentos_totales += 1

            # Incrementar contador de reintentos
            new_retry_count = retry_count + 1

            # Crear nuevas propiedades con header actualizado
            new_headers = properties.headers.copy() if properties.headers else {}
            new_headers['x-retry-count'] = new_retry_count
            new_headers['x-last-error'] = error_type
            new_headers['x-consumer-id'] = self.consumer_id

            new_properties = pika.BasicProperties(
                delivery_mode=2,  # Persistente
                content_type='application/json',
                headers=new_headers
            )

            # Republicar mensaje con delay (esperar antes de reintentar)
            # Nota: En RabbitMQ no hay delay nativo, pero podríamos usar una cola temporal
            # Por ahora, republicamos directamente
            ch.basic_publish(
                exchange='',
                routing_key=QueueConfig.ESCENARIOS,
                body=body,
                properties=new_properties
            )

            # ACK del mensaje original (ya lo republicamos)
            ch.basic_ack(delivery_tag=method.delivery_tag)

    def _ejecutar_modelo(self, escenario: Dict[str, Any]) -> Any:
        """
        Ejecuta la función del modelo con los valores del escenario.

        Soporta dos tipos:
        - tipo='expresion': Evalúa expresión con SafeExpressionEvaluator
        - tipo='codigo': Ejecuta código Python con PythonExecutor

        Args:
            escenario: Escenario con valores de variables

        Returns:
            Resultado de evaluar la expresión o ejecutar el código

        Raises:
            ExpressionEvaluationError: Si hay error evaluando expresión
            TimeoutException: Si el código excede el timeout
            SecurityException: Si el código contiene operaciones no permitidas
        """
        valores = escenario['valores']

        if self.tipo_funcion == 'expresion':
            # Evaluar expresión con valores del escenario
            resultado = self.evaluator.evaluate(self.expresion, valores)

        elif self.tipo_funcion == 'codigo':
            # Ejecutar código Python con valores del escenario
            # El código debe definir una variable 'resultado' con el resultado final
            resultado = self.python_executor.execute(
                code=self.codigo,
                variables=valores,
                result_var='resultado'
            )

        else:
            raise ConsumerError(f"Tipo de función desconocido: {self.tipo_funcion}")

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
        # Optimización Fase 4: Mensaje simplificado (removida metadata redundante)
        # Reduce tamaño de mensaje ~15-20%
        mensaje = {
            'escenario_id': escenario['escenario_id'],
            'consumer_id': self.consumer_id,
            'resultado': resultado,
            'tiempo_ejecucion': tiempo_ejecucion
        }

        self.client.publish(
            queue_name=QueueConfig.RESULTADOS,
            message=mensaje,
            persistent=True
        )

    def _publicar_stats(self) -> None:
        """
        Publica estadísticas del consumidor en la cola de stats.

        FASE 4.1: Incluye nuevas estadísticas de errores:
        - Consumer ID
        - Escenarios procesados
        - Tiempo del último escenario
        - Tiempo promedio de ejecución
        - Tasa de procesamiento
        - Estado
        - Errores totales (FASE 4.1)
        - Reintentos totales (FASE 4.1)
        - Mensajes a DLQ (FASE 4.1)
        - Errores por tipo (FASE 4.1)
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
            'tiempo_activo': tiempo_transcurrido,
            # FASE 4.1: Estadísticas de errores
            'errores_totales': self.errores_totales,
            'reintentos_totales': self.reintentos_totales,
            'mensajes_a_dlq': self.mensajes_a_dlq,
            'errores_por_tipo': self.errores_por_tipo
        }

        self.client.publish(
            queue_name=QueueConfig.STATS_CONSUMIDORES,
            message=stats,
            persistent=False  # Stats no necesitan persistencia
        )

        logger.debug(
            f"Consumidor {self.consumer_id}: Stats publicadas - "
            f"{self.escenarios_procesados} procesados, "
            f"tasa={tasa:.2f} esc/s, "
            f"errores={self.errores_totales}, "
            f"reintentos={self.reintentos_totales}, "
            f"dlq={self.mensajes_a_dlq}"
        )

    def _finalizar(self) -> None:
        """
        Finaliza el consumidor publicando estadísticas finales.

        FASE 4.1: Incluye estadísticas de errores en el resumen.
        """
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

            # FASE 4.1: Mostrar estadísticas de errores
            if self.errores_totales > 0:
                logger.info("-" * 60)
                logger.info("ESTADÍSTICAS DE ERRORES:")
                logger.info(f"  Total errores: {self.errores_totales}")
                logger.info(f"  Reintentos: {self.reintentos_totales}")
                logger.info(f"  Mensajes a DLQ: {self.mensajes_a_dlq}")
                if self.errores_por_tipo:
                    logger.info("  Errores por tipo:")
                    for tipo, count in self.errores_por_tipo.items():
                        logger.info(f"    - {tipo}: {count}")

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
