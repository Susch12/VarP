# Fase 2.2: Análisis de Resultados y Exportación - COMPLETADO ✅

## Resumen

Se han implementado funcionalidades avanzadas de **análisis de resultados y exportación de datos** para el dashboard Monte Carlo. El sistema ahora consume resultados de la simulación, calcula estadísticas descriptivas completas y permite exportar datos en formatos CSV y JSON.

## Nuevas Funcionalidades

### 1. Consumo y Análisis de Resultados

El `DataManager` ahora:
- Consume resultados de `cola_resultados` en tiempo real
- Almacena todos los valores de resultado para análisis
- Mantiene los últimos 1000 resultados completos (con metadata)
- Calcula estadísticas descriptivas automáticamente

### 2. Estadísticas Descriptivas Completas

El sistema calcula automáticamente:
- **Medidas de tendencia central**: media, mediana
- **Medidas de dispersión**: desviación estándar, varianza
- **Rango**: mínimo, máximo
- **Percentiles**: P25, P75, P95, P99
- **Intervalo de confianza**: IC 95% para la media

### 3. Visualizaciones de Resultados

Nuevas gráficas en el dashboard:
- **Histograma**: Distribución de frecuencias de resultados con línea de media
- **Box Plot**: Visualización de cuartiles, outliers y dispersión

### 4. Exportación de Datos

Dos formatos de exportación disponibles:

**CSV**:
- Resultados individuales (escenario_id, consumer_id, resultado, tiempo_ejecucion)
- Estadísticas descriptivas al final del archivo
- Formato compatible con Excel y herramientas de análisis

**JSON**:
- Estructura completa de la simulación
- Metadata (fecha, número de resultados)
- Información del modelo
- Estadísticas de productor y consumidores
- Estadísticas descriptivas
- Resultados completos

## Arquitectura

### Flujo de Datos de Resultados

```
┌─────────────────────────────────────────────────────────────┐
│                       Consumidores                           │
│                                                             │
│  consumer._publicar_resultado() publishes to:               │
│  • cola_resultados                                          │
│    {                                                        │
│      escenario_id, consumer_id, modelo_id,                  │
│      resultado, tiempo_ejecucion, timestamp                 │
│    }                                                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ RabbitMQ
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         DataManager._consume_resultados()                    │
│                                                             │
│  Consume cada 0.5s:                                         │
│  • Lee todos los mensajes disponibles                       │
│  • Almacena valores en self.resultados[]                    │
│  • Almacena mensajes completos en self.resultados_raw[]     │
│  • Llama a _calcular_estadisticas()                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│         DataManager._calcular_estadisticas()                │
│                                                             │
│  Usando NumPy:                                              │
│  • Calcula media, mediana, std, varianza                    │
│  • Calcula min, max                                         │
│  • Calcula percentiles (25, 75, 95, 99)                     │
│  • Calcula intervalo de confianza 95%                       │
│  • Almacena en self.estadisticas{}                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Thread-safe getter
                     ▼
┌─────────────────────────────────────────────────────────────┐
│               Dashboard (Dash callback)                      │
│                                                             │
│  • get_resultados() → List[float]                           │
│  • get_estadisticas() → Dict[str, Any]                      │
│  • get_resultados_raw() → List[Dict]                        │
│                                                             │
│  Genera:                                                    │
│  • Panel de estadísticas descriptivas                       │
│  • Histograma con Plotly                                    │
│  • Box plot con Plotly                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Exportación (botones)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Callbacks de Exportación                         │
│                                                             │
│  • export_csv() → archivo CSV                               │
│  • export_json() → archivo JSON                             │
│                                                             │
│  Descarga automática en navegador                           │
└─────────────────────────────────────────────────────────────┘
```

## Cambios en Archivos

### `src/dashboard/data_manager.py` (extendido)

**Nuevos atributos**:
```python
self.resultados: List[float] = []  # Todos los resultados
self.resultados_raw: List[Dict[str, Any]] = []  # Últimos 1000 completos
self.estadisticas: Dict[str, Any] = {}  # Estadísticas calculadas
```

**Nuevos métodos**:
- `_consume_resultados()`: Consume resultados de la cola
- `_calcular_estadisticas()`: Calcula estadísticas con NumPy
- `get_resultados()`: Retorna todos los resultados
- `get_resultados_raw()`: Retorna últimos 1000 resultados completos
- `get_estadisticas()`: Retorna estadísticas calculadas

**Estadísticas calculadas**:
```python
{
    'n': int,                    # Número de resultados
    'media': float,              # Promedio
    'mediana': float,            # Mediana
    'desviacion_estandar': float,# Desviación estándar
    'varianza': float,           # Varianza
    'minimo': float,             # Valor mínimo
    'maximo': float,             # Valor máximo
    'percentil_25': float,       # Primer cuartil
    'percentil_75': float,       # Tercer cuartil
    'percentil_95': float,       # Percentil 95
    'percentil_99': float,       # Percentil 99
    'intervalo_confianza_95': {  # IC 95% para la media
        'inferior': float,
        'superior': float
    }
}
```

### `src/dashboard/app.py` (extendido)

**Nuevas secciones en el layout**:
- Divider "Análisis de Resultados"
- Panel de Estadísticas Descriptivas
- Gráfica de Histograma (8 columnas)
- Gráfica de Box Plot (4 columnas)
- Panel de Exportación con botones CSV y JSON

**Nuevos métodos**:
- `_create_estadisticas_panel()`: Crea panel con métricas estadísticas
- `_create_histograma_chart()`: Genera histograma con Plotly
- `_create_boxplot_chart()`: Genera box plot con Plotly

**Nuevos callbacks**:
- `export_csv()`: Genera y descarga archivo CSV
- `export_json()`: Genera y descarga archivo JSON

**Callback principal extendido**:
- Ahora retorna 10 outputs (antes 7)
- Incluye: estadisticas_panel, grafica_histograma, grafica_boxplot

## Formatos de Exportación

### Formato CSV

```csv
escenario_id,consumer_id,resultado,tiempo_ejecucion
escenario_001,C1,0.234567,0.000123
escenario_002,C2,-1.456789,0.000234
...

ESTADISTICAS
n,1000
media,0.012345
mediana,0.023456
desviacion_estandar,1.414213
varianza,2.000000
minimo,-4.567890
maximo,4.321098
...
```

**Nombre de archivo**: `resultados_YYYYMMDD_HHMMSS.csv`

### Formato JSON

```json
{
  "metadata": {
    "fecha_exportacion": "2024-01-15T14:30:00.123456",
    "num_resultados": 1000
  },
  "modelo": {
    "modelo_id": "suma_normal_1705330200",
    "version": "1.0",
    "nombre": "suma_normal",
    "expresion": "x + y",
    ...
  },
  "productor": {
    "progreso": 1.0,
    "escenarios_generados": 1000,
    "tasa_generacion": 156.78,
    ...
  },
  "consumidores": {
    "C1": { "escenarios_procesados": 334, ... },
    "C2": { "escenarios_procesados": 333, ... },
    "C3": { "escenarios_procesados": 333, ... }
  },
  "estadisticas": {
    "n": 1000,
    "media": 0.012345,
    "mediana": 0.023456,
    ...
  },
  "resultados": [
    {
      "escenario_id": "escenario_001",
      "consumer_id": "C1",
      "resultado": 0.234567,
      "tiempo_ejecucion": 0.000123,
      ...
    },
    ...
  ]
}
```

**Nombre de archivo**: `simulacion_YYYYMMDD_HHMMSS.json`

## Visualizaciones

### Panel de Estadísticas Descriptivas

Muestra métricas en 6 columnas:
1. **Resultados**: Número total de resultados
2. **Media**: Promedio de resultados
3. **Mediana**: Valor central
4. **Desv. Estándar**: Medida de dispersión
5. **Mínimo**: Valor más pequeño
6. **Máximo**: Valor más grande

Más percentiles (P25, P75, P95, P99) e intervalo de confianza 95%.

### Histograma de Distribución

- Bins adaptativos según número de datos
- Línea vertical roja indicando la media
- Eje X: Valores de resultado
- Eje Y: Frecuencia

### Box Plot

- Muestra cuartiles (Q1, mediana, Q3)
- Whiskers (mínimo y máximo excluyendo outliers)
- Outliers como puntos individuales
- Línea de media y desviación estándar

## Validación

### Test de Validación (`test_fase_2_2.py`)

Valida 13 aspectos:

1. ✅ Conexión a RabbitMQ
2. ✅ Purga de colas
3. ✅ Creación e inicio de DataManager
4. ✅ Ejecución de productor (100 escenarios)
5. ✅ Ejecución de 3 consumidores paralelos
6. ✅ Consumo de resultados por DataManager
7. ✅ Cálculo de estadísticas descriptivas
8. ✅ Almacenamiento de resultados raw
9. ✅ Validación de distribución normal
10. ✅ Generación de estructura CSV
11. ✅ Generación de estructura JSON
12. ✅ Resumen completo del sistema
13. ✅ Detención correcta de DataManager

### Ejecutar Test

```bash
python test_fase_2_2.py
```

**Validaciones específicas**:
- Media esperada: ~0.0 (modelo x+y donde x,y ~ N(0,1))
- Desviación estándar esperada: ~1.414 (sqrt(2))
- Formato CSV correcto
- Formato JSON válido

## Uso del Dashboard Extendido

### 1. Iniciar Sistema

```bash
# Terminal 1: RabbitMQ
docker-compose up -d rabbitmq

# Terminal 2: Productor
python run_producer.py --modelo modelos/ejemplo_simple.ini --escenarios 1000

# Terminales 3-5: Consumidores
python run_consumer.py --id C1 &
python run_consumer.py --id C2 &
python run_consumer.py --id C3 &

# Terminal 6: Dashboard
python run_dashboard.py
```

### 2. Acceder al Dashboard

```
http://localhost:8050
```

### 3. Ver Análisis de Resultados

Scroll down hasta la sección **"📈 Análisis de Resultados"**:
- Panel de estadísticas descriptivas se actualiza automáticamente
- Histograma muestra distribución de resultados
- Box plot muestra cuartiles y outliers

### 4. Exportar Datos

Hacer clic en:
- **"📄 Descargar CSV"**: Descarga resultados en formato CSV
- **"📋 Descargar JSON"**: Descarga simulación completa en JSON

Los archivos se descargan automáticamente al navegador.

## Características Técnicas

### Thread-Safety

Todo el acceso a resultados y estadísticas usa locks:
```python
with self._lock:
    return self.resultados.copy()
```

### Optimización de Memoria

- Resultados completos: todos los valores float (ligero)
- Resultados raw: solo últimos 1000 (para exportación)
- Históricos: limitados a 100 puntos

### Cálculo Incremental

Las estadísticas se recalculan solo cuando hay nuevos resultados:
```python
if nuevos_resultados > 0:
    self._calcular_estadisticas()
```

### Bins Adaptativos en Histograma

```python
nbinsx = min(50, max(10, len(resultados) // 20))
```

Ajusta automáticamente el número de bins según la cantidad de datos.

## Dependencias

**NumPy**: Requerido para cálculos estadísticos eficientes

```python
import numpy as np

resultados_array = np.array(self.resultados)
media = float(np.mean(resultados_array))
std = float(np.std(resultados_array))
percentiles = np.percentile(resultados_array, [25, 75, 95, 99])
```

## Próximos Pasos (Fase 3)

Posibles mejoras para futuras fases:
- [ ] Gráficas de convergencia de media y varianza
- [ ] Tests de normalidad (Kolmogorov-Smirnov, Shapiro-Wilk)
- [ ] Comparación con distribución teórica esperada
- [ ] Q-Q plot para validar normalidad
- [ ] Exportación a otros formatos (Excel, HDF5)
- [ ] Filtrado de resultados por rango de tiempo
- [ ] Alertas cuando estadísticas se desvían de lo esperado

## Troubleshooting

### No aparecen estadísticas

- Asegúrate de que los consumidores están procesando escenarios
- Verifica que la cola `cola_resultados` tiene mensajes
- Espera al menos 1-2 segundos para que DataManager consuma

### Histograma vacío

- Necesitas al menos algunos resultados procesados
- El histograma se actualiza cada 2 segundos
- Verifica en el panel de estadísticas que n > 0

### Botones de exportación no funcionan

- Asegúrate de hacer clic solo una vez
- La descarga puede tardar unos segundos con muchos datos
- Verifica que hay resultados disponibles (n > 0)

### Estadísticas no coinciden con lo esperado

- Con pocos datos (<30) las estadísticas pueden variar mucho
- La distribución es estocástica, habrá variación natural
- Ejecuta con más escenarios (1000+) para mejor convergencia

## Conclusión

✅ **Fase 2.2 completada exitosamente**

El dashboard ahora ofrece análisis completo de resultados:
- Estadísticas descriptivas en tiempo real
- Visualizaciones de distribución (histograma, box plot)
- Exportación de datos para análisis externo
- Thread-safe y optimizado para memoria

El sistema está listo para análisis estadístico profundo de simulaciones Monte Carlo distribuidas.
