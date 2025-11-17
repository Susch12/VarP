# Sistema Distribuido de Simulación Monte Carlo con Paso de Mensajes

## 📋 Tabla de Contenidos

1. [Descripción General](#descripción-general)
2. [Requisitos del Sistema](#requisitos-del-sistema)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Especificación del Archivo de Modelo](#especificación-del-archivo-de-modelo)
5. [Componentes del Sistema](#componentes-del-sistema)
6. [Políticas de Colas en RabbitMQ](#políticas-de-colas-en-rabbitmq)
7. [Formato de Mensajes](#formato-de-mensajes)
8. [Implementación Detallada](#implementación-detallada)
9. [Dashboard y Visualización](#dashboard-y-visualización)
10. [Flujo de Ejecución](#flujo-de-ejecución)
11. [Casos de Uso](#casos-de-uso)
12. [Stack Tecnológico](#stack-tecnológico)
13. [Estructura del Proyecto](#estructura-del-proyecto)
14. [Plan de Implementación](#plan-de-implementación)
15. [Preguntas Pendientes](#preguntas-pendientes)

---

## 📖 Descripción General

Este sistema implementa una **simulación Monte Carlo distribuida** utilizando el **modelo de paso de mensajes** a través de RabbitMQ como broker de mensajería.

### Características Principales

✅ **Productor único**: Genera escenarios únicos y publica función del modelo  
✅ **Modelo flexible**: Cualquier función definida en archivo de texto  
✅ **Variables estocásticas**: Diferentes distribuciones de probabilidad  
✅ **Procesamiento distribuido**: Múltiples consumidores en paralelo  
✅ **Visualización en tiempo real**: Dashboard con estadísticas del productor y consumidores  
✅ **Gestión de modelos**: TTL con caducidad al cargar nuevo modelo  

---

## 🎯 Requisitos del Sistema

### Requisitos Funcionales

1. **Productor**:
   - Leer archivo de texto con definición del modelo
   - Generar escenarios únicos basados en distribuciones de probabilidad
   - Publicar función del modelo en cola específica
   - Publicar escenarios en cola de trabajo

2. **Cola de Modelo**:
   - Política: Time-out delivery
   - Caducidad: Al cargar nuevo modelo
   - Contenido: Función ejecutable y metadatos

3. **Consumidores**:
   - Leer modelo de la cola (una sola vez)
   - Obtener escenario de la cola de escenarios
   - Ejecutar modelo con el escenario
   - Publicar resultado en cola de resultados

4. **Dashboard**:
   - Mostrar avance de simulación en tiempo real
   - Estadísticas del productor
   - Estadísticas de cada consumidor individual
   - Visualización gráfica

### Requisitos No Funcionales

- **Escalabilidad**: Soportar N consumidores
- **Confiabilidad**: Manejo de fallos en consumidores
- **Performance**: Procesamiento eficiente de escenarios
- **Observabilidad**: Logs y métricas detalladas

---

## 🏗️ Arquitectura del Sistema

### Diagrama de Arquitectura
```
┌─────────────────────────────────────────────────────────────────────────┐
│                      SISTEMA DE SIMULACIÓN MONTE CARLO                  │
└─────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐
│   PRODUCTOR      │
│                  │
│ 1. Lee modelo    │
│    desde archivo │
│ 2. Genera N      │
│    escenarios    │
│    únicos        │
└────────┬─────────┘
         │
         │ Publica
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          RABBITMQ BROKER                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ COLA: modelo                                                  │ │
│  │ Policy: Time-out delivery                                     │ │
│  │ TTL: Caduca al publicar nuevo modelo                         │ │
│  │ Content: {funcion_codigo, metadata, variables, timestamp}    │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ COLA: escenarios                                              │ │
│  │ Policy: FIFO                                                  │ │
│  │ Content: {escenario_id, valores_variables, timestamp}        │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ COLA: resultados                                              │ │
│  │ Policy: Persistent                                            │ │
│  │ Content: {escenario_id, resultado, consumer_id, timestamp}   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ COLA: stats_productor                                         │ │
│  │ Content: {escenarios_generados, tasa, estado, timestamp}     │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ COLA: stats_consumidores                                      │ │
│  │ Content: {consumer_id, procesados, estado, timestamp}        │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
         │                                           │
         │ Consume modelo (1 vez)                    │ Consume stats
         │ Consume escenarios                        │
         ▼                                           ▼
┌──────────────────┐                    ┌──────────────────────┐
│  CONSUMIDOR 1    │                    │     DASHBOARD        │
│                  │                    │                      │
│ 1. Lee modelo    │                    │ • Stats productor   │
│ 2. Obtiene       │                    │ • Stats consumidores│
│    escenario     │                    │ • Progreso total    │
│ 3. Ejecuta       │                    │ • Gráficas RT       │
│    modelo        │                    │ • Resultados        │
│ 4. Publica       │                    └──────────────────────┘
│    resultado     │
└──────────────────┘

┌──────────────────┐
│  CONSUMIDOR 2    │
│  ...             │
└──────────────────┘

┌──────────────────┐
│  CONSUMIDOR N    │
│  ...             │
└──────────────────┘
```

---

## 📝 Especificación del Archivo de Modelo

### Preguntas Clave para Definir el Formato

**¿Cómo se especificará la función del modelo?**

Opciones:
1. Código Python embebido en el archivo
2. Expresión matemática (ej: "x^2 + y*z")
3. Referencia a función Python importable
4. DSL (Domain Specific Language) propio

**¿Qué información debe contener el archivo?**

Necesitamos definir:
- [ ] ¿Nombre/ID del modelo?
- [ ] ¿Versión del modelo?
- [ ] ¿Descripción del modelo?
- [ ] ¿Lista de variables de entrada?
- [ ] ¿Para cada variable: nombre, tipo, distribución, parámetros?
- [ ] ¿Definición de la función a ejecutar?
- [ ] ¿Parámetros de la simulación (número de escenarios)?
- [ ] ¿Configuración adicional?

### Propuesta de Formato (Pendiente de Aprobación)
```ini
# ============================================
# METADATA DEL MODELO
# ============================================
[MODELO]
nombre = modelo_ejemplo
version = 1.0
descripcion = Descripción del modelo a simular
autor = Equipo de Desarrollo
fecha_creacion = 2025-01-16

# ============================================
# VARIABLES DE ENTRADA
# ============================================
[VARIABLES]
# Formato: nombre_variable, tipo, distribucion, param1, param2, ...

# Variable con distribución normal
x, float, normal, media=0, std=1

# Variable con distribución uniforme
y, float, uniform, min=0, max=10

# Variable con distribución exponencial
z, float, exponential, lambda=1.5

# Variable con distribución log-normal
w, float, lognormal, mu=0, sigma=1

# Variable con distribución triangular
v, float, triangular, left=0, mode=5, right=10

# Variable con distribución binomial
n, int, binomial, n=10, p=0.5

# ============================================
# FUNCIÓN DEL MODELO
# ============================================
[FUNCION]
# Opción 1: Código Python directo
codigo = """
def modelo(x, y, z, w, v, n):
    '''
    Función del modelo a ejecutar.
    
    Args:
        x, y, z, w, v, n: Variables de entrada
        
    Returns:
        float o dict: Resultado del modelo
    '''
    resultado = x**2 + y*z - w + v/n
    return resultado
"""

# Opción 2: Expresión matemática simple
# expresion = x**2 + y*z - w + v/n

# Opción 3: Referencia a módulo externo
# modulo = mi_modulo.mi_funcion

# ============================================
# PARÁMETROS DE SIMULACIÓN
# ============================================
[SIMULACION]
numero_escenarios = 10000
semilla_aleatoria = 42
# ¿Otros parámetros necesarios?

# ============================================
# CONFIGURACIÓN ADICIONAL (OPCIONAL)
# ============================================
[CONFIGURACION]
timeout_consumidor = 300  # segundos
# ¿Qué más necesitamos configurar?
```

### ⚠️ Preguntas Pendientes sobre el Archivo de Modelo

1. **¿Preferencia de formato para la función?**
   - Código Python embebido
   - Expresión matemática
   - Módulo externo
   - Combinación de opciones

2. **¿Restricciones en la función?**
   - ¿Puede usar librerías externas (numpy, scipy)?
   - ¿Límite de complejidad?
   - ¿Debe retornar un tipo específico?

3. **¿Validación del modelo?**
   - ¿Validar sintaxis antes de publicar?
   - ¿Ejecutar prueba con valores de ejemplo?

4. **¿Distribuciones soportadas?**
   - ¿Cuáles distribuciones de probabilidad necesitamos soportar?
   - ¿Solo distribuciones estándar de scipy?
   - ¿Distribuciones personalizadas?

---

## 🔧 Componentes del Sistema

### 1. Productor

**Responsabilidades:**
1. Leer y parsear archivo de modelo
2. Validar modelo (sintaxis, distribuciones)
3. Generar N escenarios únicos
4. Publicar modelo en cola `modelo`
5. Publicar escenarios en cola `escenarios`
6. Publicar estadísticas en cola `stats_productor`

**Pseudocódigo:**
```python
class Productor:
    def __init__(self, rabbitmq_connection):
        self.connection = rabbitmq_connection
        self.channel = self.connection.channel()
        
    def ejecutar(self, archivo_modelo, num_escenarios):
        # 1. Leer modelo
        modelo = self.leer_modelo(archivo_modelo)
        
        # 2. Validar modelo
        self.validar_modelo(modelo)
        
        # 3. Publicar modelo en cola
        self.publicar_modelo(modelo)
        
        # 4. Generar y publicar escenarios
        for i in range(num_escenarios):
            escenario = self.generar_escenario(modelo, i)
            self.publicar_escenario(escenario)
            
            # Publicar estadísticas
            if i % 100 == 0:
                self.publicar_stats({
                    'escenarios_generados': i,
                    'total': num_escenarios,
                    'progreso': i / num_escenarios,
                    'timestamp': time.time()
                })
    
    def leer_modelo(self, archivo):
        """Lee y parsea archivo de modelo."""
        # Implementación pendiente del formato
        pass
    
    def validar_modelo(self, modelo):
        """Valida sintaxis y estructura del modelo."""
        # ¿Qué validaciones hacer?
        pass
    
    def generar_escenario(self, modelo, escenario_id):
        """
        Genera valores aleatorios para cada variable
        según su distribución.
        """
        escenario = {
            'escenario_id': escenario_id,
            'timestamp': time.time(),
            'valores': {}
        }
        
        for variable in modelo['variables']:
            valor = self.generar_valor_variable(variable)
            escenario['valores'][variable['nombre']] = valor
            
        return escenario
    
    def generar_valor_variable(self, variable):
        """Genera valor según distribución de la variable."""
        dist_type = variable['distribucion']
        params = variable['parametros']
        
        if dist_type == 'normal':
            return np.random.normal(params['media'], params['std'])
        elif dist_type == 'uniform':
            return np.random.uniform(params['min'], params['max'])
        # ... otras distribuciones
        
    def publicar_modelo(self, modelo):
        """
        Publica modelo en cola con política TTL.
        Al publicar nuevo modelo, el anterior caduca.
        """
        mensaje = {
            'modelo_id': modelo['metadata']['nombre'],
            'version': modelo['metadata']['version'],
            'funcion_codigo': modelo['funcion']['codigo'],
            'variables': modelo['variables'],
            'timestamp': time.time()
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='cola_modelo',
            body=json.dumps(mensaje),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistente
                # ¿Configurar TTL aquí?
            )
        )
    
    def publicar_escenario(self, escenario):
        """Publica escenario en cola de trabajo."""
        self.channel.basic_publish(
            exchange='',
            routing_key='cola_escenarios',
            body=json.dumps(escenario)
        )
    
    def publicar_stats(self, stats):
        """Publica estadísticas del productor."""
        self.channel.basic_publish(
            exchange='',
            routing_key='cola_stats_productor',
            body=json.dumps(stats)
        )
```

### 2. Consumidor

**Responsabilidades:**
1. Leer modelo de cola `modelo` (una sola vez)
2. Cargar y compilar función del modelo
3. Consumir escenarios de cola `escenarios`
4. Ejecutar modelo con valores del escenario
5. Publicar resultado en cola `resultados`
6. Publicar estadísticas propias en cola `stats_consumidores`

**Pseudocódigo:**
```python
class Consumidor:
    def __init__(self, rabbitmq_connection, consumer_id):
        self.connection = rabbitmq_connection
        self.channel = self.connection.channel()
        self.consumer_id = consumer_id
        self.modelo_cargado = False
        self.funcion_modelo = None
        self.escenarios_procesados = 0
        
    def ejecutar(self):
        # 1. Leer modelo (solo una vez)
        if not self.modelo_cargado:
            self.cargar_modelo()
        
        # 2. Configurar callback para escenarios
        self.channel.basic_consume(
            queue='cola_escenarios',
            on_message_callback=self.procesar_escenario,
            auto_ack=False
        )
        
        # 3. Iniciar consumo
        print(f"Consumidor {self.consumer_id} esperando escenarios...")
        self.channel.start_consuming()
    
    def cargar_modelo(self):
        """Lee modelo de la cola (una sola vez)."""
        # Obtener mensaje de cola_modelo
        method, properties, body = self.channel.basic_get(
            queue='cola_modelo',
            auto_ack=True
        )
        
        if body is None:
            raise Exception("No hay modelo en la cola")
        
        modelo_msg = json.loads(body)
        
        # Compilar función
        self.funcion_modelo = self.compilar_funcion(
            modelo_msg['funcion_codigo']
        )
        
        self.modelo_cargado = True
        print(f"Consumidor {self.consumer_id}: Modelo cargado")
    
    def compilar_funcion(self, codigo_funcion):
        """
        Compila código de la función para ejecución.
        
        ⚠️ PREGUNTA: ¿Cómo manejar seguridad?
        - ¿Sandbox para ejecución?
        - ¿Restricciones de imports?
        - ¿Timeout de ejecución?
        """
        # Opción 1: exec() - ¿Seguro?
        namespace = {}
        exec(codigo_funcion, namespace)
        return namespace['modelo']
        
        # Opción 2: Usar ast para validar
        # Opción 3: Módulo externo pre-validado
    
    def procesar_escenario(self, ch, method, properties, body):
        """Callback para procesar cada escenario."""
        try:
            inicio = time.time()
            
            # Parsear escenario
            escenario = json.loads(body)
            
            # Ejecutar modelo
            resultado = self.ejecutar_modelo(escenario)
            
            # Calcular tiempo de ejecución
            tiempo_ejecucion = time.time() - inicio
            
            # Publicar resultado
            self.publicar_resultado(escenario, resultado, tiempo_ejecucion)
            
            # Actualizar estadísticas
            self.escenarios_procesados += 1
            self.publicar_stats(tiempo_ejecucion)
            
            # ACK del mensaje
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            print(f"Error procesando escenario: {e}")
            # ¿NACK y requeue?
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
    
    def ejecutar_modelo(self, escenario):
        """
        Ejecuta función del modelo con valores del escenario.
        
        ⚠️ PREGUNTA: ¿Timeout de ejecución?
        """
        valores = escenario['valores']
        
        # Ejecutar función con timeout (opcional)
        resultado = self.funcion_modelo(**valores)
        
        return resultado
    
    def publicar_resultado(self, escenario, resultado, tiempo):
        """Publica resultado en cola de resultados."""
        mensaje = {
            'escenario_id': escenario['escenario_id'],
            'consumer_id': self.consumer_id,
            'resultado': resultado,
            'tiempo_ejecucion': tiempo,
            'timestamp': time.time()
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='cola_resultados',
            body=json.dumps(mensaje)
        )
    
    def publicar_stats(self, tiempo_ejecucion):
        """Publica estadísticas del consumidor."""
        stats = {
            'consumer_id': self.consumer_id,
            'escenarios_procesados': self.escenarios_procesados,
            'ultimo_tiempo_ejecucion': tiempo_ejecucion,
            'timestamp': time.time()
        }
        
        self.channel.basic_publish(
            exchange='',
            routing_key='cola_stats_consumidores',
            body=json.dumps(stats)
        )
```

### 3. Dashboard

**Responsabilidades:**
1. Consumir estadísticas del productor
2. Consumir estadísticas de cada consumidor
3. Consumir resultados (opcional)
4. Mostrar progreso en tiempo real
5. Visualizar métricas gráficamente

**Componentes a Mostrar:**
```
┌─────────────────────────────────────────────────────────┐
│              DASHBOARD DE SIMULACIÓN                    │
├─────────────────────────────────────────────────────────┤
│ PRODUCTOR                                               │
│  • Escenarios generados: 7,543 / 10,000 (75.4%)       │
│  • Tasa de generación: 1,234 esc/seg                   │
│  • Estado: ████████░░ Activo                           │
│  • Tiempo transcurrido: 00:06:12                       │
│  • Tiempo estimado restante: 00:02:05                  │
├─────────────────────────────────────────────────────────┤
│ CONSUMIDORES (8 activos)                                │
│                                                         │
│  ID    Procesados    Tasa      Últ.Tiempo    Estado   │
│  ─────────────────────────────────────────────────────  │
│  C1      1,245      156/s      12ms          ⚙️ Activo│
│  C2      1,238      155/s      13ms          ⚙️ Activo│
│  C3      1,251      157/s      11ms          ⚙️ Activo│
│  C4      1,247      156/s      12ms          ⚙️ Activo│
│  C5      1,240      155/s      14ms          ⚙️ Activo│
│  C6      1,243      156/s      13ms          ⚙️ Activo│
│  C7      1,249      156/s      12ms          ⚙️ Activo│
│  C8      1,230      154/s      15ms          ⚙️ Activo│
│                                                         │
│  Total procesado: 9,943                                │
│  Tasa total: 1,247 esc/seg                            │
│  Tiempo promedio: 13ms                                 │
├─────────────────────────────────────────────────────────┤
│ COLAS RABBITMQ                                          │
│  • cola_modelo: 1 mensaje                              │
│  • cola_escenarios: 57 pendientes                     │
│  • cola_resultados: 9,943 mensajes                    │
├─────────────────────────────────────────────────────────┤
│ GRÁFICAS                                                │
│  [Gráfica de progreso en tiempo real]                 │
│  [Gráfica de tasa de procesamiento]                   │
│  [Gráfica de distribución de tiempos]                 │
│  [Gráfica de resultados (si aplica)]                  │
└─────────────────────────────────────────────────────────┘
```

**Pseudocódigo:**
```python
class Dashboard:
    def __init__(self, rabbitmq_connection):
        self.connection = rabbitmq_connection
        self.channel = self.connection.channel()
        
        # Estado del sistema
        self.stats_productor = {}
        self.stats_consumidores = {}
        
    def iniciar(self):
        """Inicia dashboard en tiempo real."""
        # Configurar callbacks
        self.channel.basic_consume(
            queue='cola_stats_productor',
            on_message_callback=self.actualizar_stats_productor
        )
        
        self.channel.basic_consume(
            queue='cola_stats_consumidores',
            on_message_callback=self.actualizar_stats_consumidor
        )
        
        # Opcional: consumir resultados
        # self.channel.basic_consume(
        #     queue='cola_resultados',
        #     on_message_callback=self.procesar_resultado
        # )
        
        # Iniciar consumo en thread separado
        consumer_thread = threading.Thread(
            target=self.channel.start_consuming
        )
        consumer_thread.start()
        
        # Iniciar aplicación web (Dash/Streamlit)
        self.app = self.crear_app()
        self.app.run_server(host='0.0.0.0', port=8050)
    
    def actualizar_stats_productor(self, ch, method, properties, body):
        """Actualiza estadísticas del productor."""
        stats = json.loads(body)
        self.stats_productor = stats
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def actualizar_stats_consumidor(self, ch, method, properties, body):
        """Actualiza estadísticas de un consumidor."""
        stats = json.loads(body)
        consumer_id = stats['consumer_id']
        self.stats_consumidores[consumer_id] = stats
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def crear_app(self):
        """Crea aplicación Dash para visualización."""
        import dash
        from dash import dcc, html
        import plotly.graph_objs as go
        
        app = dash.Dash(__name__)
        
        app.layout = html.Div([
            html.H1("Dashboard de Simulación Monte Carlo"),
            
            # Actualización automática cada segundo
            dcc.Interval(
                id='interval-component',
                interval=1000,  # 1 segundo
                n_intervals=0
            ),
            
            # Sección: Productor
            html.Div([
                html.H2("Productor"),
                html.Div(id='stats-productor')
            ]),
            
            # Sección: Consumidores
            html.Div([
                html.H2("Consumidores"),
                html.Div(id='stats-consumidores')
            ]),
            
            # Gráficas
            dcc.Graph(id='grafica-progreso'),
            dcc.Graph(id='grafica-tasa'),
            # ¿Más gráficas necesarias?
        ])
        
        # Callbacks para actualización
        @app.callback(
            [Output('stats-productor', 'children'),
             Output('stats-consumidores', 'children'),
             Output('grafica-progreso', 'figure'),
             Output('grafica-tasa', 'figure')],
            Input('interval-component', 'n_intervals')
        )
        def actualizar_dashboard(n):
            # Renderizar estadísticas actuales
            # Implementación completa pendiente
            pass
        
        return app
```

---

## 🔐 Políticas de Colas en RabbitMQ

### Cola: `modelo`

**Configuración:**
```python
channel.queue_declare(
    queue='cola_modelo',
    durable=True,  # Persistente
    arguments={
        'x-max-length': 1,  # Solo 1 modelo activo
        'x-message-ttl': None,  # ¿TTL específico o None?
        # ¿Time-out delivery?: ¿Cómo configurar?
    }
)
```

**⚠️ Preguntas Pendientes:**

1. **Time-out delivery policy**: 
   - ¿Qué significa exactamente en este contexto?
   - ¿Timeout para que los consumidores lean el modelo?
   - ¿Configuración específica en RabbitMQ?

2. **Caducidad al cargar nuevo modelo**:
   - ¿Cómo implementar? Opciones:
     - Purgar cola antes de publicar nuevo modelo
     - TTL que se resetea con nuevo mensaje
     - Policy de RabbitMQ específica

### Cola: `escenarios`

**Configuración:**
```python
channel.queue_declare(
    queue='cola_escenarios',
    durable=True,
    arguments={
        'x-max-length': 100000,  # Capacidad máxima
        # ¿Otras configuraciones necesarias?
    }
)
```

### Cola: `resultados`

**Configuración:**
```python
channel.queue_declare(
    queue='cola_resultados',
    durable=True,
    # ¿Procesamiento de resultados en dashboard?
    # ¿O solo almacenamiento?
)
```

### Colas de Estadísticas

**Configuración:**
```python
# Stats productor
channel.queue_declare(
    queue='cola_stats_productor',
    durable=False,  # No necesitan persistencia
    arguments={
        'x-max-length': 100,  # Últimas 100 actualizaciones
        'x-message-ttl': 60000  # 60 segundos
    }
)

# Stats consumidores
channel.queue_declare(
    queue='cola_stats_consumidores',
    durable=False,
    arguments={
        'x-max-length': 1000,
        'x-message-ttl': 60000
    }
)
```

---

## 📦 Formato de Mensajes

### Mensaje: Modelo
```json
{
  "modelo_id": "modelo_ejemplo",
  "version": "1.0",
  "timestamp": 1737050400.123,
  "metadata": {
    "nombre": "modelo_ejemplo",
    "descripcion": "Descripción del modelo",
    "autor": "Equipo"
  },
  "variables": [
    {
      "nombre": "x",
      "tipo": "float",
      "distribucion": "normal",
      "parametros": {
        "media": 0,
        "std": 1
      }
    },
    {
      "nombre": "y",
      "tipo": "float",
      "distribucion": "uniform",
      "parametros": {
        "min": 0,
        "max": 10
      }
    }
  ],
  "funcion": {
    "codigo": "def modelo(x, y):\n    return x**2 + y",
    "tipo": "python"
  }
}
```

### Mensaje: Escenario
```json
{
  "escenario_id": 12345,
  "timestamp": 1737050401.456,
  "valores": {
    "x": 0.5234,
    "y": 7.8912
  }
}
```

### Mensaje: Resultado
```json
{
  "escenario_id": 12345,
  "consumer_id": "C1",
  "timestamp": 1737050401.567,
  "resultado": 8.1651,
  "tiempo_ejecucion": 0.012,
  "metadata": {
    "version_modelo": "1.0"
  }
}
```

### Mensaje: Stats Productor
```json
{
  "timestamp": 1737050402.000,
  "escenarios_generados": 7543,
  "escenarios_totales": 10000,
  "progreso": 0.7543,
  "tasa_generacion": 1234.5,
  "tiempo_transcurrido": 372.5,
  "tiempo_estimado_restante": 125.2,
  "estado": "activo"
}
```

### Mensaje: Stats Consumidor
```json
{
  "consumer_id": "C1",
  "timestamp": 1737050402.100,
  "escenarios_procesados": 1245,
  "tiempo_ultimo_escenario": 0.012,
  "tiempo_promedio": 0.013,
  "tasa_procesamiento": 156.8,
  "estado": "activo",
  "memoria_utilizada": 234.5,
  "cpu_utilizado": 45.2
}
```

---

## 💻 Implementación Detallada

### Estructura de Directorios
```
proyecto-montecarlo/
│
├── README.md
├── requirements.txt
├── .env
│
├── modelos/                    # Archivos de modelo
│   ├── ejemplo_simple.txt
│   ├── ejemplo_complejo.txt
│   └── ...
│
├── src/
│   ├── __init__.py
│   │
│   ├── producer/
│   │   ├── __init__.py
│   │   ├── producer.py
│   │   ├── model_parser.py    # Parse archivo modelo
│   │   ├── scenario_generator.py
│   │   └── model_validator.py
│   │
│   ├── consumer/
│   │   ├── __init__.py
│   │   ├── consumer.py
│   │   ├── model_executor.py  # Ejecuta función modelo
│   │   └── function_compiler.py
│   │
│   ├── dashboard/
│   │   ├── __init__.py
│   │   ├── app.py
│   │   ├── components/
│   │   │   ├── producer_panel.py
│   │   │   ├── consumers_table.py
│   │   │   └── charts.py
│   │   └── data_manager.py
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── rabbitmq_client.py
│   │   ├── message_schemas.py
│   │   ├── distributions.py   # Generadores de distribuciones
│   │   └── config.py
│   │
│   └── utils/
│       ├── __init__.py
│       └── logger.py
│
├── tests/
│   ├── test_producer.py
│   ├── test_consumer.py
│   ├── test_model_parser.py
│   └── test_distributions.py
│
└── docker/
    ├── docker-compose.yml
    ├── Dockerfile.producer
    ├── Dockerfile.consumer
    └── Dockerfile.dashboard
```

### Configuración de RabbitMQ

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  rabbitmq:
    image: rabbitmq:3-management
    container_name: rabbitmq
    ports:
      - "5672:5672"    # AMQP
      - "15672:15672"  # Management UI
    environment:
      RABBITMQ_DEFAULT_USER: admin
      RABBITMQ_DEFAULT_PASS: password
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  # ¿Incluir producer, consumers y dashboard en compose?
  # ¿O ejecutar manualmente?

volumes:
  rabbitmq_data:
```

---

## 📊 Dashboard y Visualización

### Gráficas Requeridas

#### 1. Progreso de Simulación
```python
def crear_grafica_progreso(stats_productor):
    """
    Barra de progreso mostrando:
    - Escenarios generados vs total
    - Escenarios procesados vs total
    """
    generados = stats_productor.get('escenarios_generados', 0)
    total = stats_productor.get('escenarios_totales', 1)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=generados,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "Progreso de Simulación"},
        delta={'reference': total},
        gauge={
            'axis': {'range': [None, total]},
            'bar': {'color': "darkblue"},
            'steps': [
                {'range': [0, total], 'color': "lightgray"}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': total * 0.9
            }
        }
    ))
    
    return fig
```

#### 2. Tasa de Procesamiento
```python
def crear_grafica_tasa(stats_productor, stats_consumidores):
    """
    Gráfica de línea mostrando:
    - Tasa de generación del productor
    - Tasa total de consumo
    - Tasa individual por consumidor (opcional)
    """
    # Implementación pendiente
    # ¿Mantener histórico de tasas?
    # ¿Cuántos puntos mostrar?
    pass
```

#### 3. Estado de Consumidores
```python
def crear_tabla_consumidores(stats_consumidores):
    """
    Tabla mostrando para cada consumidor:
    - ID
    - Escenarios procesados
    - Tasa actual
    - Último tiempo de ejecución
    - Estado (activo/inactivo)
    - Uso de recursos (opcional)
    """
    # Implementación pendiente
    pass
```

#### 4. Distribución de Tiempos de Ejecución
```python
def crear_histograma_tiempos(stats_consumidores):
    """
    Histograma de tiempos de ejecución de consumidores.
    ¿Útil para identificar cuellos de botella?
    """
    # Implementación pendiente
    pass
```

### ⚠️ Preguntas sobre Visualización

1. **¿Qué gráficas adicionales son necesarias?**
   - ¿Distribución de resultados?
   - ¿Estadísticas de RabbitMQ (tamaño de colas)?
   - ¿Uso de recursos del sistema?

2. **¿Frecuencia de actualización?**
   - ¿1 segundo es adecuado?
   - ¿Configurable?

3. **¿Almacenar histórico?**
   - ¿Guardar estadísticas para análisis posterior?
   - ¿En qué formato (DB, CSV, JSON)?

---

## 🔄 Flujo de Ejecución

### Secuencia Completa
```
Tiempo  Productor           RabbitMQ          Consumidor       Dashboard
  │         │                   │                 │                │
  │ 1. Leer modelo             │                 │                │
  │────────>│                   │                 │                │
  │         │                   │                 │                │
  │ 2. Validar                  │                 │                │
  │────────>│                   │                 │                │
  │         │                   │                 │                │
  │ 3. Publicar modelo          │                 │                │
  ├────────────────────────────>│                 │                │
  │         │                   │                 │                │
  │         │                   │ 4. Leer modelo  │                │
  │         │                   │<────────────────┤                │
  │         │                   │                 │                │
  │         │                   │                 │ 5. Compilar    │
  │         │                   │                 │    función     │
  │         │                   │                 │───────>        │
  │         │                   │                 │                │
  │ 6. Generar esc 1            │                 │                │
  │────────>│                   │                 │                │
  │         │                   │                 │                │
  │ 7. Publicar esc 1           │                 │                │
  ├────────────────────────────>│                 │                │
  │         │                   │                 │                │
  │ 8. Generar esc 2            │                 │                │
  │────────>│                   │                 │                │
  │         │                   │                 │                │
  │ 9. Publicar stats           │                 │                │
  ├────────────────────────────>│                 │                │
  │         │                   │                 │                │
  │         │                   │                 │                │
  │         │                   │ 10. Consumir    │                │
  │         │                   │     esc 1       │                │
  │         │                   │<────────────────┤                │
  │         │                   │                 │                │
  │         │                   │                 │ 11. Ejecutar   │
  │         │                   │                 │───────>        │
  │         │                   │                 │                │
  │         │                   │ 12. Publicar    │                │
  │         │                   │     resultado   │                │
  │         │                   │<────────────────┤                │
  │         │                   │                 │                │
  │         │                   │ 13. Publicar    │                │
  │         │                   │     stats       │                │
  │         │                   │<────────────────┤                │
  │         │                   │                 │                │
  │         │                   │                 │                │
  │         │                   │ 14. Consumir stats              │
  │         │                   ├────────────────────────────────>│
  │         │                   │                 │                │
  │         │                   │                 │                │ 15. Actualizar
  │         │                   │                 │                │     UI
  │         │                   │                 │                │───────>
  │         │                   │                 │                │
```

---

## 🎯 Casos de Uso

### Caso 1: Simulación Simple

**Modelo:** Suma de dos variables normales

**Archivo de modelo:**
```ini
[MODELO]
nombre = suma_normal
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
codigo = """
def modelo(x, y):
    return x + y
"""

[SIMULACION]
numero_escenarios = 1000
```

**Ejecución:**
```bash
# Terminal 1: RabbitMQ
docker-compose up rabbitmq

# Terminal 2: Productor
python src/producer/producer.py --modelo modelos/suma_normal.txt

# Terminal 3-6: Consumidores
python src/consumer/consumer.py --id C1 &
python src/consumer/consumer.py --id C2 &
python src/consumer/consumer.py --id C3 &
python src/consumer/consumer.py --id C4 &

# Terminal 7: Dashboard
python src/dashboard/app.py
```

**Resultados Esperados:**
- 1000 escenarios procesados
- Distribución de resultados: Normal(0, √2)
- Dashboard muestra progreso 100%

### Caso 2: Modelo Complejo

**Modelo:** Simulación de cartera de inversión

**⚠️ Pregunta:** ¿Este caso de uso requiere funcionalidad adicional?

---

## 🛠️ Stack Tecnológico

### Lenguajes y Frameworks

| Componente | Tecnología | Versión |
|------------|------------|---------|
| Lenguaje | Python | 3.10+ |
| Message Broker | RabbitMQ | 3.12+ |
| Cliente RabbitMQ | Pika | 1.3+ |
| Dashboard | Dash / Streamlit | Latest |
| Visualización | Plotly | 5.14+ |

### Librerías Python

**requirements.txt:**
```
# Core
numpy>=1.24.0
scipy>=1.10.0

# Message Broker
pika>=1.3.0

# Dashboard
dash>=2.10.0
plotly>=5.14.0
dash-bootstrap-components>=1.4.0

# Opcional: Streamlit (alternativa a Dash)
# streamlit>=1.22.0

# Utilidades
python-dotenv>=1.0.0
```

---

## 📋 Plan de Implementación (1 Semana)

### **FASE 1: MVP Funcional (Día 1-2) - 2 días** 🚀

**Objetivo**: Sistema básico productor-consumidor funcionando con expresiones matemáticas

**Tareas**:
- [ ] Setup inicial del proyecto
  - [ ] Crear virtualenv + requirements.txt
  - [ ] Estructura de directorios (src/, modelos/, tests/)
  - [ ] Configurar .gitignore

- [ ] Docker Compose con RabbitMQ
  - [ ] docker-compose.yml básico
  - [ ] Verificar RabbitMQ Management UI (puerto 15672)

- [ ] Parser de modelos (solo .ini con expresiones)
  - [ ] Leer archivo .ini
  - [ ] Parser sección [METADATA]
  - [ ] Parser sección [VARIABLES]
  - [ ] Parser sección [FUNCION] tipo="expresion"
  - [ ] Parser sección [SIMULACION]

- [ ] Generador de distribuciones
  - [ ] Normal (media, std)
  - [ ] Uniforme (min, max)
  - [ ] Exponencial (lambda)
  - [ ] Tests unitarios distribuciones

- [ ] Productor básico
  - [ ] Conexión a RabbitMQ con Pika
  - [ ] Declaración de colas (modelo, escenarios)
  - [ ] Purgar + publicar modelo en cola_modelo
  - [ ] Generar escenarios únicos (ID + timestamp)
  - [ ] Publicar escenarios en cola_escenarios
  - [ ] Tests de productor

- [ ] Consumidor básico
  - [ ] Leer modelo de cola (una vez al iniciar)
  - [ ] Evaluador de expresiones seguras con AST
  - [ ] Consumir escenarios de cola_escenarios
  - [ ] Ejecutar expresión con valores del escenario
  - [ ] Publicar resultados en cola_resultados
  - [ ] Tests de consumidor

- [ ] Integración y prueba
  - [ ] Ejemplo simple: suma de 2 normales
  - [ ] Ejecutar 1000 escenarios con 2 consumidores
  - [ ] Validar resultados

**Entregables**:
- ✅ Productor + Consumidor funcionando
- ✅ Modelo de ejemplo ejecutable
- ✅ Tests básicos pasando

**Horas estimadas**: 16h (8h/día x 2 días)

---

### **FASE 2: Dashboard y Monitoreo (Día 3) - 1 día** 📊

**Objetivo**: Visualización del progreso en tiempo real

**Tareas**:
- [ ] Estadísticas del productor
  - [ ] Calcular progreso, tasa generación, ETA
  - [ ] Publicar stats en cola_stats_productor cada 1s
  - [ ] Tests de cálculo métricas

- [ ] Estadísticas de consumidores
  - [ ] Calcular procesados, tasa, tiempo último
  - [ ] Publicar stats en cola_stats_consumidores cada 2s
  - [ ] Tests métricas consumidor

- [ ] Dashboard Dash básico
  - [ ] Setup app Dash + layout básico
  - [ ] Consumidor de stats en thread separado
  - [ ] Panel productor (texto + barra progreso)
  - [ ] Tabla consumidores (ID, procesados, tasa, estado)
  - [ ] Auto-refresh cada 2 segundos (dcc.Interval)

- [ ] Gráficas esenciales
  - [ ] Gauge de progreso (Plotly Indicator)
  - [ ] Línea de tasa de procesamiento
  - [ ] Barras de estado de colas RabbitMQ

**Entregables**:
- ✅ Dashboard funcional en http://localhost:8050
- ✅ Actualización en tiempo real
- ✅ 4 componentes visuales

**Horas estimadas**: 8h (1 día)

---

### **FASE 3: Funciones Avanzadas (Día 4) - 1 día** 🔐

**Objetivo**: Soporte para código Python y más distribuciones

**Tareas**:
- [ ] Ejecutor de código Python seguro
  - [ ] Integrar RestrictedPython
  - [ ] Whitelist imports (math, numpy básico)
  - [ ] Timeout decorator (30s)
  - [ ] Namespace seguro con safe_globals
  - [ ] Tests de seguridad (intentar código malicioso)

- [ ] Distribuciones adicionales
  - [ ] Lognormal (mu, sigma)
  - [ ] Triangular (left, mode, right)
  - [ ] Binomial (n, p)
  - [ ] Tests de las 6 distribuciones

- [ ] Actualizar parser
  - [ ] Soporte tipo="codigo" en sección [FUNCION]
  - [ ] Validación sintaxis Python básica
  - [ ] Tests de parsing código Python

- [ ] Ejemplo complejo
  - [ ] Modelo con función def modelo()
  - [ ] Usar las 6 distribuciones
  - [ ] Validar ejecución correcta

**Entregables**:
- ✅ Funciones Python complejas ejecutándose
- ✅ 6 distribuciones de probabilidad
- ✅ Validación de seguridad implementada

**Horas estimadas**: 8h (1 día)

---

### **FASE 4: Robustez y Producción (Día 5-6) - 2 días** 🛡️

**Objetivo**: Sistema confiable, robusto y listo para uso real

**Tareas**:
- [ ] Manejo de errores avanzado
  - [ ] Dead Letter Queue (DLQ) para mensajes fallidos
  - [ ] Reintentos automáticos (máx 3 intentos)
  - [ ] Logging estructurado (logging.config)
  - [ ] Manejo excepciones en consumidor

- [ ] Configuración óptima RabbitMQ
  - [ ] Prefetch count = 1 (fair dispatch)
  - [ ] Persistencia de mensajes
  - [ ] Heartbeat configuration
  - [ ] Connection pooling

- [ ] Exportación de resultados
  - [ ] Consumir cola_resultados en dashboard
  - [ ] Almacenar resultados en memoria
  - [ ] Exportar a JSON
  - [ ] Exportar a CSV (con pandas)
  - [ ] Botón de descarga en dashboard

- [ ] Tests de integración
  - [ ] Test con 10,000 escenarios
  - [ ] Test con 5 consumidores paralelos
  - [ ] Test de recuperación ante fallo de consumidor
  - [ ] Test de cambio de modelo (purga correcta)

- [ ] Optimizaciones
  - [ ] Validar uso de memoria
  - [ ] Optimizar tamaño de mensajes
  - [ ] Ajustar intervalos de stats

**Entregables**:
- ✅ Sistema robusto con DLQ y reintentos
- ✅ Exportación de resultados funcional
- ✅ Tests de carga pasando

**Horas estimadas**: 16h (8h/día x 2 días)

---

### **FASE 5: Deployment y Documentación (Día 7) - 1 día** 🐳

**Objetivo**: Sistema desplegable y completamente documentado

**Tareas**:
- [ ] Dockerización completa
  - [ ] Dockerfile.producer
  - [ ] Dockerfile.consumer
  - [ ] Dockerfile.dashboard
  - [ ] docker-compose.yml completo (4 servicios)
  - [ ] Variables de entorno (.env.example)
  - [ ] Health checks en compose

- [ ] Scripts de automatización
  - [ ] start.sh (levantar todo el sistema)
  - [ ] stop.sh (detener y limpiar)
  - [ ] clean_queues.sh (purgar colas)
  - [ ] run_simulation.sh (ejecutar simulación)

- [ ] Documentación de usuario
  - [ ] Actualizar README con Quick Start
  - [ ] Guía de instalación paso a paso
  - [ ] 2 ejemplos funcionales documentados
  - [ ] Troubleshooting común
  - [ ] Arquitectura final (diagrama)

- [ ] Tests finales
  - [ ] Test end-to-end completo con Docker
  - [ ] Test con docker-compose up
  - [ ] Validar en sistema limpio

- [ ] Cleanup del código
  - [ ] Docstrings completos
  - [ ] Remover código comentado
  - [ ] Formatear con black/autopep8
  - [ ] Linting con flake8

**Entregables**:
- ✅ Sistema completamente dockerizado
- ✅ `docker-compose up` funciona en <2 min
- ✅ README actualizado con Quick Start
- ✅ 2 ejemplos completos
- ✅ Tests E2E pasando

**Horas estimadas**: 8h (1 día)

---

## ⏱️ **Timeline Visual (1 Semana)**

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLAN DE 7 DÍAS                                │
├─────────────────────────────────────────────────────────────────┤
│ DÍA 1-2 │ FASE 1: MVP Funcional                                 │
│         │ ✅ Productor + Consumidor + Expresiones                │
├─────────────────────────────────────────────────────────────────┤
│ DÍA 3   │ FASE 2: Dashboard                                     │
│         │ ✅ Visualización en tiempo real                        │
├─────────────────────────────────────────────────────────────────┤
│ DÍA 4   │ FASE 3: Funciones Avanzadas                           │
│         │ ✅ Código Python + 6 distribuciones                    │
├─────────────────────────────────────────────────────────────────┤
│ DÍA 5-6 │ FASE 4: Robustez                                      │
│         │ ✅ DLQ + Exportación + Tests                           │
├─────────────────────────────────────────────────────────────────┤
│ DÍA 7   │ FASE 5: Deployment                                    │
│         │ ✅ Docker + Docs + E2E Tests                           │
└─────────────────────────────────────────────────────────────────┘

Total: 56 horas de desarrollo (8h/día)
```

---

## 🎯 Métricas de Éxito (Día 7 - 18:00)

El sistema debe cumplir:

1. ✅ **Funcionalidad**: Ejecutar 10,000 escenarios con 5 consumidores
2. ✅ **Performance**: Completar simulación en <5 minutos
3. ✅ **Dashboard**: Actualización en tiempo real cada 2s
4. ✅ **Robustez**: Recuperarse de fallo de 2 consumidores
5. ✅ **Deployment**: `docker-compose up` funcional en <2 minutos
6. ✅ **Documentación**: Quick Start + 2 ejemplos ejecutables
7. ✅ **Tests**: Cobertura >70% en componentes críticos

---

## 🔥 Estrategia de Ejecución

### Prioridades
1. **Funcionalidad antes que perfección**: MVP primero, pulir después
2. **Tests pragmáticos**: Solo casos críticos, no 100% cobertura
3. **Documentación en código**: Docstrings > docs extensos
4. **Reutilizar**: Ejemplos oficiales de RabbitMQ/Dash

### Plan de Contingencia
- **Día 3 atrasado** → Simplificar dashboard (solo logs)
- **Día 4 atrasado** → Skip código Python (solo expresiones)
- **Día 5 atrasado** → Skip DLQ (solo logging)
- **Día 6 atrasado** → Reducir tests
- **Día 7 atrasado** → Docker Compose mínimo

---

## ✅ Decisiones Técnicas (RESUELTAS)

### 1. Formato de la Función del Modelo ✅

**DECISIÓN**: Enfoque híbrido con 2 opciones (Fase 1: expresiones, Fase 3: código Python)

```ini
# Opción A: Expresión matemática simple (FASE 1)
[FUNCION]
tipo = expresion
expresion = x**2 + y*z - w + v/n

# Opción B: Código Python validado (FASE 3)
[FUNCION]
tipo = codigo
codigo = """
def modelo(x, y, z):
    resultado = x**2 + y*z
    return resultado
"""
```

**Justificación**: Expresiones son más seguras para MVP, código Python añade flexibilidad después.

---

### 2. Política Time-out Delivery ✅

**DECISIÓN**: Interpretación como "Entrega con timeout de lectura"

```python
# Cola configurada sin TTL automático
channel.queue_declare(
    queue='cola_modelo',
    durable=True,
    arguments={
        'x-max-length': 1,  # Solo 1 modelo activo
        'x-single-active-consumer': False  # Múltiples consumidores leen
    }
)

# Consumidores leen con timeout al iniciar
method, properties, body = channel.basic_get(
    queue='cola_modelo',
    auto_ack=False
)
```

**Justificación**: Cada consumidor lee el modelo una vez al iniciar, sin expiración automática.

---

### 3. Caducidad del Modelo ✅

**DECISIÓN**: Purgar cola + Version ID al publicar nuevo modelo

```python
def publicar_modelo(self, modelo):
    # 1. Purgar modelo anterior
    self.channel.queue_purge('cola_modelo')

    # 2. Publicar nuevo modelo con ID único
    mensaje = {
        'modelo_id': f"{modelo['nombre']}_{timestamp}",
        'version': modelo['version'],
        'timestamp': time.time(),
        # ... resto del modelo
    }

    self.channel.basic_publish(
        exchange='',
        routing_key='cola_modelo',
        body=json.dumps(mensaje),
        properties=pika.BasicProperties(delivery_mode=2)
    )
```

**Justificación**: Simple y predecible. Consumidores nuevos siempre obtienen el modelo actual.

---

### 4. Seguridad de Ejecución ✅

**DECISIÓN**: Enfoque por fases

**FASE 1** - Expresiones matemáticas (AST seguro):
```python
import ast
import operator

ALLOWED_OPS = {
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub
}

def evaluar_expresion_segura(expresion, variables):
    """Evalúa expresión matemática usando AST."""
    tree = ast.parse(expresion, mode='eval')
    validar_ast(tree)  # Solo operaciones permitidas
    return evaluar_nodo(tree.body, variables)
```

**FASE 3** - Código Python (RestrictedPython):
```python
from RestrictedPython import compile_restricted, safe_globals
import timeout_decorator

@timeout_decorator.timeout(30)  # Timeout 30s
def ejecutar_codigo_restringido(codigo, variables):
    byte_code = compile_restricted(codigo, '<string>', 'exec')
    safe_namespace = {
        '__builtins__': safe_globals,
        'math': math,  # Solo módulos permitidos
    }
    exec(byte_code, safe_namespace)
    return safe_namespace['modelo'](**variables)
```

**Medidas de seguridad**:
- ✅ Whitelist de operaciones/imports
- ✅ Timeout de ejecución (30s)
- ✅ Sin acceso a sistema de archivos
- ✅ Validación AST antes de ejecutar

---

### 5. Distribuciones de Probabilidad ✅

**DECISIÓN**: 6 distribuciones estándar usando scipy.stats

| Distribución | Parámetros | Fase |
|--------------|------------|------|
| Normal | media, std | Fase 1 |
| Uniforme | min, max | Fase 1 |
| Exponencial | lambda | Fase 1 |
| Lognormal | mu, sigma | Fase 3 |
| Triangular | left, mode, right | Fase 3 |
| Binomial | n, p | Fase 3 |

**Justificación**: Cubren 95% de casos de uso, todas disponibles en scipy.stats.

---

### 6. Tipo de Resultado ✅

**DECISIÓN**: Soportar `float`, `int`, y `dict` (sin arrays por ahora)

```python
# Ejemplos válidos
return 42.5           # float
return 100            # int
return {'valor': 42.5, 'categoria': 'A'}  # dict
```

**Justificación**: Flexibilidad para resultados simples y múltiples outputs.

---

### 7. Gráficas del Dashboard ✅

**DECISIÓN**: 4 gráficas esenciales

1. **Progreso de simulación** (gauge): Escenarios generados vs total
2. **Tasa de procesamiento** (línea): Velocidad productor vs consumidores
3. **Tabla de consumidores**: Estado individual de cada consumidor
4. **Estado de colas RabbitMQ** (barras): Mensajes pendientes

**Justificación**: Balance entre información útil y simplicidad de implementación.

---

### 8. Almacenamiento de Resultados ✅

**DECISIÓN**: Cola RabbitMQ + Exportación a JSON/CSV

```python
# En dashboard: consumir resultados y exportar
def exportar_resultados(resultados, formato='json'):
    if formato == 'json':
        with open('resultados.json', 'w') as f:
            json.dump(resultados, f)
    elif formato == 'csv':
        df = pd.DataFrame(resultados)
        df.to_csv('resultados.csv', index=False)
```

**Justificación**: No requiere base de datos adicional, suficiente para análisis posterior.

---

### 9-12. Funcionalidades Deseables ✅

**DECISIÓN**: Fuera del scope de la semana 1

- ⏸️ Validación de modelos con test cases (Mejora futura)
- ⏸️ Monitoreo CPU/memoria por consumidor (Mejora futura)
- ⏸️ Persistencia de historial (Mejora futura)
- ⏸️ Límites de escalabilidad: 100 consumidores / 100k escenarios (suficiente para V1)

---

## 🚀 Inicio de Implementación

### Estado del Proyecto: ✅ LISTO PARA DESARROLLO

Todas las preguntas críticas han sido resueltas. El sistema está completamente especificado y listo para implementación.

### Próximos Pasos Inmediatos

1. **DÍA 1 - Mañana (08:00-12:00)**
   ```bash
   # Setup del proyecto
   mkdir -p VarP/{src,modelos,tests,docker}
   cd VarP
   python3 -m venv venv
   source venv/bin/activate
   pip install pika numpy scipy
   ```

2. **DÍA 1 - Tarde (13:00-18:00)**
   ```bash
   # Levantar RabbitMQ
   docker-compose up -d rabbitmq
   # Abrir Management UI: http://localhost:15672
   # Credenciales: admin/password

   # Comenzar desarrollo del parser
   touch src/parser/model_parser.py
   ```

### Comandos Rápidos

```bash
# Iniciar desarrollo
git checkout -b feature/fase-1-mvp
docker-compose up -d rabbitmq

# Verificar RabbitMQ
curl -u admin:password http://localhost:15672/api/overview

# Ejecutar tests
pytest tests/ -v

# Al final del día 7
docker-compose up  # Todo el sistema
```

### Checklist Pre-Desarrollo

- [x] README actualizado con decisiones técnicas
- [x] Plan de 5 fases en 1 semana definido
- [x] Todas las preguntas críticas resueltas
- [x] Stack tecnológico definido
- [ ] Entorno de desarrollo configurado (Día 1 - mañana)
- [ ] RabbitMQ funcionando (Día 1 - mañana)

### Recursos Útiles

- **RabbitMQ Docs**: https://www.rabbitmq.com/tutorials/tutorial-one-python.html
- **Pika Docs**: https://pika.readthedocs.io/
- **Dash Docs**: https://dash.plotly.com/
- **RestrictedPython**: https://restrictedpython.readthedocs.io/
- **AST Module**: https://docs.python.org/3/library/ast.html

---

## 📊 Resumen Ejecutivo

### Cumplimiento de Requisitos: ✅ 100%

| Componente | Estado | Descripción |
|------------|--------|-------------|
| Productor único | ✅ Especificado | Genera escenarios únicos desde modelo .ini |
| Modelo desde archivo | ✅ Especificado | Parser .ini con expresiones + código Python |
| Variables estocásticas | ✅ Especificado | 6 distribuciones de probabilidad |
| RabbitMQ | ✅ Especificado | 5 colas configuradas |
| Cola de modelo | ✅ Especificado | Time-out delivery + purga al actualizar |
| Consumidores | ✅ Especificado | Leen modelo 1 vez + ejecutan escenarios |
| Dashboard | ✅ Especificado | Dash con actualización cada 2s |
| Stats productor | ✅ Especificado | Progreso, tasa, ETA |
| Stats consumidores | ✅ Especificado | Individual por consumer_id |

### Timeline: 1 Semana (56 horas)

- **Días 1-2**: MVP Funcional (Productor + Consumidor)
- **Día 3**: Dashboard en tiempo real
- **Día 4**: Funciones Python + 6 distribuciones
- **Días 5-6**: Robustez (DLQ + Tests + Exportación)
- **Día 7**: Deployment (Docker + Docs)

### Entregables Finales (Día 7 - 18:00)

1. ✅ Sistema funcionando con `docker-compose up`
2. ✅ 10,000 escenarios procesados en <5 minutos
3. ✅ Dashboard web en http://localhost:8050
4. ✅ 2 ejemplos documentados
5. ✅ Tests con cobertura >70%
6. ✅ Exportación JSON/CSV

---

**Última actualización**: 2025-01-17
**Versión del documento**: 2.0 (Plan de 1 semana)
**Estado**: ✅ Listo para implementación

---
