"""
Configuración de logging estructurado para el sistema VarP.

Proporciona logging con:
- Formato estructurado con contexto
- Rotación de archivos
- Niveles diferentes por componente
- Soporte para logging en JSON
"""

import logging
import logging.config
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from src.common.config import BASE_DIR, LogConfig


class StructuredFormatter(logging.Formatter):
    """
    Formatter que produce logs estructurados en formato JSON.

    Incluye contexto adicional:
    - timestamp ISO
    - nivel
    - logger name
    - mensaje
    - exception info si existe
    - campos extra personalizados
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea el record como JSON estructurado.

        Args:
            record: LogRecord a formatear

        Returns:
            String JSON con el log estructurado
        """
        # Construir log estructurado
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Añadir exception info si existe
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__ if record.exc_info[0] else None,
                'message': str(record.exc_info[1]) if record.exc_info[1] else None,
                'traceback': self.formatException(record.exc_info) if record.exc_info else None
            }

        # Añadir campos extra personalizados
        # Cualquier atributo extra añadido al record se incluirá
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'created', 'filename', 'funcName',
                'levelname', 'levelno', 'lineno', 'module', 'msecs',
                'message', 'pathname', 'process', 'processName',
                'relativeCreated', 'thread', 'threadName', 'exc_info',
                'exc_text', 'stack_info'
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_data['extra'] = extra_fields

        return json.dumps(log_data, ensure_ascii=False)


class ColoredFormatter(logging.Formatter):
    """
    Formatter que añade colores para mejorar legibilidad en consola.
    """

    # Códigos ANSI para colores
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Formatea el record con colores.

        Args:
            record: LogRecord a formatear

        Returns:
            String formateado con colores ANSI
        """
        # Obtener color para el nivel
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']

        # Formatear con color
        record.levelname = f"{color}{record.levelname}{reset}"

        return super().format(record)


def setup_logging(
    log_level: str = None,
    log_format: str = None,
    log_file: Optional[str] = None,
    enable_console: bool = True
) -> None:
    """
    Configura el sistema de logging para toda la aplicación.

    Args:
        log_level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Formato de logging ('json' o 'colored')
        log_file: Ruta al archivo de logs (None = no guardar en archivo)
        enable_console: Si habilitar logging en consola
    """
    # Valores por defecto desde config
    log_level = log_level or LogConfig.LEVEL
    log_format = log_format or LogConfig.FORMAT

    # Crear directorio de logs si no existe
    logs_dir = BASE_DIR / 'logs'
    logs_dir.mkdir(exist_ok=True)

    # Configuración base
    config: Dict[str, Any] = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': StructuredFormatter,
            },
            'colored': {
                '()': ColoredFormatter,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'simple': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'handlers': {},
        'root': {
            'level': log_level,
            'handlers': []
        },
        'loggers': {
            # Loggers específicos por componente
            'src.producer': {
                'level': log_level,
                'handlers': [],
                'propagate': False
            },
            'src.consumer': {
                'level': log_level,
                'handlers': [],
                'propagate': False
            },
            'src.common': {
                'level': log_level,
                'handlers': [],
                'propagate': False
            },
            'src.dashboard': {
                'level': log_level,
                'handlers': [],
                'propagate': False
            },
            # Reducir verbosidad de librerías externas
            'pika': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': False
            },
            'urllib3': {
                'level': 'WARNING',
                'handlers': [],
                'propagate': False
            }
        }
    }

    # Handler de consola
    if enable_console:
        formatter = 'colored' if log_format == 'colored' else 'simple'
        config['handlers']['console'] = {
            'class': 'logging.StreamHandler',
            'formatter': formatter,
            'stream': 'ext://sys.stdout'
        }
        config['root']['handlers'].append('console')

        # Añadir a loggers específicos
        for logger_name in config['loggers']:
            if logger_name not in ['pika', 'urllib3']:
                config['loggers'][logger_name]['handlers'].append('console')

    # Handler de archivo (JSON estructurado)
    if log_file:
        log_path = logs_dir / log_file
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'json',
            'filename': str(log_path),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8'
        }
        config['root']['handlers'].append('file')

        # Añadir a loggers específicos
        for logger_name in config['loggers']:
            config['loggers'][logger_name]['handlers'].append('file')

    # Handler de archivo de errores (solo ERROR y CRITICAL)
    error_log_path = logs_dir / 'errors.log'
    config['handlers']['error_file'] = {
        'class': 'logging.handlers.RotatingFileHandler',
        'formatter': 'json',
        'filename': str(error_log_path),
        'maxBytes': 10485760,  # 10MB
        'backupCount': 5,
        'encoding': 'utf-8',
        'level': 'ERROR'
    }
    config['root']['handlers'].append('error_file')

    # Añadir a loggers específicos
    for logger_name in config['loggers']:
        config['loggers'][logger_name]['handlers'].append('error_file')

    # Aplicar configuración
    logging.config.dictConfig(config)

    logger = logging.getLogger(__name__)
    logger.info(
        f"Sistema de logging configurado",
        extra={
            'log_level': log_level,
            'log_format': log_format,
            'log_file': log_file,
            'enable_console': enable_console
        }
    )


def get_logger(name: str, **extra_context) -> logging.LoggerAdapter:
    """
    Obtiene un logger con contexto extra permanente.

    Args:
        name: Nombre del logger
        **extra_context: Contexto adicional a incluir en todos los logs

    Returns:
        LoggerAdapter con contexto extra

    Example:
        >>> logger = get_logger('my_module', consumer_id='C-123', model_id='M-456')
        >>> logger.info('Processing scenario')  # Incluirá consumer_id y model_id
    """
    base_logger = logging.getLogger(name)
    return logging.LoggerAdapter(base_logger, extra_context)


__all__ = [
    'StructuredFormatter',
    'ColoredFormatter',
    'setup_logging',
    'get_logger'
]
