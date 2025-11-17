#!/usr/bin/env python3
"""
Script CLI para ejecutar el consumidor de simulación Monte Carlo.

Uso:
    python run_consumer.py [opciones]

Ejemplos:
    python run_consumer.py
    python run_consumer.py --id C1
    python run_consumer.py --host localhost --port 5672
    python run_consumer.py --max-escenarios 100
"""

import sys
import argparse
import logging
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.consumer.consumer import run_consumer, ConsumerError


def main():
    parser = argparse.ArgumentParser(
        description='Consumidor de simulación Monte Carlo distribuida',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s
  %(prog)s --id C1
  %(prog)s --id C2 --verbose
  %(prog)s --host rabbitmq.local --port 5672
  %(prog)s --max-escenarios 100

El consumidor se ejecutará continuamente procesando escenarios hasta:
  - Recibir Ctrl+C (KeyboardInterrupt)
  - Alcanzar max-escenarios (si se especifica)
  - No haya más escenarios en la cola

Para ejecutar múltiples consumidores en paralelo:
  python run_consumer.py --id C1 &
  python run_consumer.py --id C2 &
  python run_consumer.py --id C3 &
        """
    )

    parser.add_argument(
        '--id',
        type=str,
        default=None,
        help='ID único del consumidor (se genera automáticamente si no se provee)'
    )

    parser.add_argument(
        '--max-escenarios',
        type=int,
        default=None,
        help='Número máximo de escenarios a procesar (default: ilimitado)'
    )

    parser.add_argument(
        '--host',
        type=str,
        default=None,
        help='Host de RabbitMQ (default: desde .env)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=None,
        help='Puerto de RabbitMQ (default: desde .env)'
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
        print("  CONSUMIDOR DE SIMULACIÓN MONTE CARLO")
        print("=" * 60)
        if args.id:
            print(f"  ID: {args.id}")
        if args.max_escenarios:
            print(f"  Máximo escenarios: {args.max_escenarios}")
        print()

    # Ejecutar consumidor
    try:
        run_consumer(
            consumer_id=args.id,
            rabbitmq_host=args.host,
            rabbitmq_port=args.port,
            max_escenarios=args.max_escenarios
        )

        if not args.quiet:
            print()
            print("✅ Consumidor finalizado exitosamente")
            print()

        return 0

    except ConsumerError as e:
        logger.error(f"Error en consumidor: {e}")
        if not args.quiet:
            print()
            print(f"❌ Error: {e}")
            print()
        return 1

    except KeyboardInterrupt:
        logger.warning("Consumidor interrumpido por el usuario")
        if not args.quiet:
            print()
            print("⚠️  Consumidor interrumpido")
            print()
        return 130

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        if not args.quiet:
            print()
            print(f"❌ Error inesperado: {e}")
            print()
        return 1


if __name__ == '__main__':
    sys.exit(main())
