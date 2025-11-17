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

## 📋 Plan de Implementación

### Fase 1: Definición y Setup (Semana 1)

**Objetivos:**
- ✅ Definir formato final del archivo de modelo
- ✅ Configurar infraestructura básica

**Tareas:**
1. [ ] **DECISIÓN**: Definir formato de función en archivo modelo
2. [ ] **DECISIÓN**: Definir distribuciones de probabilidad soportadas
3. [ ] **DECISIÓN**: Definir política de timeout delivery
4. [ ] Configurar proyecto Python
5. [ ] Instalar y configurar RabbitMQ
6. [ ] Crear estructura de directorios

**Entregables:**
- Especificación completa del archivo de modelo
- RabbitMQ funcionando
- Estructura base del proyecto

### Fase 2: Productor (Semana 2)

**Objetivos:**
- Implementar generación y publicación de escenarios

**Tareas:**
1. [ ] Parser de archivo de modelo
2. [ ] Validador de modelo
3. [ ] Generador de valores aleatorios por distribución
4. [ ] Publicación de modelo en cola
5. [ ] Generación y publicación de escenarios
6. [ ] Publicación de estadísticas
7. [ ] Tests unitarios

**Entregables:**
- Productor funcional
- Tests pasando

### Fase 3: Consumidor (Semana 3)

**Objetivos:**
- Implementar ejecución de modelos

**Tareas:**
1. [ ] Lectura de modelo de cola
2. [ ] Compilador/interpretador de función
3. [ ] **DECISIÓN**: Implementar sandbox de seguridad
4. [ ] Ejecución de modelo con escenario
5. [ ] Publicación de resultados
6. [ ] Publicación de estadísticas
7. [ ] Manejo de errores y timeouts
8. [ ] Tests unitarios

**Entregables:**
- Consumidor funcional
- Tests pasando

### Fase 4: Dashboard (Semana 4)

**Objetivos:**
- Visualización en tiempo real

**Tareas:**
1. [ ] **DECISIÓN**: Elegir framework (Dash vs Streamlit)
2. [ ] Consumo de estadísticas
3. [ ] Panel de productor
4. [ ] Tabla de consumidores
5. [ ] Gráfica de progreso
6. [ ] Gráfica de tasas
7. [ ] **DECISIÓN**: Gráficas adicionales necesarias
8. [ ] Tests de integración

**Entregables:**
- Dashboard funcional
- Actualización en tiempo real

### Fase 5: Integración y Testing (Semana 5)

**Objetivos:**
- Pruebas end-to-end

**Tareas:**
1. [ ] Tests de integración completos
2. [ ] Pruebas de carga
3. [ ] Manejo de fallos
4. [ ] Optimización de rendimiento
5. [ ] Documentación de código

**Entregables:**
- Sistema completo funcionando
- Documentación completa

### Fase 6: Deployment (Semana 6)

**Objetivos:**
- Despliegue del sistema

**Tareas:**
1. [ ] Dockerizar componentes
2. [ ] Docker Compose completo
3. [ ] Scripts de inicialización
4. [ ] Documentación de usuario
5. [ ] Ejemplos de uso

**Entregables:**
- Sistema desplegable
- Manual de usuario

---

## ❓ Preguntas Pendientes

### Críticas (Bloquean Implementación)

1. **Formato de la Función del Modelo**
   - [ ] ¿Código Python embebido?
   - [ ] ¿Expresión matemática?
   - [ ] ¿Módulo externo?
   - [ ] ¿Combinación?

2. **Política Time-out Delivery**
   - [ ] ¿Qué significa exactamente?
   - [ ] ¿Cómo se implementa en RabbitMQ?
   - [ ] ¿Timeout específico?

3. **Caducidad del Modelo**
   - [ ] ¿Purgar cola al publicar nuevo modelo?
   - [ ] ¿TTL automático?
   - [ ] ¿Otro mecanismo?

4. **Seguridad de Ejecución**
   - [ ] ¿Sandbox para exec()?
   - [ ] ¿Restricciones de imports?
   - [ ] ¿Timeout de ejecución?
   - [ ] ¿Validación de código?

### Importantes (Afectan Diseño)

5. **Distribuciones de Probabilidad**
   - [ ] ¿Lista específica de distribuciones?
   - [ ] ¿Solo las de scipy.stats?
   - [ ] ¿Distribuciones personalizadas?

6. **Tipo de Resultado**
   - [ ] ¿Solo float?
   - [ ] ¿Puede ser dict/array?
   - [ ] ¿Múltiples outputs?

7. **Gráficas del Dashboard**
   - [ ] ¿Qué gráficas adicionales?
   - [ ] ¿Mostrar distribución de resultados?
   - [ ] ¿Estadísticas de RabbitMQ?

8. **Almacenamiento de Resultados**
   - [ ] ¿Solo en cola o también en DB/archivo?
   - [ ] ¿Análisis posterior de resultados?
   - [ ] ¿Formato de exportación?

### Deseables (Mejoras Futuras)

9. **Validación de Modelos**
   - [ ] ¿Ejecutar test antes de publicar?
   - [ ] ¿Valores de ejemplo en archivo?

10. **Recursos del Sistema**
    - [ ] ¿Monitorear CPU/memoria?
    - [ ] ¿Limitar recursos por consumidor?

11. **Persistencia**
    - [ ] ¿Guardar histórico de simulaciones?
    - [ ] ¿Reiniciar simulación interrumpida?

12. **Escalabilidad**
    - [ ] ¿Número máximo de consumidores?
    - [ ] ¿Límite de escenarios por simulación?

---

## 📞 Siguiente Paso

**Por favor, responde las preguntas críticas para continuar con la implementación:**

1. ¿Qué formato prefieres para especificar la función del modelo?
2. ¿Qué significa "time-out delivery" en el contexto del proyecto?
3. ¿Cómo debe manejarse la caducidad del modelo al cargar uno nuevo?
4. ¿Qué medidas de seguridad se requieren al ejecutar código arbitrario?
5. ¿Qué distribuciones de probabilidad deben soportarse?
6. ¿Qué información adicional debe mostrar el dashboard?

---
