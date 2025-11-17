# Tests de Integración del Sistema VarP

## 📋 Resumen

Los tests de integración verifican el funcionamiento correcto del sistema completo end-to-end, incluyendo:

- ✅ **Test 1**: Procesamiento de **10,000 escenarios**
- ✅ **Test 2**: **5 consumidores paralelos** con fair dispatch
- ✅ **Test 3**: **Recuperación ante fallo** de consumidor
- ✅ **Test 4**: **Cambio de modelo** con purga correcta

Estos tests validan que el sistema funciona correctamente en escenarios reales de producción.

## ⚠️ Pre-requisitos

### 1. RabbitMQ Corriendo

Los tests de integración **REQUIEREN** RabbitMQ ejecutándose en `localhost:5672`:

```bash
# Opción 1: Docker (recomendado)
docker run -d --name rabbitmq \
  -p 5672:5672 \
  -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=password \
  rabbitmq:3-management

# Opción 2: Sistema local
# (Asegurarse que RabbitMQ está instalado y corriendo)
sudo systemctl start rabbitmq-server

# Verificar que está corriendo
curl -u admin:password http://localhost:15672/api/overview
```

### 2. Dependencias Instaladas

```bash
pip install -r requirements.txt
```

### 3. Modelos de Ejemplo

Los tests usan modelos de la carpeta `modelos/`:
- `ejemplo_simple.ini`
- `ejemplo_6_dist_simple.ini`

Estos modelos ya deben estar presentes en el repositorio.

## 🧪 Ejecutar Tests

### Ejecutar Todos los Tests

```bash
python test_integracion.py
```

**Output esperado:**
```
test_1_escenarios_10000 ... ok
test_2_cinco_consumidores_paralelos ... ok
test_3_recuperacion_fallo_consumidor ... ok
test_4_cambio_modelo_purga ... ok
test_throughput_productor ... ok

----------------------------------------------------------------------
Ran 5 tests in 180.234s

OK
```

### Ejecutar Test Específico

```bash
# Solo test de 10,000 escenarios
python test_integracion.py TestIntegracionSistemaCompleto.test_1_escenarios_10000

# Solo test de 5 consumidores paralelos
python test_integracion.py TestIntegracionSistemaCompleto.test_2_cinco_consumidores_paralelos

# Solo test de recuperación ante fallo
python test_integracion.py TestIntegracionSistemaCompleto.test_3_recuperacion_fallo_consumidor

# Solo test de cambio de modelo
python test_integracion.py TestIntegracionSistemaCompleto.test_4_cambio_modelo_purga
```

### Ejecutar con Verbose

```bash
python test_integracion.py -v
```

## 📊 Descripción de Tests

### Test 1: 10,000 Escenarios

**Objetivo**: Verificar que el sistema puede procesar un volumen grande de escenarios.

**Pasos:**
1. Productor genera 10,000 escenarios usando `ejemplo_simple.ini`
2. 1 consumidor procesa todos los escenarios
3. Se verifica que todos los resultados se publican

**Métricas verificadas:**
- ✅ 10,000 escenarios generados
- ✅ 10,000 escenarios en cola
- ✅ ≥99% de resultados procesados
- ✅ Throughput > 100 esc/s (productor + consumidor)

**Tiempo estimado**: ~1-3 minutos

### Test 2: 5 Consumidores Paralelos

**Objetivo**: Verificar distribución equitativa de carga con múltiples consumidores.

**Pasos:**
1. Productor genera 5,000 escenarios
2. **5 consumidores** se lanzan en procesos separados
3. Todos procesan concurrentemente usando prefetch_count=1 (fair dispatch)
4. Se verifica distribución y throughput

**Métricas verificadas:**
- ✅ 5,000 escenarios generados
- ✅ ≥95% de escenarios procesados
- ✅ Fair dispatch funciona (sin starvation)
- ✅ Throughput aumenta con más consumidores
- ✅ Estadísticas de todos los consumidores publicadas

**Tiempo estimado**: ~1-2 minutos

### Test 3: Recuperación ante Fallo

**Objetivo**: Verificar que el sistema es resiliente ante fallos de consumidores.

**Pasos:**
1. Productor genera 1,000 escenarios
2. Consumidor 1 procesa ~5 escenarios y luego **FALLA**
3. Consumidor 2 (backup) se lanza y procesa los escenarios restantes
4. Se verifica que todos los escenarios se procesaron

**Métricas verificadas:**
- ✅ 1,000 escenarios generados
- ✅ Consumidor 1 procesa <50% antes de fallar
- ✅ >50% de escenarios quedan en cola después del fallo
- ✅ Consumidor 2 procesa los restantes
- ✅ ≥95% de escenarios procesados al final
- ✅ **Sin pérdida de mensajes**

**Tiempo estimado**: ~30-60 segundos

**Validación clave**: Demuestra que el sistema NO pierde mensajes cuando un consumidor falla, gracias al ACK manual de RabbitMQ.

### Test 4: Cambio de Modelo con Purga

**Objetivo**: Verificar que se puede cambiar el modelo correctamente.

**Pasos:**
1. Productor 1 publica `ejemplo_simple.ini` + 100 escenarios
2. Verificar que hay 1 modelo y 100 escenarios en colas
3. Productor 2 publica `ejemplo_6_dist_simple.ini` + 200 escenarios
4. **Verificar purga**: modelo antiguo debe ser reemplazado
5. Purgar escenarios antiguos manualmente
6. Generar escenarios con nuevo modelo
7. Consumidor procesa con nuevo modelo

**Métricas verificadas:**
- ✅ Modelo antiguo se purga automáticamente
- ✅ Solo 1 modelo en cola (el nuevo)
- ✅ Modelo cambió correctamente (verificado por modelo_id)
- ✅ Escenarios antiguos se pueden purgar manualmente
- ✅ Consumidor carga y usa nuevo modelo
- ✅ ≥90% de escenarios procesados con nuevo modelo

**Tiempo estimado**: ~1 minuto

**Nota importante**: La cola de modelo se purga automáticamente en `producer._publicar_modelo()`, pero los escenarios antiguos deben purgarse manualmente si se desea. Esto es intencional para prevenir pérdida accidental de datos.

### Test 5: Throughput del Productor

**Objetivo**: Medir performance del productor.

**Pasos:**
1. Productor genera 5,000 escenarios
2. Se mide tiempo total
3. Se calcula throughput

**Métricas verificadas:**
- ✅ Throughput > 100 esc/s

**Tiempo estimado**: ~30 segundos

## 🎯 Criterios de Éxito

Para que los tests pasen, se deben cumplir:

### Funcionalidad
- ✅ Todos los escenarios se generan correctamente
- ✅ Todos los escenarios se procesan (≥95% o ≥99% según test)
- ✅ No hay pérdida de mensajes ante fallos
- ✅ Cambio de modelo funciona correctamente

### Performance
- ✅ Throughput productor > 100 esc/s
- ✅ Sistema completo procesa 10,000 escenarios en < 5 minutos
- ✅ Múltiples consumidores mejoran throughput

### Resiliencia
- ✅ Sistema se recupera de fallos de consumidor
- ✅ Mensajes no se pierden (ACK manual)
- ✅ Fair dispatch distribuye carga equitativamente

## 🐛 Troubleshooting

### Error: "RabbitMQ no disponible"

**Causa**: RabbitMQ no está corriendo o no está en `localhost:5672`.

**Solución**:
```bash
# Verificar que RabbitMQ está corriendo
docker ps | grep rabbitmq

# Si no está, iniciarlo
docker run -d --name rabbitmq \
  -p 5672:5672 -p 15672:15672 \
  -e RABBITMQ_DEFAULT_USER=admin \
  -e RABBITMQ_DEFAULT_PASS=password \
  rabbitmq:3-management

# Esperar 10 segundos a que inicie
sleep 10
```

### Tests se Saltan (SKIPPED)

Si ves:
```
test_1_escenarios_10000 (test_integracion.TestIntegracionSistemaCompleto) ... skipped 'RabbitMQ no disponible'
```

**Causa**: RabbitMQ no está accesible.

**Solución**: Ver sección anterior.

### Test Timeout

Si un test se queda esperando mucho tiempo:

**Causas posibles**:
1. RabbitMQ muy lento (falta de recursos)
2. Consumidores no procesan (error en código)
3. Colas llenas (aumentar límites)

**Solución**:
```bash
# Ver logs de RabbitMQ
docker logs rabbitmq

# Ver estado de colas
# (Usar management UI: http://localhost:15672)
# Usuario: admin, Password: password

# Purgar colas manualmente si es necesario
python -c "
from src.common.rabbitmq_client import RabbitMQClient
from src.common.config import QueueConfig
client = RabbitMQClient()
client.connect()
client.declare_queues()
for q in [QueueConfig.ESCENARIOS, QueueConfig.RESULTADOS]:
    client.purge_queue(q)
"
```

### Procesos Zombie

Si después de tests quedan procesos zombie:

```bash
# Ver procesos Python
ps aux | grep python

# Matar procesos si es necesario
pkill -9 -f "run_consumer_process"
```

### Throughput Bajo

Si el throughput es muy bajo (< 10 esc/s):

**Causas**:
- RabbitMQ en Docker con pocos recursos
- Máquina muy lenta
- Modelo complejo

**Solución**:
- Aumentar recursos de Docker
- Usar modelo más simple
- Los tests ajustan automáticamente los umbrales

## 📈 Interpretación de Resultados

### Ejemplo de Output Exitoso

```
==============================================================
TEST 1: 10,000 ESCENARIOS
==============================================================
✓ Productor generó 10000 escenarios en 45.23s
  Tasa: 221.05 esc/s
✓ Cola de escenarios tiene 10000 mensajes
  Progreso: 10000/10000 resultados
✓ Consumidor procesó 10000 escenarios en 52.34s
  Tasa: 191.06 esc/s
✓ Throughput total: 102.47 esc/s
==============================================================
TEST 1: EXITOSO ✓
==============================================================
```

**Interpretación:**
- Productor generó 10K escenarios a 221 esc/s
- Consumidor procesó 10K escenarios a 191 esc/s
- Throughput total del sistema: 102 esc/s
- **TODO OK** ✓

### Throughput Esperado

Depende del hardware, pero valores típicos:

| Componente | Throughput Esperado |
|------------|---------------------|
| Productor solo | 200-500 esc/s |
| Consumidor solo | 100-300 esc/s |
| Sistema completo (1 cons) | 80-150 esc/s |
| Sistema completo (5 cons) | 200-500 esc/s |

**Nota**: Con modelos complejos (código Python), el throughput será menor.

## 🔧 Configuración

Los tests usan la configuración por defecto de `src/common/config.py`:

```python
# RabbitMQ
RABBITMQ_HOST = 'localhost'
RABBITMQ_PORT = 5672
RABBITMQ_USER = 'admin'
RABBITMQ_PASS = 'password'

# Prefetch (Fair Dispatch)
CONSUMER_PREFETCH_COUNT = 1

# Connection Pooling
POOL_SIZE = 10
POOL_MAX_OVERFLOW = 5
```

Para modificar, usar variables de entorno:

```bash
export RABBITMQ_HOST=my-rabbit-server
export RABBITMQ_PORT=5672
python test_integracion.py
```

## 📝 Notas Importantes

### Multiprocessing

Los tests usan `multiprocessing` para lanzar consumidores en procesos separados (no threads), simulando el comportamiento real donde cada consumidor es un proceso independiente.

**Inicio del método**:
```python
multiprocessing.set_start_method('spawn', force=True)
```

Esto garantiza compatibilidad cross-platform (Linux, macOS, Windows).

### Limpieza de Colas

Cada test purga todas las colas antes de ejecutarse (`setUp()`), garantizando:
- ✅ Tests independientes
- ✅ No interferencia entre tests
- ✅ Estado limpio

### Timeouts

Los tests tienen timeouts configurados:
- Test 1 (10K): 300s (5 minutos)
- Test 2 (5 cons): 120s (2 minutos)
- Test 3 (fallo): 60s (1 minuto)
- Test 4 (cambio): 60s (1 minuto)

Si un test excede el timeout, **falla**.

### Logging

Los tests usan nivel `WARNING` por defecto para reducir ruido:

```python
logging.basicConfig(level=logging.WARNING)
```

Para ver más detalles, cambiar a `INFO` o `DEBUG`:

```python
logging.basicConfig(level=logging.INFO)
```

## 🎓 Uso Avanzado

### Ejecutar con Coverage

```bash
pip install pytest-cov
pytest test_integracion.py --cov=src --cov-report=html
```

### Ejecutar N veces

```bash
# Ejecutar 10 veces para detectar race conditions
for i in {1..10}; do
    echo "=== Run $i ==="
    python test_integracion.py || break
done
```

### Ejecutar en Paralelo (NO recomendado)

Los tests de integración NO deben ejecutarse en paralelo porque comparten la misma instancia de RabbitMQ y colas.

### Stress Testing

Para stress testing más intenso:

```python
# Modificar test_1_escenarios_10000
num_escenarios = 100000  # 100K escenarios
```

## 📚 Referencias

- **RabbitMQ Docs**: https://www.rabbitmq.com/documentation.html
- **Pika (Python Client)**: https://pika.readthedocs.io/
- **Fair Dispatch**: https://www.rabbitmq.com/tutorials/tutorial-two-python.html
- **Message Acknowledgment**: https://www.rabbitmq.com/confirms.html

---

**Tests de Integración** - Sistema VarP Monte Carlo
Validan funcionamiento completo end-to-end con escenarios reales de producción.
