#!/usr/bin/env python3
"""
Script CLI para ejecutar el dashboard de monitoreo Monte Carlo.

Uso:
    python run_dashboard.py [opciones]

Ejemplos:
    python run_dashboard.py
    python run_dashboard.py --host 0.0.0.0 --port 8050
    python run_dashboard.py --host localhost --port 8080
    python run_dashboard.py --interval 1000  # Actualizar cada 1s
"""

import sys
import argparse
import logging
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.dashboard.app import create_dashboard
from src.common.rabbitmq_client import RabbitMQClient, RabbitMQConnectionError


def main():
    parser = argparse.ArgumentParser(
        description='Dashboard de monitoreo para simulación Monte Carlo distribuida',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s
  %(prog)s --host 0.0.0.0 --port 8050
  %(prog)s --host localhost --port 8080 --verbose
  %(prog)s --interval 1000  # Actualizar cada 1 segundo
  %(prog)s --rabbitmq-host rabbitmq.local

El dashboard se abrirá en el navegador automáticamente.
Para acceder manualmente, visite http://HOST:PORT (ej. http://localhost:8050)

Asegúrese de que RabbitMQ esté corriendo:
  docker-compose up -d rabbitmq

Y que haya una simulación en progreso:
  python run_producer.py --modelo modelos/ejemplo_simple.ini --escenarios 1000
  python run_consumer.py --id C1 &
  python run_consumer.py --id C2 &
        """
    )

    parser.add_argument(
        '--host',
        type=str,
        default='0.0.0.0',
        help='Host donde correr el servidor del dashboard (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8050,
        help='Puerto donde correr el servidor del dashboard (default: 8050)'
    )

    parser.add_argument(
        '--interval',
        type=int,
        default=2000,
        help='Intervalo de actualización en milisegundos (default: 2000 = 2s)'
    )

    parser.add_argument(
        '--rabbitmq-host',
        type=str,
        default=None,
        help='Host de RabbitMQ (default: desde .env)'
    )

    parser.add_argument(
        '--rabbitmq-port',
        type=int,
        default=None,
        help='Puerto de RabbitMQ (default: desde .env)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Modo debug de Dash (recarga automática)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Modo verbose (nivel DEBUG)'
    )

    parser.add_argument(
        '-q', '--quiet',
        action='store_true',
        help='Modo silencioso (solo errores)'
    )

    args = parser.parse_args()

    # Configurar logging
    if args.quiet:
        log_level = logging.ERROR
    elif args.verbose:
        log_level = logging.DEBUG
    else:
        log_level = logging.INFO

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    logger = logging.getLogger(__name__)

    # Banner
    if not args.quiet:
        print()
        print("=" * 60)
        print("  DASHBOARD MONTE CARLO - MONITOREO EN TIEMPO REAL")
        print("=" * 60)
        print(f"  URL: http://{args.host}:{args.port}")
        print(f"  Intervalo de actualización: {args.interval}ms")
        if args.rabbitmq_host:
            print(f"  RabbitMQ: {args.rabbitmq_host}:{args.rabbitmq_port or 5672}")
        print("=" * 60)
        print()

    # Conectar a RabbitMQ
    try:
        logger.info("Conectando a RabbitMQ...")
        client = RabbitMQClient(
            host=args.rabbitmq_host,
            port=args.rabbitmq_port
        )
        client.connect()
        logger.info("✅ Conectado a RabbitMQ")

    except RabbitMQConnectionError as e:
        logger.error(f"❌ Error conectando a RabbitMQ: {e}")
        if not args.quiet:
            print()
            print(f"❌ Error: No se pudo conectar a RabbitMQ")
            print()
            print("⚠️  Asegúrate de que RabbitMQ esté corriendo:")
            print("   docker-compose up -d rabbitmq")
            print()
        return 1

    # Crear y ejecutar dashboard
    try:
        logger.info("Iniciando dashboard...")

        dashboard = create_dashboard(
            rabbitmq_client=client,
            update_interval=args.interval
        )

        if not args.quiet:
            print()
            print("🚀 Dashboard iniciado exitosamente!")
            print()
            print(f"   Abre tu navegador en: http://localhost:{args.port}")
            print()
            print("   Presiona Ctrl+C para detener el dashboard")
            print()

        dashboard.start(
            host=args.host,
            port=args.port,
            debug=args.debug
        )

        return 0

    except KeyboardInterrupt:
        logger.warning("Dashboard interrumpido por el usuario")
        if not args.quiet:
            print()
            print("⚠️  Dashboard detenido")
            print()
        return 130

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        if not args.quiet:
            print()
            print(f"❌ Error inesperado: {e}")
            print()
        return 1

    finally:
        # Desconectar RabbitMQ
        try:
            client.disconnect()
            logger.info("Desconectado de RabbitMQ")
        except:
            pass


if __name__ == '__main__':
    sys.exit(main())
