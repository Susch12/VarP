# Fase 1.3: Productor Básico

## 📦 Componentes Implementados

### 1. Cliente RabbitMQ (`src/common/rabbitmq_client.py`)
- ✅ Conexión y desconexión a RabbitMQ
- ✅ Declaración de 5 colas del sistema
- ✅ Publicación de mensajes (JSON)
- ✅ Consumo de mensajes
- ✅ Obtención de un mensaje (get)
- ✅ Purga de colas
- ✅ Consulta de tamaño de colas
- ✅ Context manager para uso con `with`

### 2. Productor (`src/producer/producer.py`)
- ✅ Lectura y parsing de modelo
- ✅ Purga y publicación de modelo en `cola_modelo`
- ✅ Generación de escenarios únicos
- ✅ Publicación de escenarios en `cola_escenarios`
- ✅ Cálculo de estadísticas (progreso, tasa, ETA)
- ✅ Publicación de estadísticas en `cola_stats_productor`
- ✅ Logging detallado

### 3. Script CLI (`run_producer.py`)
- ✅ Interface de línea de comandos
- ✅ Argumentos: archivo modelo, número escenarios, host, puerto
- ✅ Modo verbose y quiet
- ✅ Manejo de errores
- ✅ Banner informativo

### 4. Tests y Validación
- ✅ `test_fase_1_3.py` - Script de validación completa

---

## 🚀 Cómo Usar

### Prerequisitos

1. **RabbitMQ corriendo**:
```bash
docker-compose up -d rabbitmq
```

2. **Verificar que RabbitMQ está activo**:
```bash
# Management UI
open http://localhost:15672
# Usuario: admin / Contraseña: password

# O por curl
curl -u admin:password http://localhost:15672/api/overview
```

3. **Instalar dependencias**:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📝 Ejecutar el Productor

### Opción 1: Script CLI (Recomendado)

```bash
# Uso básico con modelo de ejemplo
python run_producer.py modelos/ejemplo_simple.ini

# Especificar número de escenarios
python run_producer.py modelos/ejemplo_simple.ini --escenarios 5000

# Modo verbose
python run_producer.py modelos/ejemplo_simple.ini -v

# Modo silencioso
python run_producer.py modelos/ejemplo_simple.ini -q

# Especificar host de RabbitMQ
python run_producer.py modelos/ejemplo_simple.ini --host rabbitmq.local

# Ver ayuda
python run_producer.py --help
```

### Opción 2: Uso Programático

```python
from src.producer.producer import run_producer

run_producer(
    archivo_modelo='modelos/ejemplo_simple.ini',
    num_escenarios=1000,
    rabbitmq_host='localhost',
    rabbitmq_port=5672
)
```

---

## 🧪 Validar la Implementación

```bash
# Ejecutar tests de validación
python test_fase_1_3.py
```

**Output esperado**:
```
============================================================
VALIDACIÓN FASE 1.3: Productor Básico
============================================================

🔌 Test 1: Conectando a RabbitMQ...
✅ Conexión establecida
   Host: localhost:5672

📦 Test 2: Declarando colas...
✅ Colas declaradas:
   • cola_modelo
   • cola_escenarios
   • cola_resultados
   • cola_stats_productor
   • cola_stats_consumidores

🧹 Test 3: Purgando colas...
   • cola_modelo: 0 mensajes eliminados
   • cola_escenarios: 0 mensajes eliminados
   • cola_resultados: 0 mensajes eliminados
   • cola_stats_productor: 0 mensajes eliminados
✅ Colas purgadas

🏭 Test 4: Ejecutando productor (10 escenarios de prueba)...
✅ Productor ejecutado exitosamente
   • Escenarios generados: 10
   • Tiempo: 0.15s

📊 Test 5: Verificando mensajes en colas...
   • cola_modelo: 1 mensaje(s)
   • cola_escenarios: 10 mensaje(s)
   • cola_stats_productor: 2 mensaje(s)

✅ Mensajes correctos en colas

📖 Test 6: Leyendo modelo de la cola...
✅ Modelo leído de la cola:
   • Modelo ID: suma_normal_1737157200
   • Versión: 1.0
   • Variables: 2
   • Tipo función: expresion
   • Expresión: x + y
   • Modelo devuelto a la cola

🎲 Test 7: Leyendo escenario de la cola...
✅ Escenario leído de la cola:
   • Escenario ID: 0
   • Valores:
     - x = 0.4967
     - y = -0.1383
   • Timestamp: 1737157200.123

🧹 Limpiando...
✅ Desconectado de RabbitMQ

============================================================
✅ FASE 1.3 COMPLETADA EXITOSAMENTE
============================================================

Componentes validados:
  ✅ Cliente RabbitMQ (conexión, declaración, pub/sub)
  ✅ Productor (lectura modelo, generación escenarios)
  ✅ Publicación de modelo en cola
  ✅ Publicación de escenarios en cola
  ✅ Publicación de estadísticas
  ✅ Purga de cola de modelo

Próximo paso: Fase 1.4 - Consumidor Básico
```

---

## 📊 Verificar en RabbitMQ Management UI

1. Abrir http://localhost:15672
2. Login: `admin` / `password`
3. Ir a la pestaña **Queues**
4. Verificar que existan las colas:
   - `cola_modelo` (1 mensaje)
   - `cola_escenarios` (N mensajes según configuración)
   - `cola_stats_productor` (varios mensajes)

5. Click en `cola_modelo` → **Get messages** para ver el contenido

---

## 🔍 Estructura de Mensajes

### Mensaje: Modelo (en `cola_modelo`)
```json
{
  "modelo_id": "suma_normal_1737157200",
  "version": "1.0",
  "timestamp": 1737157200.123,
  "metadata": {
    "nombre": "suma_normal",
    "descripcion": "Suma de dos variables normales independientes",
    "autor": "VarP Team",
    "fecha_creacion": "2025-01-17"
  },
  "variables": [
    {
      "nombre": "x",
      "tipo": "float",
      "distribucion": "normal",
      "parametros": {"media": 0.0, "std": 1.0}
    },
    {
      "nombre": "y",
      "tipo": "float",
      "distribucion": "normal",
      "parametros": {"media": 0.0, "std": 1.0}
    }
  ],
  "funcion": {
    "tipo": "expresion",
    "expresion": "x + y",
    "codigo": null
  },
  "simulacion": {
    "numero_escenarios": 1000,
    "semilla_aleatoria": 42
  }
}
```

### Mensaje: Escenario (en `cola_escenarios`)
```json
{
  "escenario_id": 0,
  "timestamp": 1737157200.456,
  "valores": {
    "x": 0.4967141530112327,
    "y": -0.1382643929856114
  }
}
```

### Mensaje: Stats Productor (en `cola_stats_productor`)
```json
{
  "timestamp": 1737157201.0,
  "escenarios_generados": 500,
  "escenarios_totales": 1000,
  "progreso": 0.5,
  "tasa_generacion": 625.3,
  "tiempo_transcurrido": 0.8,
  "tiempo_estimado_restante": 0.8,
  "estado": "activo"
}
```

---

## 🐛 Troubleshooting

### Error: "No se pudo conectar a RabbitMQ"

**Solución**:
```bash
# Verificar que RabbitMQ está corriendo
docker-compose ps

# Si no está corriendo, levantarlo
docker-compose up -d rabbitmq

# Esperar 30 segundos para que inicie
sleep 30
```

### Error: "Archivo de modelo no encontrado"

**Solución**:
```bash
# Verificar que el archivo existe
ls -la modelos/ejemplo_simple.ini

# Usar ruta absoluta si es necesario
python run_producer.py /ruta/absoluta/al/modelo.ini
```

### Error: Connection refused

**Solución**:
```bash
# Verificar que el puerto 5672 está abierto
netstat -an | grep 5672

# Verificar logs de RabbitMQ
docker-compose logs rabbitmq

# Reiniciar RabbitMQ
docker-compose restart rabbitmq
```

---

## 📈 Progreso del Proyecto

```
FASE 1: MVP Funcional (Día 1-2)
├── ✅ 1.1 Setup inicial          [COMPLETADO]
├── ✅ 1.2 Parser y distribuciones [COMPLETADO]
├── ✅ 1.3 Productor básico        [COMPLETADO]
├── ⏳ 1.4 Consumidor básico       [SIGUIENTE]
└── ⏸️ 1.5 Integración y prueba

Progreso Fase 1: ████████████░░ 60%
```

---

## 📝 Archivos Creados en Esta Fase

| Archivo | Líneas | Descripción |
|---------|--------|-------------|
| `src/common/rabbitmq_client.py` | 267 | Cliente RabbitMQ |
| `src/producer/producer.py` | 345 | Productor de escenarios |
| `run_producer.py` | 148 | Script CLI |
| `test_fase_1_3.py` | 209 | Tests de validación |
| **TOTAL** | **969** | **4 archivos** |

---

## 🎯 Siguiente Paso

**Fase 1.4: Consumidor Básico**

El consumidor será responsable de:
1. Leer el modelo de `cola_modelo` (una sola vez)
2. Compilar/evaluar la expresión del modelo
3. Consumir escenarios de `cola_escenarios`
4. Ejecutar el modelo con los valores del escenario
5. Publicar resultados en `cola_resultados`
6. Publicar estadísticas en `cola_stats_consumidores`
