#!/usr/bin/env python3
"""
Script CLI para ejecutar el productor de simulación Monte Carlo.

Uso:
    python run_producer.py <archivo_modelo> [opciones]

Ejemplos:
    python run_producer.py modelos/ejemplo_simple.ini
    python run_producer.py modelos/ejemplo_simple.ini --escenarios 5000
    python run_producer.py modelos/ejemplo_simple.ini --host localhost --port 5672
"""

import sys
import argparse
import logging
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.producer.producer import run_producer, ProducerError


def main():
    parser = argparse.ArgumentParser(
        description='Productor de simulación Monte Carlo distribuida',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  %(prog)s modelos/ejemplo_simple.ini
  %(prog)s modelos/ejemplo_simple.ini --escenarios 5000
  %(prog)s modelos/ejemplo_simple.ini --host rabbitmq.local --port 5672
  %(prog)s modelos/ejemplo_simple.ini --verbose
        """
    )

    parser.add_argument(
        'modelo',
        type=str,
        help='Ruta al archivo .ini del modelo'
    )

    parser.add_argument(
        '-n', '--escenarios',
        type=int,
        default=None,
        help='Número de escenarios a generar (override del archivo)'
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

    # Validar archivo de modelo
    if not Path(args.modelo).exists():
        logger.error(f"Archivo de modelo no encontrado: {args.modelo}")
        return 1

    # Banner
    if not args.quiet:
        print()
        print("=" * 60)
        print("  PRODUCTOR DE SIMULACIÓN MONTE CARLO")
        print("=" * 60)
        print()

    # Ejecutar productor
    try:
        run_producer(
            archivo_modelo=args.modelo,
            num_escenarios=args.escenarios,
            rabbitmq_host=args.host,
            rabbitmq_port=args.port
        )

        if not args.quiet:
            print()
            print("✅ Productor completado exitosamente")
            print()

        return 0

    except ProducerError as e:
        logger.error(f"Error en productor: {e}")
        if not args.quiet:
            print()
            print(f"❌ Error: {e}")
            print()
        return 1

    except KeyboardInterrupt:
        logger.warning("Productor interrumpido por el usuario")
        if not args.quiet:
            print()
            print("⚠️  Productor interrumpido")
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
