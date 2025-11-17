# Fase 4.1: Manejo de Errores Avanzado

## 📋 Resumen

La Fase 4.1 implementa un sistema robusto de manejo de errores para el sistema VarP, incluyendo:

- ✅ **Dead Letter Queue (DLQ)** para mensajes fallidos
- ✅ **Reintentos automáticos** (máximo 3 intentos)
- ✅ **Logging estructurado** con formato JSON
- ✅ **Manejo detallado de excepciones** con clasificación recuperable/no recuperable
- ✅ **Estadísticas completas de errores** por tipo y total

## 🎯 Objetivos Cumplidos

### 1. Dead Letter Queue (DLQ) ✅

Se implementaron dos colas DLQ para capturar mensajes que no pueden ser procesados:

- **`cola_dlq_escenarios`**: Captura escenarios que fallaron después de agotar reintentos
- **`cola_dlq_resultados`**: Captura resultados que no pudieron ser publicados

**Configuración en RabbitMQ:**
```python
# Cola de escenarios con DLQ configurada
arguments={
    'x-max-length': 100000,
    'x-dead-letter-exchange': '',
    'x-dead-letter-routing-key': 'cola_dlq_escenarios'
}
```

**Ventajas:**
- Los mensajes fallidos no se pierden
- Permite análisis post-mortem de fallos
- No bloquea la cola principal
- Capacidad de reintento manual desde DLQ

### 2. Reintentos Automáticos ✅

Sistema inteligente de reintentos con las siguientes características:

**Lógica de reintentos:**
```
Intento 1 → Falla → Reintento 1
Intento 2 → Falla → Reintento 2
Intento 3 → Falla → Reintento 3
Intento 4 → Falla → DLQ
```

**Implementación:**
- Contador de reintentos en header `x-retry-count`
- Máximo de 3 reintentos (configurable)
- Información del último error en `x-last-error`
- ID del consumidor que procesó en `x-consumer-id`

**Errores recuperables vs no recuperables:**

| Tipo de Error | Recuperable | Acción |
|--------------|-------------|--------|
| `ValueError`, `TypeError`, etc. | ✅ Sí | Reintentar hasta 3 veces |
| `ExpressionEvaluationError` | ❌ No | DLQ inmediato |
| `TimeoutException` | ❌ No | DLQ inmediato |
| `SecurityException` | ❌ No | DLQ inmediato |

### 3. Logging Estructurado ✅

Sistema de logging profesional con múltiples formatos y destinos.

**Características:**

**a) StructuredFormatter (JSON):**
```json
{
  "timestamp": "2024-01-15T10:30:45.123456",
  "level": "ERROR",
  "logger": "src.consumer.consumer",
  "message": "Error procesando escenario ESC-001",
  "module": "consumer",
  "function": "_procesar_escenario_callback",
  "line": 233,
  "extra": {
    "consumer_id": "C-abc123",
    "escenario_id": "ESC-001",
    "error_type": "ValueError",
    "retry_count": 1,
    "recoverable": true
  },
  "exception": {
    "type": "ValueError",
    "message": "division by zero",
    "traceback": "..."
  }
}
```

**b) ColoredFormatter (Consola):**
- Colores ANSI para cada nivel de log
- Formato legible para desarrollo
- Verde (INFO), Amarillo (WARNING), Rojo (ERROR), etc.

**c) Múltiples destinos:**
```python
setup_logging(
    log_level='INFO',           # Nivel de logging
    log_format='colored',       # 'json' o 'colored'
    log_file='varp.log',        # Archivo principal
    enable_console=True         # Logging a consola
)
```

**Archivos de log generados:**
- `logs/varp.log`: Todos los logs en formato JSON
- `logs/errors.log`: Solo errores (ERROR y CRITICAL)
- Rotación automática a 10MB
- Mantiene 5 backups

### 4. Manejo de Excepciones Mejorado ✅

**Nuevo método `_handle_error()`:**

```python
def _handle_error(
    self,
    error: Exception,
    error_type: str,
    escenario_id: Optional[str],
    retry_count: int,
    recoverable: bool,
    ch, method, properties, body
) -> None:
    """
    Maneja errores con lógica de reintentos.

    Decisiones:
    1. Error NO recuperable → DLQ inmediato
    2. Reintentos agotados (≥3) → DLQ
    3. Error recuperable → Reintentar con contador incrementado
    """
```

**Flujo de decisión:**

```
┌─────────────────┐
│ Error Capturado │
└────────┬────────┘
         │
         ▼
┌────────────────────┐      No     ┌──────────┐
│ ¿Recuperable?      ├────────────►│   DLQ    │
└────────┬───────────┘             └──────────┘
         │ Sí
         ▼
┌────────────────────┐      Sí     ┌──────────┐
│ ¿Reintentos ≥ 3?  ├────────────►│   DLQ    │
└────────┬───────────┘             └──────────┘
         │ No
         ▼
┌────────────────────┐
│ Republicar mensaje │
│ retry_count++      │
└────────────────────┘
```

### 5. Estadísticas de Errores ✅

**Nuevas métricas trackeadas:**

```python
# En Consumer
self.errores_totales = 0           # Total de errores encontrados
self.reintentos_totales = 0        # Total de reintentos realizados
self.mensajes_a_dlq = 0            # Mensajes enviados a DLQ
self.errores_por_tipo = {          # Distribución por tipo de error
    'ValueError': 5,
    'TimeoutException': 2,
    'SecurityException': 1
}
```

**Publicadas en stats del consumidor:**

```json
{
  "consumer_id": "C-abc123",
  "timestamp": 1705320645.123,
  "escenarios_procesados": 1000,
  "tiempo_promedio": 0.015,
  "tasa_procesamiento": 66.67,
  "errores_totales": 8,
  "reintentos_totales": 15,
  "mensajes_a_dlq": 3,
  "errores_por_tipo": {
    "ValueError": 5,
    "TimeoutException": 2,
    "SecurityException": 1
  }
}
```

**Resumen al finalizar:**

```
============================================================
CONSUMIDOR C-abc123 FINALIZADO
============================================================
Escenarios procesados: 1000
Tiempo total: 15.00s
Tasa promedio: 66.67 esc/s
------------------------------------------------------------
ESTADÍSTICAS DE ERRORES:
  Total errores: 8
  Reintentos: 15
  Mensajes a DLQ: 3
  Errores por tipo:
    - ValueError: 5
    - TimeoutException: 2
    - SecurityException: 1
============================================================
```

## 📁 Archivos Modificados/Creados

### Nuevos Archivos

1. **`src/common/logging_config.py`** (290 líneas)
   - `StructuredFormatter`: Formatter JSON
   - `ColoredFormatter`: Formatter con colores
   - `setup_logging()`: Configuración centralizada
   - `get_logger()`: Logger con contexto

2. **`test_fase_4_1.py`** (640 líneas)
   - 19 tests unitarios
   - Cobertura completa de DLQ, reintentos, logging, estadísticas

3. **`FASE_4_1_README.md`** (Este archivo)
   - Documentación completa de la fase

### Archivos Modificados

1. **`src/common/config.py`**
   - Añadidas configuraciones DLQ:
     ```python
     DLQ_ESCENARIOS = 'cola_dlq_escenarios'
     DLQ_RESULTADOS = 'cola_dlq_resultados'
     ```
   - Configuraciones de reintentos:
     ```python
     MAX_RETRIES = 3
     RETRY_DELAY = 5  # segundos
     ```

2. **`src/common/rabbitmq_client.py`**
   - Modificado `declare_queues()`:
     - Declara DLQs primero
     - Configura colas principales con DLQ
     - Argumentos `x-dead-letter-exchange` y `x-dead-letter-routing-key`

3. **`src/consumer/consumer.py`**
   - Nuevas estadísticas de errores
   - Método `_handle_error()` completo
   - Callback `_procesar_escenario_callback()` con lógica de reintentos
   - `_publicar_stats()` con métricas de errores
   - `_finalizar()` muestra resumen de errores

## 🧪 Tests

### Ejecución

```bash
python test_fase_4_1.py
```

### Resultados

```
======================================================================
RESUMEN DE TESTS - FASE 4.1
======================================================================
Tests ejecutados: 19
✅ Exitosos: 19
❌ Fallidos: 0
💥 Errores: 0
======================================================================

✅ TODOS LOS TESTS PASARON EXITOSAMENTE
```

### Cobertura de Tests

| Categoría | Tests | Descripción |
|-----------|-------|-------------|
| **DLQ Configuration** | 3 | Verifican declaración correcta de DLQs |
| **Retry Mechanism** | 6 | Prueban lógica de reintentos y límites |
| **Error Statistics** | 3 | Validan tracking de estadísticas |
| **Logging** | 4 | Verifican formatters y configuración |
| **Configuration** | 3 | Validan valores de config |

**Tests destacados:**

- ✅ `test_dlq_queues_declared`: DLQs se declaran correctamente
- ✅ `test_retry_count_increments`: Contador se incrementa en reintentos
- ✅ `test_max_retries_exceeded_sends_to_dlq`: Mensaje va a DLQ tras 3 reintentos
- ✅ `test_non_recoverable_error_goes_to_dlq_directly`: Errores no recuperables van directo a DLQ
- ✅ `test_timeout_exception_goes_to_dlq`: Timeout no se reintenta
- ✅ `test_security_exception_goes_to_dlq`: Violaciones de seguridad no se reintentan
- ✅ `test_successful_retry_logs_correctly`: Reintentos exitosos se loggean
- ✅ `test_error_statistics_tracking`: Estadísticas se rastrean correctamente
- ✅ `test_structured_formatter_creates_json`: Formatter genera JSON válido

## 🔧 Uso y Configuración

### Configuración Básica

**Variables de entorno (.env):**
```bash
# Manejo de errores
CONSUMER_MAX_RETRIES=3
CONSUMER_RETRY_DELAY=5

# DLQ
QUEUE_DLQ_ESCENARIOS=cola_dlq_escenarios
QUEUE_DLQ_RESULTADOS=cola_dlq_resultados

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=colored  # o 'json'
```

### Uso de Logging Estructurado

**Configuración en aplicación:**
```python
from src.common.logging_config import setup_logging, get_logger

# Configurar logging al inicio
setup_logging(
    log_level='INFO',
    log_format='json',
    log_file='varp.log',
    enable_console=True
)

# Obtener logger con contexto
logger = get_logger(
    'my_module',
    consumer_id='C-123',
    model_id='M-456'
)

# Todos los logs incluirán consumer_id y model_id
logger.info('Processing started')
logger.error('Error occurred', extra={'escenario_id': 'ESC-001'})
```

### Monitoreo de DLQ

**Verificar mensajes en DLQ:**
```python
from src.common.rabbitmq_client import RabbitMQClient
from src.common.config import QueueConfig

with RabbitMQClient() as client:
    client.connect()

    # Ver tamaño de DLQ
    dlq_size = client.get_queue_size(QueueConfig.DLQ_ESCENARIOS)
    print(f"Mensajes en DLQ: {dlq_size}")

    # Obtener mensaje de DLQ para análisis
    failed_msg = client.get_message(
        queue_name=QueueConfig.DLQ_ESCENARIOS,
        auto_ack=False
    )
    print(f"Mensaje fallido: {failed_msg}")
```

**Republicar desde DLQ (después de fix):**
```python
# Leer mensaje de DLQ
msg = client.get_message(QueueConfig.DLQ_ESCENARIOS)

# Republicar a cola principal
client.publish(
    queue_name=QueueConfig.ESCENARIOS,
    message=msg,
    persistent=True
)
```

## 📊 Métricas y Monitoreo

### Métricas Clave

**Tasa de error:**
```
error_rate = errores_totales / (escenarios_procesados + errores_totales)
```

**Tasa de reintento:**
```
retry_rate = reintentos_totales / errores_totales
```

**Tasa de DLQ:**
```
dlq_rate = mensajes_a_dlq / errores_totales
```

### Alertas Recomendadas

1. **Alta tasa de errores:** `error_rate > 0.05` (5%)
2. **DLQ creciendo:** `dlq_size > 100` mensajes
3. **Muchos timeouts:** `TimeoutException > 10` por minuto
4. **Violaciones de seguridad:** `SecurityException > 0`

## 🎓 Lecciones Aprendidas

### Diseño de Reintentos

**✅ Hacer:**
- Clasificar errores como recuperables/no recuperables
- Limitar número de reintentos
- Trackear headers para evitar loops infinitos
- Loggear información detallada de cada reintento

**❌ Evitar:**
- Reintentar errores permanentes (syntax errors, security violations)
- Reintentos sin límite
- Perder información del error original
- Bloquear la cola con reintentos continuos

### Logging Estructurado

**Ventajas:**
- Parseable por herramientas (ELK, Splunk, etc.)
- Búsqueda y filtrado eficiente
- Contexto rico en cada log
- Correlación de eventos

**Best Practices:**
- Incluir IDs únicos (consumer_id, escenario_id)
- Timestamps en ISO format
- Stack traces completos en errores
- Metadata relevante en campo `extra`

### DLQ Design

**Consideraciones:**
- DLQ debe ser durable (persistente)
- Capacidad limitada (evitar memory overflow)
- Monitorear tamaño de DLQ
- Proceso para revisar y republicar mensajes

## 🚀 Próximos Pasos

Posibles mejoras futuras:

1. **Retry delay exponencial**: Esperar más tiempo entre reintentos
   ```python
   delay = RETRY_DELAY * (2 ** retry_count)
   ```

2. **Circuit breaker**: Parar temporalmente si tasa de error es alta

3. **Alerting**: Integrar con Prometheus/Grafana para alertas

4. **DLQ procesamiento**: Script automático para análisis de DLQ

5. **Distributed tracing**: Integrar OpenTelemetry para trazas completas

## 📚 Referencias

- [RabbitMQ DLQ Documentation](https://www.rabbitmq.com/dlx.html)
- [Python logging.config](https://docs.python.org/3/library/logging.config.html)
- [Retry Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/retry)
- [Circuit Breaker Pattern](https://martinfowler.com/bliki/CircuitBreaker.html)

## ✅ Checklist de Implementación

- [x] DLQ configuradas en RabbitMQ
- [x] Sistema de reintentos con límite de 3
- [x] Logging estructurado (JSON + Colored)
- [x] Clasificación de errores recuperables/no recuperables
- [x] Estadísticas de errores completas
- [x] Tests unitarios (19 tests, 100% passing)
- [x] Documentación completa
- [x] Headers de tracking (x-retry-count, x-last-error)
- [x] Resumen de errores al finalizar consumidor
- [x] Rotación de logs automática

---

**Estado:** ✅ **COMPLETADO**
**Tests:** 19/19 passing
**Cobertura:** DLQ, Reintentos, Logging, Estadísticas
**Fecha:** 2025-01-15
