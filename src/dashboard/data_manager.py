"""
Gestor de datos para el dashboard.

Consume estadísticas de RabbitMQ en un thread separado y mantiene
el estado actualizado para el dashboard.
"""

import threading
import time
import logging
import json
import csv
import io
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import deque

import numpy as np
import pandas as pd
from scipy import stats

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

        # Resultados de la simulación
        # Optimización Fase 4: Limitar memoria usando deque con maxlen
        # self.resultados mantiene últimos 50,000 valores (suficiente para estadísticas confiables)
        self.resultados: deque = deque(maxlen=50000)  # Últimos 50K valores para estadísticas
        self.resultados_raw: deque = deque(maxlen=1000)  # Últimos 1000 resultados completos
        self.estadisticas: Dict[str, Any] = {}  # Estadísticas calculadas

        # Convergencia y análisis avanzado (Fase 2.3)
        self.historico_convergencia: List[Dict[str, Any]] = []  # Media/varianza vs tiempo
        self.tests_normalidad: Dict[str, Any] = {}  # Resultados de tests estadísticos
        self.logs_sistema: deque = deque(maxlen=100)  # Últimos 100 logs

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

                # Consumir resultados
                self._consume_resultados()

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

    def _consume_resultados(self) -> None:
        """Consume resultados de la simulación y calcula estadísticas."""
        try:
            # Consumir todos los resultados disponibles
            nuevos_resultados = 0
            while True:
                resultado_msg = self.client.get_message(
                    QueueConfig.RESULTADOS,
                    auto_ack=True
                )

                if not resultado_msg:
                    break

                resultado_valor = resultado_msg.get('resultado')
                if resultado_valor is None:
                    continue

                with self._lock:
                    # Agregar valor a lista de resultados (deque limita automáticamente a 50K)
                    self.resultados.append(float(resultado_valor))

                    # Agregar resultado completo a lista raw (deque limita automáticamente a 1000)
                    self.resultados_raw.append(resultado_msg)

                nuevos_resultados += 1

                # Pequeña pausa entre mensajes
                time.sleep(0.001)

            # Si hubo nuevos resultados, recalcular estadísticas
            if nuevos_resultados > 0:
                self._calcular_estadisticas()
                logger.debug(f"{nuevos_resultados} nuevos resultados procesados (total: {len(self.resultados)})")

        except Exception as e:
            logger.error(f"Error consumiendo resultados: {e}")

    def _calcular_estadisticas(self) -> None:
        """Calcula estadísticas descriptivas de los resultados."""
        try:
            with self._lock:
                if not self.resultados:
                    self.estadisticas = {}
                    return

                resultados_array = np.array(self.resultados)

                self.estadisticas = {
                    'n': len(self.resultados),
                    'media': float(np.mean(resultados_array)),
                    'mediana': float(np.median(resultados_array)),
                    'desviacion_estandar': float(np.std(resultados_array)),
                    'varianza': float(np.var(resultados_array)),
                    'minimo': float(np.min(resultados_array)),
                    'maximo': float(np.max(resultados_array)),
                    'percentil_25': float(np.percentile(resultados_array, 25)),
                    'percentil_75': float(np.percentile(resultados_array, 75)),
                    'percentil_95': float(np.percentile(resultados_array, 95)),
                    'percentil_99': float(np.percentile(resultados_array, 99)),
                }

                # Calcular intervalo de confianza 95% (media ± 1.96 * std/sqrt(n))
                error_estandar = self.estadisticas['desviacion_estandar'] / np.sqrt(len(resultados_array))
                self.estadisticas['intervalo_confianza_95'] = {
                    'inferior': float(self.estadisticas['media'] - 1.96 * error_estandar),
                    'superior': float(self.estadisticas['media'] + 1.96 * error_estandar)
                }

                # Calcular convergencia (sin lock, ya estamos dentro del lock)
                self._calcular_convergencia_internal(resultados_array)

                # Calcular tests de normalidad (si hay suficientes datos)
                if len(resultados_array) >= 20:
                    self._calcular_tests_normalidad_internal(resultados_array)

                logger.debug(f"Estadísticas calculadas: media={self.estadisticas['media']:.4f}, std={self.estadisticas['desviacion_estandar']:.4f}")

        except Exception as e:
            logger.error(f"Error calculando estadísticas: {e}")

    def _calcular_convergencia_internal(self, resultados_array: np.ndarray) -> None:
        """
        Calcula convergencia de media y varianza vs tiempo.

        NOTA: Este método debe ser llamado DENTRO de un lock.

        Args:
            resultados_array: Array de resultados
        """
        try:
            n = len(resultados_array)

            # Solo calcular si tenemos suficientes datos y es múltiplo de 10
            if n < 30 or n % 10 != 0:
                return

            # Calcular media y varianza acumuladas
            media_acum = float(np.mean(resultados_array))
            var_acum = float(np.var(resultados_array))

            # Agregar punto de convergencia
            punto = {
                'n': n,
                'media': media_acum,
                'varianza': var_acum,
                'timestamp': time.time()
            }

            self.historico_convergencia.append(punto)

            # Mantener solo últimos 100 puntos
            if len(self.historico_convergencia) > 100:
                self.historico_convergencia.pop(0)

            # Agregar log
            self._add_log_internal('info', f"Convergencia calculada: n={n}, media={media_acum:.4f}, var={var_acum:.4f}")

        except Exception as e:
            logger.error(f"Error calculando convergencia: {e}")

    def _calcular_tests_normalidad_internal(self, resultados_array: np.ndarray) -> None:
        """
        Calcula tests de normalidad (Kolmogorov-Smirnov y Shapiro-Wilk).

        NOTA: Este método debe ser llamado DENTRO de un lock.

        Args:
            resultados_array: Array de resultados
        """
        try:
            n = len(resultados_array)

            # Kolmogorov-Smirnov test
            # Comparar con distribución normal con media y std de los datos
            media = np.mean(resultados_array)
            std = np.std(resultados_array)

            # KS test contra N(media, std)
            ks_statistic, ks_pvalue = stats.kstest(
                resultados_array,
                lambda x: stats.norm.cdf(x, loc=media, scale=std)
            )

            # Shapiro-Wilk test (solo si n <= 5000)
            if n <= 5000:
                sw_statistic, sw_pvalue = stats.shapiro(resultados_array)
            else:
                sw_statistic, sw_pvalue = None, None

            # Almacenar resultados
            self.tests_normalidad = {
                'n': n,
                'kolmogorov_smirnov': {
                    'statistic': float(ks_statistic),
                    'pvalue': float(ks_pvalue),
                    'is_normal_alpha_05': ks_pvalue > 0.05,  # No rechazar H0
                    'is_normal_alpha_01': ks_pvalue > 0.01
                },
                'shapiro_wilk': {
                    'statistic': float(sw_statistic) if sw_statistic is not None else None,
                    'pvalue': float(sw_pvalue) if sw_pvalue is not None else None,
                    'is_normal_alpha_05': sw_pvalue > 0.05 if sw_pvalue is not None else None,
                    'is_normal_alpha_01': sw_pvalue > 0.01 if sw_pvalue is not None else None
                } if sw_statistic is not None else None,
                'parametros': {
                    'media_estimada': float(media),
                    'std_estimada': float(std)
                }
            }

            # Agregar log
            resultado = "NORMAL" if ks_pvalue > 0.05 else "NO NORMAL"
            self._add_log_internal('info', f"Test KS: p-value={ks_pvalue:.4f} → {resultado} (α=0.05)")

        except Exception as e:
            logger.error(f"Error calculando tests de normalidad: {e}")

    def _add_log_internal(self, level: str, message: str) -> None:
        """
        Agrega un log al sistema.

        NOTA: Este método debe ser llamado DENTRO de un lock.

        Args:
            level: Nivel del log (info, warning, error)
            message: Mensaje del log
        """
        try:
            log_entry = {
                'timestamp': datetime.now(),
                'level': level,
                'message': message
            }
            self.logs_sistema.append(log_entry)
        except Exception as e:
            logger.error(f"Error agregando log: {e}")

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

    def get_resultados(self) -> List[float]:
        """Retorna lista de todos los resultados."""
        with self._lock:
            return self.resultados.copy()

    def get_resultados_raw(self) -> List[Dict[str, Any]]:
        """Retorna últimos 1000 resultados completos."""
        with self._lock:
            return self.resultados_raw.copy()

    def get_estadisticas(self) -> Dict[str, Any]:
        """Retorna estadísticas descriptivas de los resultados."""
        with self._lock:
            return self.estadisticas.copy()

    def get_historico_convergencia(self) -> List[Dict[str, Any]]:
        """Retorna histórico de convergencia (media/varianza vs tiempo)."""
        with self._lock:
            return self.historico_convergencia.copy()

    def get_tests_normalidad(self) -> Dict[str, Any]:
        """Retorna resultados de tests de normalidad."""
        with self._lock:
            return self.tests_normalidad.copy()

    def get_logs_sistema(self) -> List[Dict[str, Any]]:
        """Retorna logs del sistema."""
        with self._lock:
            return list(self.logs_sistema)

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
            estadisticas = self.estadisticas.copy()

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
            'estadisticas': estadisticas,
            'num_consumidores': len(stats_cons),
            'total_procesados': total_procesados,
            'tasa_total_consumidores': tasa_total_consumidores,
            'num_resultados': len(self.resultados),
            'last_update': self.last_update
        }

    # FASE 4.3: Métodos de exportación

    def export_resultados_json(self) -> str:
        """
        Exporta los resultados y estadísticas a formato JSON.

        Returns:
            String JSON con resultados completos y estadísticas

        Example:
            >>> json_data = data_manager.export_resultados_json()
            >>> with open('resultados.json', 'w') as f:
            ...     f.write(json_data)
        """
        with self._lock:
            # Construir objeto de exportación
            export_data = {
                'metadata': {
                    'fecha_exportacion': datetime.now().isoformat(),
                    'num_resultados': len(self.resultados),
                    'modelo': self.modelo_info.copy(),
                },
                'estadisticas': self.estadisticas.copy(),
                'tests_normalidad': self.tests_normalidad.copy() if self.tests_normalidad else {},
                'resultados': self.resultados.copy(),
                'resultados_detallados': self.resultados_raw.copy(),
                'convergencia': self.historico_convergencia.copy(),
            }

        # Convertir a JSON con formato legible
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Resultados exportados a JSON: {len(self.resultados)} resultados")
        return json_str

    def export_resultados_csv(self, include_metadata: bool = True) -> str:
        """
        Exporta los resultados a formato CSV usando pandas.

        Args:
            include_metadata: Si incluir columnas de metadata (consumer_id, timestamp, etc.)

        Returns:
            String CSV con resultados

        Example:
            >>> csv_data = data_manager.export_resultados_csv()
            >>> with open('resultados.csv', 'w') as f:
            ...     f.write(csv_data)
        """
        with self._lock:
            resultados_raw = self.resultados_raw.copy()
            estadisticas = self.estadisticas.copy()

        if not resultados_raw:
            # Si no hay resultados detallados, usar solo valores
            with self._lock:
                resultados = self.resultados.copy()

            df = pd.DataFrame({
                'resultado': resultados,
                'escenario_id': range(len(resultados))
            })
        else:
            # Crear DataFrame desde resultados detallados
            df = pd.DataFrame(resultados_raw)

            # Reordenar columnas
            base_cols = ['escenario_id', 'resultado']
            other_cols = [c for c in df.columns if c not in base_cols]

            if include_metadata:
                df = df[base_cols + other_cols]
            else:
                df = df[base_cols]

        # Añadir fila de estadísticas al final (como comentario en el CSV)
        csv_buffer = io.StringIO()

        # Escribir estadísticas como comentarios
        if estadisticas:
            csv_buffer.write(f"# Estadísticas Descriptivas\n")
            csv_buffer.write(f"# Número de resultados: {estadisticas.get('n', 0)}\n")
            csv_buffer.write(f"# Media: {estadisticas.get('media', 0):.6f}\n")
            csv_buffer.write(f"# Mediana: {estadisticas.get('mediana', 0):.6f}\n")
            csv_buffer.write(f"# Desviación Estándar: {estadisticas.get('desviacion_estandar', 0):.6f}\n")
            csv_buffer.write(f"# Mínimo: {estadisticas.get('minimo', 0):.6f}\n")
            csv_buffer.write(f"# Máximo: {estadisticas.get('maximo', 0):.6f}\n")
            csv_buffer.write(f"#\n")

        # Escribir datos
        df.to_csv(csv_buffer, index=False, float_format='%.6f')

        csv_str = csv_buffer.getvalue()

        logger.info(f"Resultados exportados a CSV: {len(df)} filas")
        return csv_str

    def export_estadisticas_csv(self) -> str:
        """
        Exporta solo las estadísticas descriptivas a CSV.

        Returns:
            String CSV con estadísticas en formato tabla

        Example:
            >>> csv_data = data_manager.export_estadisticas_csv()
            >>> with open('estadisticas.csv', 'w') as f:
            ...     f.write(csv_data)
        """
        with self._lock:
            estadisticas = self.estadisticas.copy()

        if not estadisticas:
            return "Estadistica,Valor\n# Sin datos disponibles\n"

        # Crear DataFrame con estadísticas
        rows = []
        for key, value in estadisticas.items():
            if key == 'intervalo_confianza_95':
                rows.append(['IC 95% Inferior', value['inferior']])
                rows.append(['IC 95% Superior', value['superior']])
            elif isinstance(value, (int, float)):
                rows.append([key.replace('_', ' ').title(), value])

        df = pd.DataFrame(rows, columns=['Estadistica', 'Valor'])

        csv_str = df.to_csv(index=False, float_format='%.6f')

        logger.info("Estadísticas exportadas a CSV")
        return csv_str

    def export_convergencia_csv(self) -> str:
        """
        Exporta datos de convergencia a CSV.

        Returns:
            String CSV con histórico de convergencia

        Example:
            >>> csv_data = data_manager.export_convergencia_csv()
            >>> with open('convergencia.csv', 'w') as f:
            ...     f.write(csv_data)
        """
        with self._lock:
            convergencia = self.historico_convergencia.copy()

        if not convergencia:
            return "n,media,varianza,timestamp\n# Sin datos de convergencia disponibles\n"

        # Crear DataFrame
        df = pd.DataFrame(convergencia)

        # Convertir timestamp a formato legible
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

        csv_str = df.to_csv(index=False, float_format='%.6f')

        logger.info(f"Convergencia exportada a CSV: {len(df)} puntos")
        return csv_str


__all__ = ['DataManager']
