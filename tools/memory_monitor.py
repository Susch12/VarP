"""
Herramienta de monitoreo de memoria y performance del sistema VarP.

Analiza:
- Uso de memoria de componentes
- Tamaño de mensajes en RabbitMQ
- Frecuencia de publicación de stats
- Performance de productor/consumidor
"""

import time
import sys
import psutil
import json
from typing import Dict, Any, List
from datetime import datetime

from src.common.rabbitmq_client import RabbitMQClient
from src.common.config import QueueConfig


class MemoryMonitor:
    """Monitor de uso de memoria y performance."""

    def __init__(self):
        self.process = psutil.Process()
        self.measurements: List[Dict[str, Any]] = []

    def get_memory_info(self) -> Dict[str, float]:
        """
        Obtiene información de memoria del proceso actual.

        Returns:
            Dict con memoria RSS, VMS, y porcentaje
        """
        mem_info = self.process.memory_info()
        mem_percent = self.process.memory_percent()

        return {
            'rss_mb': mem_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': mem_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': mem_percent,
            'timestamp': time.time()
        }

    def measure(self, label: str = "") -> Dict[str, float]:
        """
        Toma una medición de memoria.

        Args:
            label: Etiqueta para la medición

        Returns:
            Dict con información de memoria
        """
        info = self.get_memory_info()
        info['label'] = label

        self.measurements.append(info)

        return info

    def print_measurement(self, label: str = ""):
        """Imprime medición de memoria."""
        info = self.measure(label)

        print(f"[{label}] Memoria: RSS={info['rss_mb']:.2f}MB, "
              f"VMS={info['vms_mb']:.2f}MB, {info['percent']:.2f}%")

    def get_memory_growth(self) -> Dict[str, float]:
        """
        Calcula crecimiento de memoria desde primera medición.

        Returns:
            Dict con deltas de memoria
        """
        if len(self.measurements) < 2:
            return {'rss_mb': 0, 'vms_mb': 0, 'percent': 0}

        first = self.measurements[0]
        last = self.measurements[-1]

        return {
            'rss_mb': last['rss_mb'] - first['rss_mb'],
            'vms_mb': last['vms_mb'] - first['vms_mb'],
            'percent': last['percent'] - first['percent'],
            'time_seconds': last['timestamp'] - first['timestamp']
        }

    def print_summary(self):
        """Imprime resumen de uso de memoria."""
        if not self.measurements:
            print("No hay mediciones")
            return

        growth = self.get_memory_growth()

        print("\n" + "=" * 60)
        print("RESUMEN DE MEMORIA")
        print("=" * 60)
        print(f"Mediciones: {len(self.measurements)}")
        print(f"Tiempo transcurrido: {growth['time_seconds']:.2f}s")
        print(f"\nMemoria inicial:")
        print(f"  RSS: {self.measurements[0]['rss_mb']:.2f}MB")
        print(f"  VMS: {self.measurements[0]['vms_mb']:.2f}MB")
        print(f"\nMemoria final:")
        print(f"  RSS: {self.measurements[-1]['rss_mb']:.2f}MB")
        print(f"  VMS: {self.measurements[-1]['vms_mb']:.2f}MB")
        print(f"\nCrecimiento:")
        print(f"  RSS: {growth['rss_mb']:+.2f}MB ({growth['percent']:+.2f}%)")
        print(f"  VMS: {growth['vms_mb']:+.2f}MB")
        print("=" * 60)


class MessageSizeAnalyzer:
    """Analiza tamaño de mensajes en RabbitMQ."""

    def __init__(self, rabbitmq_client: RabbitMQClient):
        self.client = rabbitmq_client

    def analyze_message_size(self, queue_name: str, num_samples: int = 10) -> Dict[str, Any]:
        """
        Analiza tamaño de mensajes en una cola.

        Args:
            queue_name: Nombre de la cola
            num_samples: Número de mensajes a samplear

        Returns:
            Dict con estadísticas de tamaño
        """
        sizes = []
        messages = []

        for _ in range(num_samples):
            msg = self.client.get_message(queue_name, auto_ack=False)
            if not msg:
                break

            # Serializar a JSON para medir tamaño real
            json_str = json.dumps(msg)
            size_bytes = len(json_str.encode('utf-8'))

            sizes.append(size_bytes)
            messages.append(msg)

        if not sizes:
            return {
                'queue': queue_name,
                'samples': 0,
                'avg_bytes': 0,
                'min_bytes': 0,
                'max_bytes': 0,
                'total_kb': 0
            }

        return {
            'queue': queue_name,
            'samples': len(sizes),
            'avg_bytes': sum(sizes) / len(sizes),
            'min_bytes': min(sizes),
            'max_bytes': max(sizes),
            'total_kb': sum(sizes) / 1024,
            'messages': messages  # Para análisis detallado
        }

    def analyze_all_queues(self) -> Dict[str, Dict[str, Any]]:
        """
        Analiza todas las colas principales.

        Returns:
            Dict con análisis de cada cola
        """
        results = {}

        queues_to_analyze = [
            QueueConfig.MODELO,
            QueueConfig.ESCENARIOS,
            QueueConfig.RESULTADOS,
            QueueConfig.STATS_PRODUCTOR,
            QueueConfig.STATS_CONSUMIDORES
        ]

        for queue in queues_to_analyze:
            try:
                queue_size = self.client.get_queue_size(queue)
                if queue_size > 0:
                    analysis = self.analyze_message_size(queue, num_samples=min(5, queue_size))
                    results[queue] = analysis
            except Exception as e:
                print(f"Error analizando {queue}: {e}")

        return results

    def print_analysis(self, results: Dict[str, Dict[str, Any]]):
        """Imprime análisis de tamaños de mensajes."""
        print("\n" + "=" * 60)
        print("ANÁLISIS DE TAMAÑO DE MENSAJES")
        print("=" * 60)

        for queue, analysis in results.items():
            if analysis['samples'] == 0:
                continue

            print(f"\n{queue}:")
            print(f"  Muestras: {analysis['samples']}")
            print(f"  Promedio: {analysis['avg_bytes']:.0f} bytes ({analysis['avg_bytes']/1024:.2f} KB)")
            print(f"  Mínimo: {analysis['min_bytes']} bytes")
            print(f"  Máximo: {analysis['max_bytes']} bytes")

        print("=" * 60)

    def identify_optimization_opportunities(self, results: Dict[str, Dict[str, Any]]) -> List[str]:
        """
        Identifica oportunidades de optimización.

        Args:
            results: Resultados del análisis

        Returns:
            Lista de recomendaciones
        """
        recommendations = []

        for queue, analysis in results.items():
            if analysis['samples'] == 0:
                continue

            avg_kb = analysis['avg_bytes'] / 1024

            # Si mensajes > 10KB, investigar
            if avg_kb > 10:
                recommendations.append(
                    f"⚠️  {queue}: Mensajes grandes ({avg_kb:.2f} KB). "
                    "Considerar reducir payload o comprimir."
                )

            # Si mensajes > 100KB, crítico
            if avg_kb > 100:
                recommendations.append(
                    f"🔴 {queue}: Mensajes MUY grandes ({avg_kb:.2f} KB). "
                    "CRÍTICO: Optimizar inmediatamente."
                )

        return recommendations


class StatsFrequencyAnalyzer:
    """Analiza frecuencia de publicación de estadísticas."""

    def __init__(self, rabbitmq_client: RabbitMQClient):
        self.client = rabbitmq_client

    def analyze_stats_frequency(self, queue_name: str, duration_seconds: int = 10) -> Dict[str, Any]:
        """
        Analiza frecuencia de publicación de stats.

        Args:
            queue_name: Cola de stats a analizar
            duration_seconds: Duración del análisis

        Returns:
            Dict con análisis de frecuencia
        """
        initial_size = self.client.get_queue_size(queue_name)

        print(f"Analizando {queue_name} por {duration_seconds}s...")
        time.sleep(duration_seconds)

        final_size = self.client.get_queue_size(queue_name)

        messages_per_second = (final_size - initial_size) / duration_seconds

        return {
            'queue': queue_name,
            'duration_seconds': duration_seconds,
            'initial_size': initial_size,
            'final_size': final_size,
            'new_messages': final_size - initial_size,
            'messages_per_second': messages_per_second
        }


def run_full_analysis():
    """Ejecuta análisis completo del sistema."""
    print("=" * 60)
    print("ANÁLISIS DE OPTIMIZACIÓN - SISTEMA VarP")
    print("=" * 60)

    # Conectar a RabbitMQ
    print("\nConectando a RabbitMQ...")
    try:
        client = RabbitMQClient()
        client.connect()
        print("✓ Conectado")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("\nAsegúrate de que RabbitMQ esté corriendo:")
        print("  docker run -d --name rabbitmq -p 5672:5672 rabbitmq:3-management")
        return

    # 1. Análisis de tamaño de mensajes
    print("\n1. ANALIZANDO TAMAÑO DE MENSAJES...")
    msg_analyzer = MessageSizeAnalyzer(client)
    results = msg_analyzer.analyze_all_queues()
    msg_analyzer.print_analysis(results)

    # Recomendaciones
    recommendations = msg_analyzer.identify_optimization_opportunities(results)
    if recommendations:
        print("\n📊 RECOMENDACIONES:")
        for rec in recommendations:
            print(f"  {rec}")
    else:
        print("\n✓ Tamaños de mensajes están optimizados")

    # 2. Análisis de estado de colas
    print("\n2. ESTADO DE COLAS:")
    print("-" * 60)
    for queue in [QueueConfig.MODELO, QueueConfig.ESCENARIOS, QueueConfig.RESULTADOS,
                  QueueConfig.STATS_PRODUCTOR, QueueConfig.STATS_CONSUMIDORES]:
        try:
            size = client.get_queue_size(queue)
            print(f"  {queue}: {size} mensajes")
        except:
            print(f"  {queue}: N/A")

    # Cleanup
    client.disconnect()

    print("\n" + "=" * 60)
    print("ANÁLISIS COMPLETADO")
    print("=" * 60)


if __name__ == '__main__':
    run_full_analysis()
