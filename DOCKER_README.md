# Docker - Sistema VarP Monte Carlo

## 📋 Resumen

Fase 5.1: Dockerización completa del sistema VarP para simulación Monte Carlo distribuida.

**Componentes dockerizados**:
- ✅ **RabbitMQ**: Message broker con management UI
- ✅ **Producer**: Generador de escenarios
- ✅ **Consumer**: Procesador de escenarios (escalable)
- ✅ **Dashboard**: Dashboard web de monitoreo

**Características**:
- ✅ Health checks en todos los servicios
- ✅ Dependencias con condiciones (wait-for)
- ✅ Volumes persistentes para RabbitMQ
- ✅ Network aislada
- ✅ Variables de entorno configurables
- ✅ Escalabilidad de consumidores
- ✅ Restart policies
- ✅ Resource limits

## 🚀 Quick Start

### 1. Preparación

```bash
# Copiar .env.example a .env
cp .env.example .env

# Opcional: Editar .env para ajustar configuración
nano .env
```

### 2. Construir Imágenes

```bash
# Construir todas las imágenes
docker-compose build

# O construir imagen específica
docker-compose build producer
docker-compose build consumer
docker-compose build dashboard
```

### 3. Iniciar Sistema

```bash
# Iniciar todos los servicios
docker-compose up -d

# Ver logs
docker-compose logs -f

# Ver logs de servicio específico
docker-compose logs -f dashboard
```

### 4. Acceder al Dashboard

Abrir en navegador: **http://localhost:8050**

### 5. Detener Sistema

```bash
# Detener servicios
docker-compose down

# Detener y eliminar volumes
docker-compose down -v
```

## 📊 Servicios

### RabbitMQ

**Imagen**: `rabbitmq:3.12-management-alpine`

**Puertos**:
- `5672`: AMQP protocol
- `15672`: Management UI

**Management UI**: http://localhost:15672
- Usuario: `admin` (configurable en .env)
- Password: `password` (configurable en .env)

**Health check**: `rabbitmq-diagnostics -q ping`

**Volumes**:
- `rabbitmq_data`: Datos persistentes
- `rabbitmq_logs`: Logs

### Producer

**Build**: `Dockerfile.producer`

**Función**: Genera escenarios de simulación Monte Carlo

**Variables de entorno clave**:
```bash
RABBITMQ_HOST=rabbitmq
DEFAULT_NUM_ESCENARIOS=1000
MODELO_FILE=modelos/ejemplo_simple.ini
PRODUCER_STATS_INTERVAL=5
```

**Depends on**: `rabbitmq` (healthy)

**Restart**: `on-failure` (se ejecuta una vez y termina)

### Consumer

**Build**: `Dockerfile.consumer`

**Función**: Procesa escenarios de la cola

**Variables de entorno clave**:
```bash
RABBITMQ_HOST=rabbitmq
CONSUMER_STATS_INTERVAL=5
CONSUMER_PREFETCH_COUNT=1
CONSUMER_MAX_RETRIES=3
```

**Depends on**:
- `rabbitmq` (healthy)
- `producer` (started)

**Restart**: `unless-stopped`

**Escalable**: Sí (ver sección de escalabilidad)

**Resource limits**:
- CPU: 1 core (limit), 0.5 core (reservation)
- Memory: 512MB (limit), 256MB (reservation)

### Dashboard

**Build**: `Dockerfile.dashboard`

**Función**: Dashboard web de monitoreo en tiempo real

**Puerto**: `8050`

**Variables de entorno clave**:
```bash
RABBITMQ_HOST=rabbitmq
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8050
DASHBOARD_REFRESH_INTERVAL=2000
```

**Depends on**: `rabbitmq` (healthy)

**Restart**: `unless-stopped`

**Health check**: `curl -f http://localhost:8050/`

**URL**: http://localhost:8050

## ⚙️ Configuración

### Variables de Entorno

Las variables se configuran en `.env` (basado en `.env.example`):

```bash
# RabbitMQ
RABBITMQ_HOST=rabbitmq  # hostname en Docker network
RABBITMQ_PORT=5672
RABBITMQ_USER=admin
RABBITMQ_PASS=password

# Simulación
DEFAULT_NUM_ESCENARIOS=1000
MODELO_FILE=modelos/ejemplo_simple.ini

# Optimizaciones (Fase 4)
PRODUCER_STATS_INTERVAL=5
CONSUMER_STATS_INTERVAL=5
CONSUMER_PREFETCH_COUNT=1

# Dashboard
DASHBOARD_PORT=8050
```

### Cambiar Modelo de Simulación

Editar `.env`:
```bash
MODELO_FILE=modelos/ejemplo_complejo_negocio.ini
```

Luego reiniciar:
```bash
docker-compose restart producer
```

### Cambiar Número de Escenarios

Editar `.env`:
```bash
DEFAULT_NUM_ESCENARIOS=10000
```

Reiniciar producer:
```bash
docker-compose restart producer
```

## 🔄 Escalabilidad

### Escalar Consumidores

Docker Compose permite escalar el servicio `consumer`:

```bash
# Escalar a 5 consumidores
docker-compose up -d --scale consumer=5

# Escalar a 10 consumidores
docker-compose up -d --scale consumer=10

# Verificar consumidores corriendo
docker-compose ps consumer
```

**Ejemplo**:
```bash
$ docker-compose up -d --scale consumer=5
Creating varp_consumer_1 ... done
Creating varp_consumer_2 ... done
Creating varp_consumer_3 ... done
Creating varp_consumer_4 ... done
Creating varp_consumer_5 ... done
```

**Nota**: El servicio `consumer` no tiene `container_name` para permitir múltiples instancias.

### Performance con Múltiples Consumidores

| Consumidores | Throughput Aprox | Uso recomendado |
|--------------|------------------|------------------|
| 1 | ~100-150 esc/s | Desarrollo |
| 3 | ~250-400 esc/s | Testing |
| 5 | ~400-650 esc/s | Producción pequeña |
| 10 | ~750-1200 esc/s | Producción grande |

**Limitaciones**:
- CPU/RAM disponible en host
- Resource limits configurados (1 CPU, 512MB por consumer)

## 📝 Comandos Útiles

### Ver Estado

```bash
# Ver servicios corriendo
docker-compose ps

# Ver uso de recursos
docker stats

# Ver logs en tiempo real
docker-compose logs -f

# Ver logs de últimos 100 líneas
docker-compose logs --tail=100
```

### Gestión de Servicios

```bash
# Iniciar servicio específico
docker-compose up -d producer

# Detener servicio específico
docker-compose stop consumer

# Reiniciar servicio
docker-compose restart dashboard

# Ver logs de servicio
docker-compose logs -f rabbitmq
```

### Debugging

```bash
# Ejecutar comando en contenedor corriendo
docker-compose exec dashboard sh

# Ver variables de entorno de un servicio
docker-compose exec producer env

# Inspeccionar health check
docker inspect varp-dashboard --format='{{json .State.Health}}'
```

### Limpieza

```bash
# Detener y remover contenedores
docker-compose down

# Detener, remover contenedores y volumes
docker-compose down -v

# Remover imágenes también
docker-compose down --rmi all -v

# Limpiar todo Docker (¡cuidado!)
docker system prune -a
```

## 🏥 Health Checks

Todos los servicios tienen health checks configurados:

### RabbitMQ
```yaml
healthcheck:
  test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 40s
```

### Dashboard
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8050/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

### Ver Estado de Health Checks

```bash
# Ver estado de todos los servicios
docker-compose ps

# Inspeccionar health check específico
docker inspect varp-rabbitmq --format='{{json .State.Health}}' | jq
```

## 🔗 Networks

Sistema usa network aislada `varp-network`:

```bash
# Ver networks
docker network ls | grep varp

# Inspeccionar network
docker network inspect varp_varp-network

# Ver qué contenedores están en la network
docker network inspect varp_varp-network --format='{{range .Containers}}{{.Name}} {{end}}'
```

**Beneficios**:
- Aislamiento de otros servicios
- DNS automático entre contenedores (por nombre)
- Comunicación segura interna

## 💾 Volumes

Volumes persistentes para RabbitMQ:

```bash
# Ver volumes
docker volume ls | grep varp

# Inspeccionar volume
docker volume inspect varp_rabbitmq_data

# Backup de datos de RabbitMQ
docker run --rm -v varp_rabbitmq_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/rabbitmq_backup.tar.gz -C /data .

# Restaurar backup
docker run --rm -v varp_rabbitmq_data:/data -v $(pwd):/backup alpine \
  tar xzf /backup/rabbitmq_backup.tar.gz -C /data
```

## 🎯 Ejemplos de Uso

### Ejemplo 1: Simulación Simple

```bash
# 1. Copiar .env
cp .env.example .env

# 2. Editar .env
nano .env
# Configurar:
#   DEFAULT_NUM_ESCENARIOS=1000
#   MODELO_FILE=modelos/ejemplo_simple.ini

# 3. Iniciar con 1 consumidor
docker-compose up -d

# 4. Ver progreso
docker-compose logs -f producer
docker-compose logs -f consumer

# 5. Abrir dashboard
open http://localhost:8050
```

### Ejemplo 2: Simulación Grande con 5 Consumidores

```bash
# 1. Editar .env
nano .env
# Configurar:
#   DEFAULT_NUM_ESCENARIOS=50000
#   MODELO_FILE=modelos/ejemplo_complejo_negocio.ini

# 2. Iniciar con 5 consumidores
docker-compose up -d --scale consumer=5

# 3. Monitorear
watch -n 2 'docker-compose ps'

# 4. Ver dashboard en tiempo real
open http://localhost:8050
```

### Ejemplo 3: Desarrollo con Hot Reload

Para desarrollo, montar código fuente como volume:

```yaml
# En docker-compose.override.yml
services:
  dashboard:
    volumes:
      - ./src:/app/src:ro
    command: python -m src.dashboard.app --debug
```

```bash
# Crear override
cat > docker-compose.override.yml << 'EOF'
version: '3.8'
services:
  dashboard:
    volumes:
      - ./src:/app/src:ro
EOF

# Iniciar
docker-compose up -d dashboard
```

## 🐛 Troubleshooting

### Producer Falla

**Síntoma**: `docker-compose logs producer` muestra errores.

**Causas comunes**:
1. RabbitMQ no está listo
   - **Solución**: Esperar más tiempo, verificar health check
2. Archivo de modelo no existe
   - **Solución**: Verificar que `MODELO_FILE` existe en `modelos/`

```bash
# Verificar logs
docker-compose logs producer

# Verificar modelo existe
docker-compose exec producer ls -la modelos/
```

### Consumer No Procesa

**Síntoma**: Consumer corriendo pero no procesa escenarios.

**Causas comunes**:
1. Modelo no publicado (producer no terminó)
   - **Solución**: Esperar a que producer termine
2. No hay escenarios en cola
   - **Solución**: Verificar RabbitMQ management UI

```bash
# Ver estado de colas en RabbitMQ
open http://localhost:15672

# Ver logs de consumer
docker-compose logs -f consumer
```

### Dashboard No Carga

**Síntoma**: http://localhost:8050 no responde.

**Causas comunes**:
1. Dashboard no inició correctamente
   - **Solución**: Ver logs
2. Puerto 8050 ocupado
   - **Solución**: Cambiar `DASHBOARD_PORT` en .env

```bash
# Ver logs
docker-compose logs dashboard

# Verificar si puerto está escuchando
netstat -an | grep 8050

# Cambiar puerto
echo "DASHBOARD_PORT=8051" >> .env
docker-compose restart dashboard
```

### Out of Memory

**Síntoma**: Consumidores se detienen con OOM.

**Causas**:
- Demasiados consumidores para RAM disponible
- Modelo muy complejo

**Soluciones**:
```bash
# Reducir número de consumidores
docker-compose up -d --scale consumer=3

# Aumentar memory limit en docker-compose.yml
# limits: memory: 1G
```

## 📊 Monitoreo

### RabbitMQ Management

http://localhost:15672

**Qué ver**:
- **Queues**: Tamaño de colas, tasa de mensajes
- **Connections**: Conexiones activas
- **Consumers**: Consumidores por cola
- **Overview**: Tasa de mensajes global

### Docker Stats

```bash
# Ver uso de recursos en tiempo real
docker stats

# Ver solo servicios VarP
docker stats $(docker ps --filter "label=com.varp.service" -q)
```

### Logs Centralizados

Para producción, considerar:
- **ELK Stack**: Elasticsearch + Logstash + Kibana
- **Grafana + Loki**: Visualización de logs
- **Datadog**: Monitoreo completo

## 🔒 Seguridad

### Mejores Prácticas

1. **Cambiar credenciales** de RabbitMQ en `.env`:
   ```bash
   RABBITMQ_USER=mi_usuario
   RABBITMQ_PASS=contraseña_segura_123
   ```

2. **No exponer RabbitMQ** al exterior en producción:
   ```yaml
   # Comentar o eliminar
   # ports:
   #   - "5672:5672"
   #   - "15672:15672"
   ```

3. **Usar secrets** en Docker Swarm:
   ```yaml
   secrets:
     rabbitmq_password:
       external: true
   ```

4. **Limitar recursos**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1'
         memory: 512M
   ```

## 📁 Estructura de Archivos

```
VarP/
├── Dockerfile.producer          # Imagen del productor
├── Dockerfile.consumer          # Imagen del consumidor
├── Dockerfile.dashboard         # Imagen del dashboard
├── docker-compose.yml           # Orquestación completa
├── .dockerignore               # Archivos a ignorar en build
├── .env.example                # Template de variables
├── .env                        # Variables (crear desde .example)
├── DOCKER_README.md            # Este archivo
└── src/                        # Código fuente
    ├── producer/
    ├── consumer/
    ├── dashboard/
    └── common/
```

## 🚀 Despliegue en Producción

### Docker Swarm

```bash
# Inicializar swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.yml varp

# Ver servicios
docker stack services varp

# Escalar
docker service scale varp_consumer=10

# Remover stack
docker stack rm varp
```

### Kubernetes

Convertir docker-compose a Kubernetes manifests:

```bash
# Usar kompose
kompose convert -f docker-compose.yml

# O crear manualmente
kubectl create deployment varp-producer --image=varp/producer
kubectl create deployment varp-consumer --image=varp/consumer --replicas=5
kubectl create deployment varp-dashboard --image=varp/dashboard
```

## 📚 Referencias

- **Docker Compose**: https://docs.docker.com/compose/
- **Docker Health Checks**: https://docs.docker.com/engine/reference/builder/#healthcheck
- **RabbitMQ Docker**: https://hub.docker.com/_/rabbitmq
- **Docker Best Practices**: https://docs.docker.com/develop/dev-best-practices/

---

**Fase 5.1: Dockerización Completa** ✅

Sistema VarP completamente dockerizado y listo para despliegue en cualquier plataforma que soporte Docker.
