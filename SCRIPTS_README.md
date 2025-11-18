# Scripts de Automatización - Sistema VarP Monte Carlo

**Fase 5.2: Scripts de automatización**

Este documento describe los scripts de automatización disponibles para gestionar el sistema VarP Monte Carlo distribuido con Docker.

## 📋 Índice

- [Scripts Disponibles](#scripts-disponibles)
- [Instalación y Prerrequisitos](#instalación-y-prerrequisitos)
- [Guía de Uso](#guía-de-uso)
- [Ejemplos Completos](#ejemplos-completos)
- [Solución de Problemas](#solución-de-problemas)

---

## Scripts Disponibles

| Script | Descripción | Uso Principal |
|--------|-------------|---------------|
| `start.sh` | Inicia el sistema completo | Levantar servicios |
| `stop.sh` | Detiene y limpia el sistema | Apagar servicios |
| `clean_queues.sh` | Purga colas de RabbitMQ | Limpiar mensajes |
| `run_simulation.sh` | Ejecuta una simulación completa | Ejecutar simulaciones |

---

## Instalación y Prerrequisitos

### Prerrequisitos

```bash
# Verificar que Docker está instalado
docker --version

# Verificar que docker-compose está instalado
docker-compose --version

# Verificar que el demonio de Docker está corriendo
docker ps
```

### Hacer Scripts Ejecutables

```bash
chmod +x start.sh
chmod +x stop.sh
chmod +x clean_queues.sh
chmod +x run_simulation.sh
```

### Configuración de Variables de Entorno

```bash
# Copiar .env.example a .env
cp .env.example .env

# Editar según necesidad
nano .env
```

---

## Guía de Uso

### 1️⃣ start.sh - Iniciar Sistema

Inicia todos los servicios del sistema VarP (RabbitMQ, Producer, Consumer, Dashboard).

#### Sintaxis

```bash
./start.sh [NUM_CONSUMERS] [OPCIONES]
```

#### Opciones

| Opción | Descripción |
|--------|-------------|
| `NUM_CONSUMERS` | Número de consumidores a iniciar (default: 1) |
| `--build` | Reconstruir imágenes antes de iniciar |
| `--dev` | Modo desarrollo (no rebuilds, solo restart) |
| `--help` | Mostrar ayuda |

#### Ejemplos

```bash
# Iniciar con 1 consumidor (default)
./start.sh

# Iniciar con 5 consumidores paralelos
./start.sh 5

# Reconstruir imágenes e iniciar con 3 consumidores
./start.sh --build 3

# Modo desarrollo (rápido, sin rebuild)
./start.sh --dev
```

#### ¿Qué hace?

1. ✅ Valida que Docker y docker-compose estén instalados
2. ✅ Verifica que el demonio de Docker esté corriendo
3. ✅ Crea archivo `.env` si no existe
4. ✅ Inicia servicios con `docker-compose up -d`
5. ✅ Escala consumidores según parámetro
6. ✅ Espera a que RabbitMQ esté listo (healthcheck)
7. ✅ Muestra estado de servicios
8. ✅ Muestra URLs de acceso

#### Salida Esperada

```
============================================
INICIANDO SISTEMA VarP
============================================

✓ docker-compose está instalado
✓ Demonio de Docker está corriendo
✓ Archivo .env encontrado

============================================
LEVANTANDO SERVICIOS
============================================

ℹ Iniciando servicios con docker-compose...
✓ Servicios iniciados

============================================
ESPERANDO A RABBITMQ
============================================

ℹ Esperando a que RabbitMQ esté listo...
✓ RabbitMQ está listo y respondiendo

============================================
ESTADO DE SERVICIOS
============================================

✓ rabbitmq: corriendo
✓ producer: corriendo
✓ consumer: corriendo (5 réplicas)
✓ dashboard: corriendo

============================================
SISTEMA INICIADO
============================================

ℹ Acceder al dashboard:
  http://localhost:8050

ℹ RabbitMQ Management UI:
  http://localhost:15672
  Usuario: admin
  Contraseña: password
```

---

### 2️⃣ stop.sh - Detener Sistema

Detiene los servicios y opcionalmente limpia volumes e imágenes.

#### Sintaxis

```bash
./stop.sh [OPCIONES]
```

#### Opciones

| Opción | Descripción |
|--------|-------------|
| `--clean` | Detener y eliminar volumes persistentes |
| `--full-clean` | Detener, eliminar volumes e imágenes |
| `--force` | No pedir confirmación |
| `--help` | Mostrar ayuda |

#### Ejemplos

```bash
# Detener servicios (mantener volumes)
./stop.sh

# Detener y eliminar volumes (se pierde historial de RabbitMQ)
./stop.sh --clean

# Limpieza completa (volumes + imágenes)
./stop.sh --full-clean

# Forzar limpieza sin confirmación
./stop.sh --clean --force
```

#### Niveles de Limpieza

| Nivel | Comando | ¿Qué se elimina? | ¿Cuándo usar? |
|-------|---------|------------------|---------------|
| **Básico** | `./stop.sh` | Solo detiene contenedores | Pausa temporal |
| **Clean** | `./stop.sh --clean` | Contenedores + volumes | Reinicio limpio |
| **Full Clean** | `./stop.sh --full-clean` | Todo + imágenes | Rebuild necesario |

#### ¿Qué hace?

1. ✅ Valida que docker-compose esté instalado
2. ✅ Pide confirmación para acciones destructivas (a menos que `--force`)
3. ✅ Detiene contenedores con `docker-compose down`
4. ✅ Opcionalmente elimina volumes (`-v`)
5. ✅ Opcionalmente elimina imágenes (`--rmi local`)
6. ✅ Muestra estado final

#### Salida Esperada

```
============================================
DETENIENDO SISTEMA VarP
============================================

⚠ Esta acción eliminará volumes persistentes
ℹ Se perderá:
  - Datos de RabbitMQ
  - Logs de RabbitMQ

¿Continuar? [y/N]: y

============================================
DETENIENDO SERVICIOS
============================================

ℹ Deteniendo contenedores...
✓ Servicios detenidos y volumes eliminados

============================================
LIMPIEZA COMPLETADA
============================================

✓ No hay contenedores corriendo

ℹ Sistema detenido exitosamente

ℹ Para reiniciar:
  ./start.sh
```

---

### 3️⃣ clean_queues.sh - Purgar Colas

Limpia mensajes de las colas de RabbitMQ sin detener el sistema.

#### Sintaxis

```bash
./clean_queues.sh [OPCIONES]
```

#### Opciones

| Opción | Descripción |
|--------|-------------|
| `--all` | Purgar todas las colas (default) |
| `--escenarios` | Purgar solo cola_escenarios |
| `--resultados` | Purgar solo cola_resultados |
| `--stats` | Purgar solo colas de estadísticas |
| `--modelo` | Purgar solo cola_modelo |
| `--dlq` | Purgar solo Dead Letter Queues |
| `--force` | No pedir confirmación |
| `--help` | Mostrar ayuda |

#### Ejemplos

```bash
# Purgar todas las colas
./clean_queues.sh

# Purgar solo escenarios pendientes
./clean_queues.sh --escenarios

# Purgar stats sin confirmación
./clean_queues.sh --stats --force

# Purgar resultados y escenarios
./clean_queues.sh --resultados --escenarios
```

#### ¿Qué hace?

1. ✅ Verifica que RabbitMQ esté corriendo
2. ✅ Muestra tamaño actual de todas las colas
3. ✅ Pide confirmación (a menos que `--force`)
4. ✅ Purga colas seleccionadas usando RabbitMQ API
5. ✅ Muestra estado final de colas

#### Salida Esperada

```
============================================
LIMPIEZA DE COLAS RABBITMQ
============================================

✓ RabbitMQ está corriendo

============================================
ESTADO ACTUAL DE COLAS
============================================

  cola_modelo: 0 mensajes
  cola_escenarios: 1500 mensajes
  cola_resultados: 230 mensajes
  cola_stats_productor: 12 mensajes
  cola_stats_consumidores: 45 mensajes
  cola_dlq_escenarios: 0 mensajes
  cola_dlq_resultados: 0 mensajes

ℹ Total de mensajes: 1787

⚠ Esta acción eliminará mensajes de las colas

¿Continuar con la purga? [y/N]: y

============================================
PURGANDO COLAS
============================================

ℹ Cola 'cola_modelo': vacía (0 mensajes)
⚠ Cola 'cola_escenarios': 1500 mensajes
✓ Cola 'cola_escenarios' purgada (1500 mensajes eliminados)
⚠ Cola 'cola_resultados': 230 mensajes
✓ Cola 'cola_resultados' purgada (230 mensajes eliminados)
...

============================================
PURGA COMPLETADA
============================================

✓ Todas las colas purgadas exitosamente

ℹ Estado final de colas:

  cola_modelo: 0 mensajes
  cola_escenarios: 0 mensajes
  cola_resultados: 0 mensajes
  ...
```

---

### 4️⃣ run_simulation.sh - Ejecutar Simulación

Ejecuta una simulación completa de Monte Carlo con monitoreo de progreso.

#### Sintaxis

```bash
./run_simulation.sh [OPCIONES]
```

#### Opciones

| Opción | Descripción |
|--------|-------------|
| `-m, --modelo FILE` | Archivo de modelo (.ini) |
| `-n, --num NUM` | Número de escenarios |
| `-c, --consumers NUM` | Número de consumidores |
| `--clean` | Limpiar colas antes de ejecutar |
| `--open-dashboard` | Abrir dashboard automáticamente |
| `--no-wait` | No esperar a que termine |
| `--export-json FILE` | Exportar resultados a JSON |
| `--export-csv FILE` | Exportar resultados a CSV |
| `--help` | Mostrar ayuda |

#### Ejemplos

```bash
# Simulación simple con defaults (1000 escenarios)
./run_simulation.sh

# Simulación personalizada
./run_simulation.sh -m modelos/ejemplo_simple.ini -n 10000 -c 5

# Limpiar colas y ejecutar
./run_simulation.sh --clean -n 5000

# Ejecutar y abrir dashboard automáticamente
./run_simulation.sh -n 1000 --open-dashboard

# Simulación con exportación automática
./run_simulation.sh -n 5000 --export-json results.json --export-csv results.csv

# Simulación rápida sin esperar
./run_simulation.sh -n 100000 -c 10 --no-wait
```

#### ¿Qué hace?

1. ✅ Valida que el modelo existe
2. ✅ Verifica que el sistema esté corriendo (o lo inicia)
3. ✅ Escala consumidores según parámetro
4. ✅ Opcionalmente purga colas (`--clean`)
5. ✅ Opcionalmente abre dashboard (`--open-dashboard`)
6. ✅ Ejecuta el productor con el modelo especificado
7. ✅ Monitorea progreso en tiempo real
8. ✅ Calcula tiempo de ejecución y throughput
9. ✅ Opcionalmente exporta resultados

#### Salida Esperada

```
============================================
CONFIGURACIÓN DE SIMULACIÓN
============================================

✓ Modelo: modelos/ejemplo_simple.ini
✓ Escenarios: 10000
✓ Consumidores: 5

============================================
VERIFICANDO SISTEMA
============================================

✓ Sistema está corriendo
ℹ Escalando consumidores de 1 a 5...
✓ Consumidores escalados a 5

============================================
EJECUTANDO SIMULACIÓN
============================================

ℹ Iniciando productor con:
  - Modelo: modelos/ejemplo_simple.ini
  - Escenarios: 10000
  - Consumidores: 5

Ejecutando simulación con 10000 escenarios...
Productor finalizado
✓ Productor completado - Escenarios enviados a la cola

============================================
MONITOREANDO PROGRESO
============================================

ℹ Esperando a que se procesen todos los escenarios...
ℹ Dashboard disponible en: http://localhost:8050

  ▶ Progreso: 8523/10000 (85%) | Cola escenarios: 1477 | Cola resultados: 45

✓ Simulación completada

============================================
SIMULACIÓN COMPLETADA
============================================

✓ Tiempo de ejecución: 2m 15s
✓ Escenarios procesados: 10000
✓ Consumidores utilizados: 5
✓ Throughput: ~74 escenarios/segundo

ℹ Dashboard disponible en:
  http://localhost:8050

ℹ RabbitMQ Management UI:
  http://localhost:15672
```

---

## Ejemplos Completos

### Ejemplo 1: Primera Ejecución

```bash
# 1. Iniciar sistema con 3 consumidores
./start.sh 3

# 2. Ejecutar simulación de 5000 escenarios
./run_simulation.sh -m modelos/ejemplo_simple.ini -n 5000

# 3. Ver resultados en dashboard
# Abrir http://localhost:8050

# 4. Detener sistema
./stop.sh
```

### Ejemplo 2: Múltiples Simulaciones

```bash
# Iniciar sistema una vez
./start.sh 5

# Ejecutar primera simulación
./run_simulation.sh -m modelos/modelo1.ini -n 10000 --export-csv sim1.csv

# Limpiar colas
./clean_queues.sh --force

# Ejecutar segunda simulación
./run_simulation.sh -m modelos/modelo2.ini -n 10000 --export-csv sim2.csv

# Detener
./stop.sh
```

### Ejemplo 3: Desarrollo y Testing

```bash
# Modo desarrollo (rápido)
./start.sh --dev

# Ejecutar test rápido
./run_simulation.sh -n 100 --clean

# Ver logs si hay problemas
docker-compose logs -f consumer

# Limpiar y probar de nuevo
./clean_queues.sh --force
./run_simulation.sh -n 100

# Detener sin borrar volumes
./stop.sh
```

### Ejemplo 4: Producción Completa

```bash
# Build fresh + 10 consumidores
./start.sh --build 10

# Simulación grande con monitoreo
./run_simulation.sh \
  -m modelos/produccion.ini \
  -n 100000 \
  -c 10 \
  --clean \
  --open-dashboard \
  --export-json results_$(date +%Y%m%d_%H%M%S).json \
  --export-csv results_$(date +%Y%m%d_%H%M%S).csv

# Al terminar, detener pero mantener volumes para análisis
./stop.sh
```

### Ejemplo 5: Limpieza Completa

```bash
# Detener todo y limpiar completamente
./stop.sh --full-clean --force

# Rebuild desde cero
./start.sh --build

# Nueva simulación limpia
./run_simulation.sh -n 1000 --clean
```

---

## Solución de Problemas

### ❌ Error: "docker-compose no está instalado"

```bash
# Instalar docker-compose
sudo apt-get install docker-compose  # Ubuntu/Debian
brew install docker-compose          # macOS
```

### ❌ Error: "Demonio de Docker no está corriendo"

```bash
# Iniciar Docker
sudo systemctl start docker          # Linux
# O abrir Docker Desktop en Windows/macOS
```

### ❌ Error: "RabbitMQ no está listo después de 60 segundos"

```bash
# Ver logs de RabbitMQ
docker-compose logs rabbitmq

# Reiniciar solo RabbitMQ
docker-compose restart rabbitmq

# Si persiste, rebuild
./stop.sh --clean
./start.sh --build
```

### ❌ Consumidores no procesan escenarios

```bash
# Ver logs de consumidores
docker-compose logs consumer

# Verificar colas en RabbitMQ UI
# http://localhost:15672

# Escalar consumidores
docker-compose up -d --scale consumer=5

# Limpiar y reiniciar
./stop.sh --clean
./start.sh 5
```

### ❌ Dashboard no responde

```bash
# Ver logs del dashboard
docker-compose logs dashboard

# Reiniciar dashboard
docker-compose restart dashboard

# Verificar que el puerto 8050 no esté ocupado
lsof -i :8050
```

### ❌ Simulación se queda estancada

```bash
# Ver logs en tiempo real
docker-compose logs -f consumer

# Verificar estado de colas
./clean_queues.sh --force  # Sin argumentos muestra estado

# Reiniciar consumidores
docker-compose restart consumer
```

### ❌ Exportación falla

```bash
# Exportar manualmente desde el dashboard
# 1. Abrir http://localhost:8050
# 2. Hacer clic en botón "Exportar JSON" o "Exportar CSV"

# O usar docker exec directamente
docker-compose exec dashboard python -c "
from src.dashboard.data_manager import DataManager
from src.common.rabbitmq_client import RabbitMQClient
client = RabbitMQClient()
client.connect()
dm = DataManager(client)
print(dm.export_resultados_json())
" > results.json
```

### 🔍 Comandos Útiles de Diagnóstico

```bash
# Ver todos los contenedores
docker-compose ps

# Ver logs de todos los servicios
docker-compose logs

# Ver logs de un servicio específico
docker-compose logs -f consumer

# Ver logs de una réplica específica
docker-compose logs varp-consumer-1

# Entrar a un contenedor
docker-compose exec dashboard bash

# Ver uso de recursos
docker stats

# Ver colas en RabbitMQ
docker exec varp-rabbitmq rabbitmqctl list_queues

# Ver estado de RabbitMQ
docker exec varp-rabbitmq rabbitmq-diagnostics status
```

---

## 📊 Monitoreo y URLs

### Interfaces Web

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| **Dashboard VarP** | http://localhost:8050 | - |
| **RabbitMQ Management** | http://localhost:15672 | admin / password |

### Puertos Utilizados

| Puerto | Servicio | Propósito |
|--------|----------|-----------|
| 5672 | RabbitMQ | AMQP protocol |
| 15672 | RabbitMQ | Management UI |
| 8050 | Dashboard | Web UI |

---

## 🎯 Mejores Prácticas

### 1. **Inicio del Día**

```bash
./start.sh 5
```

### 2. **Entre Simulaciones**

```bash
# Limpiar colas para nueva simulación
./clean_queues.sh --force
```

### 3. **Fin del Día**

```bash
# Detener pero mantener volumes
./stop.sh
```

### 4. **Semanalmente**

```bash
# Limpieza completa y rebuild
./stop.sh --full-clean --force
./start.sh --build
```

### 5. **Simulaciones Grandes**

```bash
# Usar muchos consumidores y no-wait para background
./run_simulation.sh -n 1000000 -c 20 --no-wait

# Monitorear en dashboard
# http://localhost:8050
```

---

## 📝 Notas Adicionales

- Todos los scripts tienen `--help` para ver opciones completas
- Los scripts usan colores para mejor legibilidad (✓ verde, ⚠ amarillo, ✗ rojo)
- La configuración se lee de `.env` si existe
- Los volumes de RabbitMQ persisten entre reinicios (a menos que `--clean`)
- Los consumidores se pueden escalar dinámicamente sin reiniciar todo

---

## 🔗 Enlaces Relacionados

- [Docker README](DOCKER_README.md) - Guía completa de Docker
- [README Principal](README.md) - Documentación del proyecto
- [Fase 4 Optimizaciones](FASE_4_OPTIMIZACIONES_README.md) - Detalles de optimizaciones
- [Tests de Integración](TEST_INTEGRACION_README.md) - Guía de testing

---

**Fase 5.2 completada** ✅

Scripts de automatización para gestión completa del sistema VarP Monte Carlo distribuido.
