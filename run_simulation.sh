#!/bin/bash
# ============================================
# run_simulation.sh - Sistema VarP Monte Carlo
# Fase 5.2: Scripts de automatización
# ============================================
#
# Script para ejecutar una simulación completa.
#
# Uso:
#   ./run_simulation.sh                                    # Simulación con defaults
#   ./run_simulation.sh -m modelos/mi_modelo.ini           # Especificar modelo
#   ./run_simulation.sh -n 10000                           # 10,000 escenarios
#   ./run_simulation.sh -c 5                               # 5 consumidores
#   ./run_simulation.sh -m modelo.ini -n 5000 -c 3         # Completo
#   ./run_simulation.sh --clean                            # Limpiar antes de ejecutar
#   ./run_simulation.sh --open-dashboard                   # Abrir dashboard automáticamente
#   ./run_simulation.sh --help                             # Mostrar ayuda

set -e  # Salir si hay error

# ============================================
# Colores para output
# ============================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ============================================
# Funciones auxiliares
# ============================================

print_header() {
    echo ""
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_progress() {
    echo -e "${CYAN}▶${NC} $1"
}

show_help() {
    cat << EOF
Sistema VarP Monte Carlo - Run Simulation Script

USO:
    ./run_simulation.sh [OPCIONES]

OPCIONES:
    -m, --modelo FILE       Archivo de modelo (.ini) a utilizar
    -n, --num NUM           Número de escenarios a simular
    -c, --consumers NUM     Número de consumidores paralelos
    --clean                 Limpiar colas antes de ejecutar
    --open-dashboard        Abrir dashboard en navegador
    --no-wait               No esperar a que termine la simulación
    --export-json FILE      Exportar resultados a JSON
    --export-csv FILE       Exportar resultados a CSV
    --help                  Mostrar esta ayuda

EJEMPLOS:
    # Simulación simple con defaults (1000 escenarios, 1 consumidor)
    ./run_simulation.sh

    # Simulación personalizada
    ./run_simulation.sh -m modelos/ejemplo_simple.ini -n 10000 -c 5

    # Limpiar colas y ejecutar
    ./run_simulation.sh --clean -n 5000

    # Ejecutar y abrir dashboard
    ./run_simulation.sh -n 1000 --open-dashboard

    # Simulación con exportación automática
    ./run_simulation.sh -n 5000 --export-json results.json --export-csv results.csv

NOTAS:
    - Si el sistema no está corriendo, se iniciará automáticamente
    - El script espera a que la simulación termine por defecto
    - Se puede monitorear el progreso en el dashboard (http://localhost:8050)
    - Los resultados quedan disponibles en el dashboard

EOF
    exit 0
}

# ============================================
# Cargar variables de entorno
# ============================================

# Cargar .env si existe
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# ============================================
# Valores por defecto
# ============================================

MODELO_FILE=${MODELO_FILE:-modelos/ejemplo_simple.ini}
NUM_ESCENARIOS=${DEFAULT_NUM_ESCENARIOS:-1000}
NUM_CONSUMERS=1
CLEAN_BEFORE=false
OPEN_DASHBOARD=false
NO_WAIT=false
EXPORT_JSON=""
EXPORT_CSV=""

RABBITMQ_HOST=${RABBITMQ_HOST:-localhost}
RABBITMQ_PORT=${RABBITMQ_PORT:-5672}
RABBITMQ_MGMT_PORT=${RABBITMQ_MGMT_PORT:-15672}
RABBITMQ_USER=${RABBITMQ_USER:-admin}
RABBITMQ_PASS=${RABBITMQ_PASS:-password}
RABBITMQ_VHOST=${RABBITMQ_VHOST:-/}
DASHBOARD_PORT=${DASHBOARD_PORT:-8050}

# ============================================
# Parsear argumentos
# ============================================

while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--modelo)
            MODELO_FILE="$2"
            shift 2
            ;;
        -n|--num)
            NUM_ESCENARIOS="$2"
            shift 2
            ;;
        -c|--consumers)
            NUM_CONSUMERS="$2"
            shift 2
            ;;
        --clean)
            CLEAN_BEFORE=true
            shift
            ;;
        --open-dashboard)
            OPEN_DASHBOARD=true
            shift
            ;;
        --no-wait)
            NO_WAIT=true
            shift
            ;;
        --export-json)
            EXPORT_JSON="$2"
            shift 2
            ;;
        --export-csv)
            EXPORT_CSV="$2"
            shift 2
            ;;
        --help|-h)
            show_help
            ;;
        *)
            print_error "Argumento desconocido: $1"
            echo "Usar --help para ver opciones"
            exit 1
            ;;
    esac
done

# ============================================
# Validaciones
# ============================================

print_header "CONFIGURACIÓN DE SIMULACIÓN"

# Verificar que el modelo existe
if [ ! -f "$MODELO_FILE" ]; then
    print_error "Archivo de modelo no encontrado: $MODELO_FILE"
    exit 1
fi

print_success "Modelo: $MODELO_FILE"
print_success "Escenarios: $NUM_ESCENARIOS"
print_success "Consumidores: $NUM_CONSUMERS"

# Validar número de escenarios
if [ "$NUM_ESCENARIOS" -lt 1 ]; then
    print_error "El número de escenarios debe ser mayor a 0"
    exit 1
fi

# Validar número de consumidores
if [ "$NUM_CONSUMERS" -lt 1 ]; then
    print_error "El número de consumidores debe ser mayor a 0"
    exit 1
fi

# ============================================
# Verificar que el sistema está corriendo
# ============================================

print_header "VERIFICANDO SISTEMA"

SYSTEM_RUNNING=false

if docker-compose ps | grep -q "Up"; then
    SYSTEM_RUNNING=true
    print_success "Sistema está corriendo"
else
    print_warning "Sistema no está corriendo"
    print_info "Iniciando sistema..."

    ./start.sh $NUM_CONSUMERS

    if [ $? -ne 0 ]; then
        print_error "Error iniciando sistema"
        exit 1
    fi

    SYSTEM_RUNNING=true
    print_success "Sistema iniciado"
fi

# ============================================
# Escalar consumidores si es necesario
# ============================================

CURRENT_CONSUMERS=$(docker-compose ps consumer | grep -c "Up" || echo "0")

if [ "$CURRENT_CONSUMERS" != "$NUM_CONSUMERS" ]; then
    print_info "Escalando consumidores de $CURRENT_CONSUMERS a $NUM_CONSUMERS..."
    docker-compose up -d --scale consumer=$NUM_CONSUMERS --no-recreate
    sleep 3
    print_success "Consumidores escalados a $NUM_CONSUMERS"
fi

# ============================================
# Limpiar colas si se solicitó
# ============================================

if [ "$CLEAN_BEFORE" = true ]; then
    print_header "LIMPIANDO COLAS"
    ./clean_queues.sh --force
    echo ""
fi

# ============================================
# Abrir dashboard si se solicitó
# ============================================

if [ "$OPEN_DASHBOARD" = true ]; then
    print_info "Abriendo dashboard en navegador..."

    # Intentar abrir en diferentes navegadores
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:$DASHBOARD_PORT" &> /dev/null &
    elif command -v open &> /dev/null; then
        open "http://localhost:$DASHBOARD_PORT" &> /dev/null &
    else
        print_warning "No se pudo abrir el navegador automáticamente"
        print_info "Abrir manualmente: http://localhost:$DASHBOARD_PORT"
    fi
fi

# ============================================
# Ejecutar simulación
# ============================================

print_header "EJECUTANDO SIMULACIÓN"

print_info "Iniciando productor con:"
echo "  - Modelo: $MODELO_FILE"
echo "  - Escenarios: $NUM_ESCENARIOS"
echo "  - Consumidores: $NUM_CONSUMERS"
echo ""

START_TIME=$(date +%s)

# Ejecutar productor en el contenedor
docker-compose run --rm \
    -e MODELO_FILE="$MODELO_FILE" \
    -e DEFAULT_NUM_ESCENARIOS="$NUM_ESCENARIOS" \
    producer \
    python -c "
from src.producer.producer import Producer
from src.common.rabbitmq_client import RabbitMQClient
import os

client = RabbitMQClient()
client.connect()
producer = Producer(client)

modelo = os.getenv('MODELO_FILE', 'modelos/ejemplo_simple.ini')
num_escenarios = int(os.getenv('DEFAULT_NUM_ESCENARIOS', '1000'))

print(f'Ejecutando simulación con {num_escenarios} escenarios...')
producer.ejecutar(modelo, num_escenarios)
print('Productor finalizado')
client.disconnect()
"

if [ $? -ne 0 ]; then
    print_error "Error ejecutando simulación"
    exit 1
fi

print_success "Productor completado - Escenarios enviados a la cola"

# ============================================
# Esperar a que se procesen todos los escenarios
# ============================================

if [ "$NO_WAIT" = false ]; then
    print_header "MONITOREANDO PROGRESO"

    print_info "Esperando a que se procesen todos los escenarios..."
    print_info "Dashboard disponible en: http://localhost:$DASHBOARD_PORT"
    echo ""

    VHOST_ENCODED=$(echo "$RABBITMQ_VHOST" | sed 's|/|%2F|g')
    QUEUE_ESCENARIOS=${QUEUE_ESCENARIOS:-cola_escenarios}
    QUEUE_RESULTADOS=${QUEUE_RESULTADOS:-cola_resultados}

    LAST_ESCENARIOS=-1
    LAST_RESULTADOS=-1
    STALLED_COUNT=0

    while true; do
        # Obtener tamaño de colas usando RabbitMQ API
        ESCENARIOS_SIZE=$(docker exec varp-rabbitmq \
            curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
            "http://localhost:15672/api/queues/$VHOST_ENCODED/$QUEUE_ESCENARIOS" 2>/dev/null \
            | grep -o '"messages":[0-9]*' | head -1 | cut -d':' -f2)

        RESULTADOS_SIZE=$(docker exec varp-rabbitmq \
            curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
            "http://localhost:15672/api/queues/$VHOST_ENCODED/$QUEUE_RESULTADOS" 2>/dev/null \
            | grep -o '"messages":[0-9]*' | head -1 | cut -d':' -f2)

        # Validar que obtuvimos valores
        ESCENARIOS_SIZE=${ESCENARIOS_SIZE:-0}
        RESULTADOS_SIZE=${RESULTADOS_SIZE:-0}

        # Calcular progreso aproximado
        PROCESSED=$((NUM_ESCENARIOS - ESCENARIOS_SIZE))
        if [ $PROCESSED -lt 0 ]; then
            PROCESSED=0
        fi

        PERCENT=0
        if [ $NUM_ESCENARIOS -gt 0 ]; then
            PERCENT=$((PROCESSED * 100 / NUM_ESCENARIOS))
        fi

        # Mostrar progreso
        echo -ne "\r  ${CYAN}▶${NC} Progreso: $PROCESSED/$NUM_ESCENARIOS ($PERCENT%) | Cola escenarios: $ESCENARIOS_SIZE | Cola resultados: $RESULTADOS_SIZE"

        # Verificar si terminó
        if [ "$ESCENARIOS_SIZE" -eq 0 ]; then
            # Si la cola de escenarios está vacía, dar tiempo a que se procesen los últimos
            sleep 2

            # Verificar de nuevo
            ESCENARIOS_SIZE=$(docker exec varp-rabbitmq \
                curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
                "http://localhost:15672/api/queues/$VHOST_ENCODED/$QUEUE_ESCENARIOS" 2>/dev/null \
                | grep -o '"messages":[0-9]*' | head -1 | cut -d':' -f2)
            ESCENARIOS_SIZE=${ESCENARIOS_SIZE:-0}

            if [ "$ESCENARIOS_SIZE" -eq 0 ]; then
                echo ""
                break
            fi
        fi

        # Detectar estancamiento
        if [ "$ESCENARIOS_SIZE" -eq "$LAST_ESCENARIOS" ] && [ "$RESULTADOS_SIZE" -eq "$LAST_RESULTADOS" ]; then
            STALLED_COUNT=$((STALLED_COUNT + 1))
            if [ $STALLED_COUNT -gt 30 ]; then
                echo ""
                print_warning "El procesamiento parece estar estancado"
                print_info "Verificar logs: docker-compose logs consumer"
                break
            fi
        else
            STALLED_COUNT=0
        fi

        LAST_ESCENARIOS=$ESCENARIOS_SIZE
        LAST_RESULTADOS=$RESULTADOS_SIZE

        sleep 2
    done

    echo ""
    print_success "Simulación completada"
fi

# ============================================
# Calcular tiempo de ejecución
# ============================================

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

print_header "SIMULACIÓN COMPLETADA"

print_success "Tiempo de ejecución: ${MINUTES}m ${SECONDS}s"
print_success "Escenarios procesados: $NUM_ESCENARIOS"
print_success "Consumidores utilizados: $NUM_CONSUMERS"

if [ $DURATION -gt 0 ]; then
    THROUGHPUT=$((NUM_ESCENARIOS / DURATION))
    print_success "Throughput: ~$THROUGHPUT escenarios/segundo"
fi

echo ""
print_info "Dashboard disponible en:"
echo "  ${YELLOW}http://localhost:$DASHBOARD_PORT${NC}"
echo ""
print_info "RabbitMQ Management UI:"
echo "  ${YELLOW}http://localhost:$RABBITMQ_MGMT_PORT${NC}"
echo ""

# ============================================
# Exportar resultados si se solicitó
# ============================================

if [ -n "$EXPORT_JSON" ] || [ -n "$EXPORT_CSV" ]; then
    print_header "EXPORTANDO RESULTADOS"

    # Dar tiempo a que el dashboard procese los últimos resultados
    sleep 3

    if [ -n "$EXPORT_JSON" ]; then
        print_info "Exportando a JSON: $EXPORT_JSON"

        # Usar la API del dashboard o ejecutar script Python
        docker-compose exec -T dashboard python -c "
from src.dashboard.data_manager import DataManager
from src.common.rabbitmq_client import RabbitMQClient
import json

client = RabbitMQClient()
client.connect()
dm = DataManager(client)

# Dar tiempo a cargar datos
import time
time.sleep(2)

json_str = dm.export_resultados_json()
print(json_str)
" > "$EXPORT_JSON" 2>/dev/null

        if [ $? -eq 0 ]; then
            print_success "Exportado a JSON: $EXPORT_JSON"
        else
            print_warning "No se pudo exportar a JSON automáticamente"
            print_info "Usar el botón de descarga en el dashboard"
        fi
    fi

    if [ -n "$EXPORT_CSV" ]; then
        print_info "Exportando a CSV: $EXPORT_CSV"

        docker-compose exec -T dashboard python -c "
from src.dashboard.data_manager import DataManager
from src.common.rabbitmq_client import RabbitMQClient

client = RabbitMQClient()
client.connect()
dm = DataManager(client)

# Dar tiempo a cargar datos
import time
time.sleep(2)

csv_str = dm.export_resultados_csv(include_metadata=True)
print(csv_str)
" > "$EXPORT_CSV" 2>/dev/null

        if [ $? -eq 0 ]; then
            print_success "Exportado a CSV: $EXPORT_CSV"
        else
            print_warning "No se pudo exportar a CSV automáticamente"
            print_info "Usar el botón de descarga en el dashboard"
        fi
    fi

    echo ""
fi

# ============================================
# Mostrar siguiente paso
# ============================================

print_info "Próximos pasos:"
echo "  - Ver resultados en dashboard: http://localhost:$DASHBOARD_PORT"
echo "  - Exportar resultados desde el dashboard"
echo "  - Ver logs: ${YELLOW}docker-compose logs -f${NC}"
echo "  - Detener sistema: ${YELLOW}./stop.sh${NC}"
echo ""
