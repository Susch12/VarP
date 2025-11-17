# Fase 4.3: Exportación de Resultados

## 📋 Resumen

La Fase 4.3 implementa funcionalidad completa de exportación de resultados del dashboard, permitiendo descargar y analizar los datos de simulación Monte Carlo en formatos estándar:

- ✅ **Exportación a JSON** con metadata completa (modelo, estadísticas, convergencia, tests)
- ✅ **Exportación a CSV con pandas** (resultados detallados con estadísticas en header)
- ✅ **Exportación de estadísticas a CSV** (formato tabla limpio)
- ✅ **Exportación de convergencia a CSV** (histórico con timestamps)
- ✅ **Botones de descarga en dashboard** integrados en la interfaz web
- ✅ **Thread-safe** con locks para acceso concurrente

## 🎯 Objetivos Cumplidos

### 1. Consumo de Resultados ✅ (Ya Implementado)

El sistema ya contaba con infraestructura para consumir y almacenar resultados desde RabbitMQ.

**DataManager** (`src/dashboard/data_manager.py`):
```python
def _consume_resultados(self):
    """Consume resultados de cola_resultados en background."""
    while self.running:
        try:
            msg = self.client.get_message(
                QueueConfig.RESULTADOS,
                auto_ack=False
            )
            if msg:
                with self._lock:
                    # Almacenar resultado
                    self.resultados.append(msg['resultado'])

                    # Almacenar detallado (últimos 1000)
                    self.resultados_raw.append(msg)
                    if len(self.resultados_raw) > 1000:
                        self.resultados_raw.pop(0)

                    # Calcular estadísticas
                    self._calcular_estadisticas()
```

**Características:**
- ✅ Polling continuo en thread separado
- ✅ Almacenamiento en memoria (self.resultados)
- ✅ Historial detallado (últimos 1000 con metadata)
- ✅ Cálculo automático de estadísticas

### 2. Exportación a JSON ✅

Exporta todos los datos de la simulación en formato JSON estructurado.

**Implementación** (`src/dashboard/data_manager.py:563-594`):
```python
def export_resultados_json(self) -> str:
    """
    Exporta los resultados y estadísticas a formato JSON.

    Returns:
        String JSON con resultados completos y estadísticas
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

    return json_str
```

**Estructura del JSON exportado:**
```json
{
  "metadata": {
    "fecha_exportacion": "2025-11-17T10:30:00",
    "num_resultados": 10000,
    "modelo": {
      "nombre": "simulacion_riesgo",
      "version": "1.0",
      "expresion": "x + y",
      "num_variables": 2
    }
  },
  "estadisticas": {
    "n": 10000,
    "media": 0.0045,
    "mediana": 0.0023,
    "desviacion_estandar": 1.4142,
    "varianza": 2.0,
    "intervalo_confianza_95": {
      "inferior": -0.0232,
      "superior": 0.0322
    },
    ...
  },
  "tests_normalidad": {
    "kolmogorov_smirnov": {
      "statistic": 0.0089,
      "pvalue": 0.4523,
      "is_normal_alpha_05": true
    },
    "shapiro_wilk": {...}
  },
  "resultados": [1.23, 2.45, ...],
  "resultados_detallados": [
    {
      "escenario_id": 1,
      "resultado": 1.23,
      "consumer_id": "consumer_0",
      "tiempo_ejecucion": 0.0123
    },
    ...
  ],
  "convergencia": [
    {"n": 100, "media": 0.01, "varianza": 1.98, "timestamp": 1700000000},
    ...
  ]
}
```

**Beneficios:**
- ✅ Formato estándar, fácil de parsear
- ✅ Incluye TODA la información de la simulación
- ✅ Tests de normalidad incluidos
- ✅ Histórico de convergencia para análisis
- ✅ Metadata para trazabilidad

### 3. Exportación a CSV con Pandas ✅

Exporta resultados a CSV usando pandas para máxima compatibilidad.

**Implementación** (`src/dashboard/data_manager.py:596-657`):
```python
def export_resultados_csv(self, include_metadata: bool = True) -> str:
    """
    Exporta los resultados a formato CSV usando pandas.

    Args:
        include_metadata: Si incluir columnas de metadata

    Returns:
        String CSV con resultados
    """
    with self._lock:
        resultados_raw = self.resultados_raw.copy()
        estadisticas = self.estadisticas.copy()

    # Crear DataFrame desde resultados detallados
    df = pd.DataFrame(resultados_raw)

    # Reordenar columnas: escenario_id, resultado primero
    base_cols = ['escenario_id', 'resultado']
    other_cols = [c for c in df.columns if c not in base_cols]

    if include_metadata:
        df = df[base_cols + other_cols]
    else:
        df = df[base_cols]

    # Añadir estadísticas como comentarios al inicio
    csv_buffer = io.StringIO()

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

    return csv_buffer.getvalue()
```

**Ejemplo de CSV generado:**
```csv
# Estadísticas Descriptivas
# Número de resultados: 10000
# Media: 0.004500
# Mediana: 0.002300
# Desviación Estándar: 1.414214
# Mínimo: -4.567890
# Máximo: 4.890123
#
escenario_id,resultado,consumer_id,tiempo_ejecucion
1,1.230000,consumer_0,0.012300
2,2.450000,consumer_1,0.011500
3,-0.890000,consumer_2,0.013200
...
```

**Características:**
- ✅ Usa pandas para máxima compatibilidad
- ✅ Estadísticas en header como comentarios
- ✅ Formato flotante con 6 decimales de precisión
- ✅ Opción para incluir/excluir metadata (consumer_id, timestamp, etc.)
- ✅ Compatible con Excel, R, Python, MATLAB

### 4. Exportación de Estadísticas a CSV ✅

CSV dedicado solo para estadísticas en formato tabla.

**Implementación** (`src/dashboard/data_manager.py:659-691`):
```python
def export_estadisticas_csv(self) -> str:
    """
    Exporta solo las estadísticas descriptivas a CSV.

    Returns:
        String CSV con estadísticas en formato tabla
    """
    with self._lock:
        estadisticas = self.estadisticas.copy()

    # Crear DataFrame con estadísticas
    rows = []
    for key, value in estadisticas.items():
        if key == 'intervalo_confianza_95':
            rows.append(['IC 95% Inferior', value['inferior']])
            rows.append(['IC 95% Superior', value['superior']])
        elif isinstance(value, (int, float)):
            rows.append([key.replace('_', ' ').title(), value])

    df = pd.DataFrame(rows, columns=['Estadistica', 'Valor'])

    return df.to_csv(index=False, float_format='%.6f')
```

**Ejemplo de salida:**
```csv
Estadistica,Valor
N,10000
Media,0.004500
Mediana,0.002300
Desviacion Estandar,1.414214
Varianza,2.000000
Minimo,-4.567890
Maximo,4.890123
Percentil 25,-0.950000
Percentil 75,0.960000
IC 95% Inferior,-0.023200
IC 95% Superior,0.032200
```

**Uso:**
- ✅ Reportes ejecutivos
- ✅ Fácil importación a Excel
- ✅ Formato limpio para presentaciones

### 5. Exportación de Convergencia a CSV ✅

CSV con histórico de convergencia para análisis temporal.

**Implementación** (`src/dashboard/data_manager.py:693-721`):
```python
def export_convergencia_csv(self) -> str:
    """
    Exporta datos de convergencia a CSV.

    Returns:
        String CSV con histórico de convergencia
    """
    with self._lock:
        convergencia = self.historico_convergencia.copy()

    # Crear DataFrame
    df = pd.DataFrame(convergencia)

    # Convertir timestamp a formato legible
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

    return df.to_csv(index=False, float_format='%.6f')
```

**Ejemplo de salida:**
```csv
n,media,varianza,timestamp
100,0.010000,1.980000,2025-11-17 10:00:00
200,-0.005000,2.010000,2025-11-17 10:00:05
500,0.002000,2.000500,2025-11-17 10:00:15
1000,0.000100,1.999800,2025-11-17 10:00:30
...
```

**Uso:**
- ✅ Análisis de convergencia
- ✅ Validación de estabilidad
- ✅ Gráficas de evolución temporal
- ✅ Determinación de n óptimo

### 6. Botones de Descarga en Dashboard ✅

Interfaz web con botones para descargar los resultados.

**Layout** (`src/dashboard/app.py:196-225`):
```python
# Panel de Exportación
dbc.Row([
    dbc.Col([
        dbc.Card([
            dbc.CardHeader(html.H5("💾 Exportar Datos")),
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.P("Exportar resultados y estadísticas:", className="mb-3"),
                        dbc.ButtonGroup([
                            dbc.Button(
                                "📄 Descargar CSV",
                                id="btn-export-csv",
                                color="primary",
                                className="mr-2"
                            ),
                            dbc.Button(
                                "📋 Descargar JSON",
                                id="btn-export-json",
                                color="info"
                            ),
                        ]),
                        dcc.Download(id="download-csv"),
                        dcc.Download(id="download-json"),
                    ])
                ])
            ])
        ])
    ])
], className="mb-4")
```

**Callbacks** (`src/dashboard/app.py:398-446`):
```python
# Callback para exportar CSV
@self.app.callback(
    Output('download-csv', 'data'),
    [Input('btn-export-csv', 'n_clicks')],
    prevent_initial_call=True
)
def export_csv(n_clicks):
    """Exporta resultados a CSV usando pandas (FASE 4.3)."""
    # Usar nuevo método de exportación de data_manager
    csv_str = self.data_manager.export_resultados_csv(include_metadata=True)

    return dict(
        content=csv_str,
        filename=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

# Callback para exportar JSON
@self.app.callback(
    Output('download-json', 'data'),
    [Input('btn-export-json', 'n_clicks')],
    prevent_initial_call=True
)
def export_json(n_clicks):
    """Exporta resultados y estadísticas a JSON (FASE 4.3)."""
    # Usar nuevo método de exportación de data_manager
    json_str = self.data_manager.export_resultados_json()

    return dict(
        content=json_str,
        filename=f"simulacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
```

**Características:**
- ✅ Botones visibles en dashboard
- ✅ Nombres de archivo con timestamp
- ✅ Descarga directa desde navegador
- ✅ No requiere acceso al servidor
- ✅ Prevent initial call para evitar descarga automática

### 7. Thread Safety ✅

Todos los métodos de exportación son thread-safe.

**Implementación:**
```python
def export_resultados_json(self) -> str:
    with self._lock:  # Adquirir lock
        # Copiar datos mientras se tiene el lock
        export_data = {
            'metadata': {...},
            'estadisticas': self.estadisticas.copy(),
            'resultados': self.resultados.copy(),
            ...
        }
    # Liberar lock antes de I/O

    # Serialización fuera del lock (no bloquea otros threads)
    json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

    return json_str
```

**Patrón:**
1. ✅ Adquirir lock con `with self._lock:`
2. ✅ Copiar datos (`.copy()` para evitar referencias)
3. ✅ Liberar lock automáticamente al salir del `with`
4. ✅ Hacer I/O y procesamiento fuera del lock

**Beneficios:**
- ✅ Múltiples usuarios pueden exportar simultáneamente
- ✅ Exportación no bloquea actualización de datos
- ✅ Sin race conditions
- ✅ Consistencia garantizada

## 🧪 Testing

La Fase 4.3 incluye suite completa de tests (23 tests).

**Ejecutar tests:**
```bash
python test_fase_4_3.py
```

**Resultado esperado:**
```
test_export_csv_empty_data ... ok
test_export_csv_float_format ... ok
test_export_csv_pandas_usage ... ok
test_export_csv_statistics_header ... ok
test_export_csv_with_metadata ... ok
test_export_csv_without_metadata ... ok
test_export_convergencia_csv_empty ... ok
test_export_convergencia_csv_structure ... ok
test_export_convergencia_csv_timestamp_format ... ok
test_export_convergencia_csv_values ... ok
test_export_estadisticas_csv_empty ... ok
test_export_estadisticas_csv_intervalo_confianza ... ok
test_export_estadisticas_csv_structure ... ok
test_export_estadisticas_csv_values ... ok
test_all_export_methods_work ... ok
test_export_consistency ... ok
test_thread_safety ... ok
test_export_json_convergencia ... ok
test_export_json_empty_data ... ok
test_export_json_estadisticas ... ok
test_export_json_metadata ... ok
test_export_json_structure ... ok
test_export_json_tests_normalidad ... ok

----------------------------------------------------------------------
Ran 23 tests in 0.051s

OK
```

**Clases de test:**
- `TestJSONExport`: 6 tests para exportación JSON
- `TestCSVExport`: 6 tests para exportación CSV con pandas
- `TestEstadisticasCSVExport`: 4 tests para CSV de estadísticas
- `TestConvergenciaCSVExport`: 4 tests para CSV de convergencia
- `TestExportIntegration`: 3 tests de integración (consistencia, thread-safety)

## 📊 Uso

### Desde Dashboard Web

1. **Iniciar simulación** (productor + consumidores)
2. **Abrir dashboard** en `http://localhost:8050`
3. **Esperar a que se procesen escenarios**
4. **Ir al panel "💾 Exportar Datos"** (al final del dashboard)
5. **Hacer clic en botón:**
   - **"📄 Descargar CSV"** → descarga `resultados_YYYYMMDD_HHMMSS.csv`
   - **"📋 Descargar JSON"** → descarga `simulacion_YYYYMMDD_HHMMSS.json`

### Desde Python (API Programática)

```python
from src.common.rabbitmq_client import RabbitMQClient
from src.dashboard.data_manager import DataManager

# Conectar a RabbitMQ
client = RabbitMQClient()
client.connect()

# Crear DataManager
data_manager = DataManager(client)
data_manager.start()

# Esperar a que se procesen resultados
time.sleep(10)

# Exportar JSON
json_str = data_manager.export_resultados_json()
with open('resultados.json', 'w') as f:
    f.write(json_str)

# Exportar CSV completo
csv_str = data_manager.export_resultados_csv(include_metadata=True)
with open('resultados.csv', 'w') as f:
    f.write(csv_str)

# Exportar solo estadísticas
stats_csv = data_manager.export_estadisticas_csv()
with open('estadisticas.csv', 'w') as f:
    f.write(stats_csv)

# Exportar convergencia
conv_csv = data_manager.export_convergencia_csv()
with open('convergencia.csv', 'w') as f:
    f.write(conv_csv)

# Cleanup
data_manager.stop()
client.disconnect()
```

### Análisis con Pandas

```python
import pandas as pd
import json

# Cargar JSON
with open('resultados.json', 'r') as f:
    data = json.load(f)

print(f"Simulación: {data['metadata']['modelo']['nombre']}")
print(f"Resultados: {data['metadata']['num_resultados']}")
print(f"Media: {data['estadisticas']['media']:.6f}")
print(f"Normal? {data['tests_normalidad']['kolmogorov_smirnov']['is_normal_alpha_05']}")

# Cargar CSV
df = pd.read_csv('resultados.csv', comment='#')
print(df.describe())
print(df.groupby('consumer_id')['tiempo_ejecucion'].mean())

# Cargar convergencia
df_conv = pd.read_csv('convergencia.csv')
df_conv.plot(x='n', y=['media', 'varianza'])
```

## 📁 Archivos Modificados

```
src/dashboard/
├── data_manager.py          # +165 líneas: 4 métodos de exportación
└── app.py                   # Modificado: callbacks actualizados a usar nuevos métodos

test_fase_4_3.py             # +480 líneas: 23 tests completos
FASE_4_3_README.md           # Este archivo
```

## ✅ Checklist de Implementación

- [x] Consumir resultados de cola_resultados (ya implementado)
- [x] Almacenar resultados en memoria (ya implementado)
- [x] Método `export_resultados_json()` con metadata completa
- [x] Método `export_resultados_csv()` con pandas
- [x] Método `export_estadisticas_csv()` para solo stats
- [x] Método `export_convergencia_csv()` para histórico
- [x] Callbacks en dashboard actualizados
- [x] Botones de descarga en UI (ya existían)
- [x] Thread-safety con locks
- [x] Tests unitarios completos (23 tests)
- [x] Documentación completa

## 🎯 Beneficios de la Implementación

### Para Usuarios
✅ **Descarga fácil**: 1 clic desde dashboard web
✅ **Formatos estándar**: JSON y CSV compatibles con todo
✅ **Análisis offline**: Procesar datos fuera del sistema
✅ **Trazabilidad**: Metadata completa con timestamp y modelo

### Para Análisis
✅ **Pandas**: CSV listo para importar a DataFrame
✅ **Excel**: Abrir directamente resultados.csv
✅ **R/MATLAB**: Compatibilidad total
✅ **JSON**: Para procesamiento automatizado

### Para el Sistema
✅ **Thread-safe**: Exportaciones concurrentes sin problemas
✅ **Eficiente**: Copia datos y libera lock rápido
✅ **Completo**: Toda la información en un archivo
✅ **Testado**: 23 tests garantizan corrección

## 🚀 Próximos Pasos

Fase 4.3 completa. Posibles mejoras futuras:

1. **Más formatos**: Excel (.xlsx), Parquet, HDF5
2. **Filtros**: Exportar solo rango de escenarios
3. **Compresión**: ZIP/GZIP para archivos grandes
4. **S3/Cloud**: Upload directo a cloud storage
5. **Programar**: Exportaciones automáticas cada N minutos

## 📚 Referencias

- **Pandas**: https://pandas.pydata.org/docs/
- **Dash Download**: https://dash.plotly.com/dash-core-components/download
- **Thread Safety**: https://docs.python.org/3/library/threading.html#lock-objects
- **JSON**: https://docs.python.org/3/library/json.html
- **CSV**: https://docs.python.org/3/library/csv.html

---

**Fase 4.3 completada con éxito** ✅

Sistema VarP ahora permite exportar todos los resultados de simulación Monte Carlo en formatos JSON y CSV, con estadísticas completas, tests de normalidad, histórico de convergencia y metadata de trazabilidad. Los datos pueden descargarse directamente desde el dashboard web o programáticamente desde Python.
