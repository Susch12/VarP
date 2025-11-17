# Fase 2.1: Dashboard Básico - COMPLETADO ✅

## Resumen

Se ha implementado el **Dashboard de Monitoreo en Tiempo Real** para la simulación Monte Carlo distribuida. El dashboard permite visualizar en tiempo real:

- **Progreso del productor**: barra de progreso, tasa de generación, ETA
- **Estadísticas de consumidores**: tabla con métricas individuales de cada consumidor
- **Gráficas interactivas**: progreso, tasas de procesamiento, estado de colas
- **Información del modelo**: metadatos y expresión matemática
- **Actualización automática**: cada 2 segundos (configurable)

## Arquitectura

### Componentes Implementados

#### 1. DataManager (`src/dashboard/data_manager.py`)

Gestor de datos que consume estadísticas de RabbitMQ en un thread separado.

**Responsabilidades:**
- Consumir stats del productor de `cola_stats_productor`
- Consumir stats de consumidores de `cola_stats_consumidores`
- Obtener información del modelo de `cola_modelo`
- Monitorear tamaños de todas las colas
- Mantener histórico de datos (últimos 100 puntos)
- Proveer acceso thread-safe a los datos

**Características:**
- Thread daemon en background que ejecuta loop de consumo cada 0.5s
- Locks para acceso thread-safe
- Históricos limitados a 100 puntos para optimizar memoria
- Métodos getter para acceso seguro a datos

```python
# Uso del DataManager
data_manager = DataManager(rabbitmq_client)
data_manager.start()

# Obtener datos (thread-safe)
stats_prod = data_manager.get_stats_productor()
stats_cons = data_manager.get_stats_consumidores()
modelo_info = data_manager.get_modelo_info()
summary = data_manager.get_summary()

data_manager.stop()
```

#### 2. Dashboard Web (`src/dashboard/app.py`)

Aplicación Dash con layout completo y callbacks para actualización automática.

**Componentes del Layout:**
- **Header**: Título y descripción del dashboard
- **Panel de Modelo**: Nombre, versión, variables, tipo, expresión
- **Panel de Productor**:
  - Barra de progreso visual
  - Métricas: escenarios generados, total, tasa, ETA
  - Estado (completado/activo)
- **Panel de Consumidores**:
  - Resumen: número de consumidores, total procesados, tasa total
  - Tabla interactiva con stats de cada consumidor
- **Gráfica de Progreso**: Gauge indicador de 0-100%
- **Gráfica de Tasas**: Líneas temporales de productor y consumidores
- **Gráfica de Colas**: Barras con número de mensajes en cada cola
- **Footer**: Timestamp de última actualización

**Actualización Automática:**
- `dcc.Interval` ejecuta callback cada 2000ms (2 segundos)
- El callback actualiza TODOS los componentes simultáneamente
- Usa DataManager para obtener datos actualizados

```python
# Uso del Dashboard
dashboard = create_dashboard(rabbitmq_client, update_interval=2000)
dashboard.start(host='0.0.0.0', port=8050, debug=False)
```

#### 3. Script CLI (`run_dashboard.py`)

Script ejecutable para lanzar el dashboard desde línea de comandos.

**Características:**
- Argumentos para configurar host, puerto, intervalo
- Configuración de logging (verbose, quiet)
- Modo debug de Dash para desarrollo
- Manejo de errores con mensajes claros
- Banner informativo con URL de acceso

```bash
# Uso básico
python run_dashboard.py

# Personalizado
python run_dashboard.py --host 0.0.0.0 --port 8080 --interval 1000
python run_dashboard.py --rabbitmq-host localhost --verbose
python run_dashboard.py --debug  # Modo desarrollo
```

## Estructura de Archivos

```
src/dashboard/
├── __init__.py
├── data_manager.py      # Gestor de datos en background
└── app.py               # Aplicación Dash

run_dashboard.py         # Script CLI para ejecutar
test_fase_2_1.py        # Test de validación
```

## Flujo de Datos

```
┌─────────────────────────────────────────────────────────────┐
│                      RabbitMQ Queues                        │
├─────────────────────────────────────────────────────────────┤
│  • cola_stats_productor    (stats del productor)            │
│  • cola_stats_consumidores (stats de consumidores)          │
│  • cola_modelo             (metadata del modelo)            │
│  • cola_escenarios         (escenarios pendientes)          │
│  • cola_resultados         (resultados procesados)          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Consume cada 0.5s
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              DataManager (Background Thread)                │
├─────────────────────────────────────────────────────────────┤
│  • stats_productor: Dict[str, Any]                          │
│  • stats_consumidores: Dict[str, Dict[str, Any]]            │
│  • modelo_info: Dict[str, Any]                              │
│  • queue_sizes: Dict[str, int]                              │
│  • historico_productor: List[Dict] (últimos 100)            │
│  • historico_consumidores: Dict[str, List[Dict]]            │
│  • _lock: threading.Lock (acceso thread-safe)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Métodos getter (thread-safe)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Dashboard Dash (dcc.Interval callback)            │
├─────────────────────────────────────────────────────────────┤
│  Cada 2 segundos:                                           │
│  1. Obtener datos del DataManager                           │
│  2. Generar componentes HTML/Bootstrap                      │
│  3. Crear gráficas Plotly                                   │
│  4. Actualizar todos los Output del layout                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ HTTP
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Navegador Web (localhost:8050)                 │
│                                                             │
│  • Visualización interactiva                                │
│  • Gráficas actualizadas en tiempo real                     │
│  • Responsive (Bootstrap)                                   │
└─────────────────────────────────────────────────────────────┘
```

## Validación

El script `test_fase_2_1.py` valida todos los componentes del dashboard:

```bash
# Ejecutar test de validación
python test_fase_2_1.py
```

**Tests ejecutados:**
1. ✅ Conexión a RabbitMQ
2. ✅ Purga de colas
3. ✅ Creación de DataManager
4. ✅ Inicio de DataManager en background
5. ✅ Ejecución de productor (30 escenarios)
6. ✅ Captura de stats del productor
7. ✅ Ejecución de 2 consumidores paralelos
8. ✅ Captura de stats de consumidores
9. ✅ Captura de información del modelo
10. ✅ Monitoreo de tamaños de colas
11. ✅ Generación de históricos
12. ✅ Generación de resumen del sistema
13. ✅ Detención correcta de DataManager

## Uso del Dashboard

### 1. Iniciar RabbitMQ

```bash
docker-compose up -d rabbitmq
```

### 2. Ejecutar Simulación

```bash
# Terminal 1: Productor
python run_producer.py --modelo modelos/ejemplo_simple.ini --escenarios 1000

# Terminal 2-4: Consumidores
python run_consumer.py --id C1 &
python run_consumer.py --id C2 &
python run_consumer.py --id C3 &
```

### 3. Ejecutar Dashboard

```bash
# Terminal 5: Dashboard
python run_dashboard.py
```

### 4. Abrir Navegador

```
http://localhost:8050
```

El dashboard se actualizará automáticamente cada 2 segundos mostrando:
- Progreso en tiempo real
- Tasas de procesamiento
- Stats de cada consumidor
- Estado de las colas

## Tecnologías Utilizadas

- **Dash 2.14+**: Framework web para dashboards interactivos
- **Plotly**: Gráficas interactivas (gauge, line, bar)
- **Dash Bootstrap Components**: Componentes UI responsivos
- **Threading**: Consumo de datos en background
- **Locks**: Sincronización thread-safe
- **RabbitMQ**: Broker de mensajes

## Características Destacadas

### Thread-Safe
Todo el acceso a datos compartidos usa locks para garantizar seguridad entre threads:
```python
with self._lock:
    return self.stats_productor.copy()
```

### Históricos Limitados
Para optimizar memoria, se mantienen solo los últimos 100 puntos:
```python
if len(self.historico_productor) > 100:
    self.historico_productor.pop(0)
```

### Auto-Actualización
El dashboard se actualiza automáticamente sin recargar la página:
```python
dcc.Interval(id='interval-component', interval=2000, n_intervals=0)
```

### Responsive Design
Usa Bootstrap Grid system para layout responsive:
```python
dbc.Row([
    dbc.Col([...], width=4),
    dbc.Col([...], width=8),
])
```

## Próximos Pasos (Fase 2.2)

- [ ] Agregar gráfica de distribución de resultados (histograma)
- [ ] Implementar panel de control (pausar/reanudar simulación)
- [ ] Agregar exportación de datos a CSV/JSON
- [ ] Implementar alertas visuales (escenarios fallidos, colas llenas)
- [ ] Mejorar diseño visual con CSS personalizado
- [ ] Agregar documentación interactiva en el dashboard

## Comandos Útiles

```bash
# Ejecutar test de validación
python test_fase_2_1.py

# Dashboard básico
python run_dashboard.py

# Dashboard en puerto personalizado
python run_dashboard.py --port 8080

# Dashboard con actualización rápida (cada 1s)
python run_dashboard.py --interval 1000

# Dashboard en modo debug (auto-reload)
python run_dashboard.py --debug --verbose

# Ver logs detallados
python run_dashboard.py --verbose
```

## Troubleshooting

### Error: "No se pudo conectar a RabbitMQ"
```bash
# Verificar que RabbitMQ esté corriendo
docker-compose ps rabbitmq

# Iniciar RabbitMQ
docker-compose up -d rabbitmq
```

### Dashboard muestra "Esperando datos..."
- Asegúrate de que hay una simulación en progreso
- Ejecuta productor y consumidores antes del dashboard
- Verifica que las colas de stats tengan mensajes

### Gráficas vacías
- El dashboard necesita tiempo para acumular datos históricos
- Espera al menos 10-20 segundos después de iniciar la simulación
- Verifica que el DataManager esté consumiendo datos (logs)

### Puerto 8050 ya está en uso
```bash
# Usa un puerto diferente
python run_dashboard.py --port 8888
```

## Conclusión

✅ **Fase 2.1 completada exitosamente**

El dashboard básico está completamente funcional y listo para:
- Monitorear simulaciones en tiempo real
- Visualizar métricas de productor y consumidores
- Mostrar progreso y tasas de procesamiento
- Proveer una interfaz web interactiva y responsive

El sistema está listo para extenderse con funcionalidades adicionales en Fase 2.2.
