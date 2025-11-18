#!/bin/bash
# ============================================
# clean_queues.sh - Sistema VarP Monte Carlo
# Fase 5.2: Scripts de automatización
# ============================================
#
# Script para purgar colas de RabbitMQ.
#
# Uso:
#   ./clean_queues.sh                # Purgar todas las colas
#   ./clean_queues.sh --escenarios   # Purgar solo cola_escenarios
#   ./clean_queues.sh --resultados   # Purgar solo cola_resultados
#   ./clean_queues.sh --stats        # Purgar solo colas de stats
#   ./clean_queues.sh --all          # Purgar todas (mismo que sin args)
#   ./clean_queues.sh --force        # No pedir confirmación
#   ./clean_queues.sh --help         # Mostrar ayuda

set -e  # Salir si hay error

# ============================================
# Colores para output
# ============================================
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
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

show_help() {
    cat << EOF
Sistema VarP Monte Carlo - Clean Queues Script

USO:
    ./clean_queues.sh [OPCIONES]

OPCIONES:
    --all           Purgar todas las colas (default)
    --escenarios    Purgar solo cola_escenarios
    --resultados    Purgar solo cola_resultados
    --stats         Purgar solo colas de estadísticas
    --modelo        Purgar solo cola_modelo
    --dlq           Purgar solo Dead Letter Queues
    --force         No pedir confirmación
    --help          Mostrar esta ayuda

EJEMPLOS:
    ./clean_queues.sh                    # Purgar todas las colas
    ./clean_queues.sh --escenarios       # Solo purgar escenarios
    ./clean_queues.sh --stats --force    # Purgar stats sin confirmación
    ./clean_queues.sh --all              # Purgar todas las colas

NOTAS:
    - Requiere que RabbitMQ esté corriendo (docker-compose up)
    - Las colas se vacían pero no se eliminan
    - Los mensajes purgados no se pueden recuperar
    - Se muestra el tamaño de cada cola antes de purgar

EOF
    exit 0
}

confirm() {
    read -p "$1 [y/N]: " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        return 1
    fi
    return 0
}

# ============================================
# Cargar variables de entorno
# ============================================

# Cargar .env si existe
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Valores por defecto
RABBITMQ_USER=${RABBITMQ_USER:-admin}
RABBITMQ_PASS=${RABBITMQ_PASS:-password}
RABBITMQ_VHOST=${RABBITMQ_VHOST:-/}
RABBITMQ_CONTAINER=${RABBITMQ_CONTAINER:-varp-rabbitmq}

# Nombres de colas
QUEUE_MODELO=${QUEUE_MODELO:-cola_modelo}
QUEUE_ESCENARIOS=${QUEUE_ESCENARIOS:-cola_escenarios}
QUEUE_RESULTADOS=${QUEUE_RESULTADOS:-cola_resultados}
QUEUE_STATS_PRODUCTOR=${QUEUE_STATS_PRODUCTOR:-cola_stats_productor}
QUEUE_STATS_CONSUMIDORES=${QUEUE_STATS_CONSUMIDORES:-cola_stats_consumidores}
QUEUE_DLQ_ESCENARIOS=${QUEUE_DLQ_ESCENARIOS:-cola_dlq_escenarios}
QUEUE_DLQ_RESULTADOS=${QUEUE_DLQ_RESULTADOS:-cola_dlq_resultados}

# ============================================
# Parsear argumentos
# ============================================

PURGE_ALL=false
PURGE_ESCENARIOS=false
PURGE_RESULTADOS=false
PURGE_STATS=false
PURGE_MODELO=false
PURGE_DLQ=false
FORCE=false

# Si no hay argumentos, purgar todo
if [ $# -eq 0 ]; then
    PURGE_ALL=true
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            PURGE_ALL=true
            shift
            ;;
        --escenarios)
            PURGE_ESCENARIOS=true
            shift
            ;;
        --resultados)
            PURGE_RESULTADOS=true
            shift
            ;;
        --stats)
            PURGE_STATS=true
            shift
            ;;
        --modelo)
            PURGE_MODELO=true
            shift
            ;;
        --dlq)
            PURGE_DLQ=true
            shift
            ;;
        --force)
            FORCE=true
            shift
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

print_header "LIMPIEZA DE COLAS RABBITMQ"

# Verificar que docker está instalado
if ! command -v docker &> /dev/null; then
    print_error "docker no está instalado"
    exit 1
fi

# Verificar que el contenedor de RabbitMQ está corriendo
if ! docker ps | grep -q "$RABBITMQ_CONTAINER"; then
    print_error "RabbitMQ no está corriendo"
    print_info "Iniciar con: ./start.sh"
    exit 1
fi

# ============================================
# Funciones de RabbitMQ
# ============================================

get_queue_size() {
    local queue_name=$1
    local vhost_encoded=$(echo "$RABBITMQ_VHOST" | sed 's|/|%2F|g')

    local response=$(docker exec $RABBITMQ_CONTAINER \
        curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
        "http://localhost:15672/api/queues/$vhost_encoded/$queue_name" 2>/dev/null)

    if [ -z "$response" ]; then
        echo "0"
        return
    fi

    # Extraer el campo 'messages' del JSON
    echo "$response" | grep -o '"messages":[0-9]*' | head -1 | cut -d':' -f2
}

purge_queue() {
    local queue_name=$1
    local vhost_encoded=$(echo "$RABBITMQ_VHOST" | sed 's|/|%2F|g')

    # Obtener tamaño antes de purgar
    local size_before=$(get_queue_size "$queue_name")

    if [ -z "$size_before" ] || [ "$size_before" = "0" ]; then
        print_info "Cola '$queue_name': vacía (0 mensajes)"
        return 0
    fi

    print_warning "Cola '$queue_name': $size_before mensajes"

    # Purgar la cola
    docker exec $RABBITMQ_CONTAINER \
        curl -s -u "$RABBITMQ_USER:$RABBITMQ_PASS" \
        -X DELETE \
        "http://localhost:15672/api/queues/$vhost_encoded/$queue_name/contents" \
        > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        print_success "Cola '$queue_name' purgada ($size_before mensajes eliminados)"
        return 0
    else
        print_error "Error purgando cola '$queue_name'"
        return 1
    fi
}

# ============================================
# Mostrar estado actual
# ============================================

print_header "ESTADO ACTUAL DE COLAS"

ALL_QUEUES=(
    "$QUEUE_MODELO"
    "$QUEUE_ESCENARIOS"
    "$QUEUE_RESULTADOS"
    "$QUEUE_STATS_PRODUCTOR"
    "$QUEUE_STATS_CONSUMIDORES"
    "$QUEUE_DLQ_ESCENARIOS"
    "$QUEUE_DLQ_RESULTADOS"
)

TOTAL_MESSAGES=0

for queue in "${ALL_QUEUES[@]}"; do
    size=$(get_queue_size "$queue")
    if [ -n "$size" ] && [ "$size" != "0" ]; then
        echo -e "  ${YELLOW}$queue${NC}: $size mensajes"
        TOTAL_MESSAGES=$((TOTAL_MESSAGES + size))
    else
        echo -e "  $queue: 0 mensajes"
    fi
done

echo ""
print_info "Total de mensajes: $TOTAL_MESSAGES"
echo ""

if [ "$TOTAL_MESSAGES" -eq 0 ]; then
    print_success "Todas las colas están vacías"
    exit 0
fi

# ============================================
# Confirmar operación
# ============================================

if [ "$FORCE" = false ]; then
    print_warning "Esta acción eliminará mensajes de las colas"
    echo ""

    if ! confirm "¿Continuar con la purga?"; then
        print_info "Operación cancelada"
        exit 0
    fi
fi

# ============================================
# Purgar colas según opciones
# ============================================

print_header "PURGANDO COLAS"

PURGED_COUNT=0
ERROR_COUNT=0

if [ "$PURGE_ALL" = true ]; then
    # Purgar todas las colas
    for queue in "${ALL_QUEUES[@]}"; do
        purge_queue "$queue"
        if [ $? -eq 0 ]; then
            PURGED_COUNT=$((PURGED_COUNT + 1))
        else
            ERROR_COUNT=$((ERROR_COUNT + 1))
        fi
    done
else
    # Purgar selectivamente
    if [ "$PURGE_MODELO" = true ]; then
        purge_queue "$QUEUE_MODELO"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))
    fi

    if [ "$PURGE_ESCENARIOS" = true ]; then
        purge_queue "$QUEUE_ESCENARIOS"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))
    fi

    if [ "$PURGE_RESULTADOS" = true ]; then
        purge_queue "$QUEUE_RESULTADOS"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))
    fi

    if [ "$PURGE_STATS" = true ]; then
        purge_queue "$QUEUE_STATS_PRODUCTOR"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))

        purge_queue "$QUEUE_STATS_CONSUMIDORES"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))
    fi

    if [ "$PURGE_DLQ" = true ]; then
        purge_queue "$QUEUE_DLQ_ESCENARIOS"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))

        purge_queue "$QUEUE_DLQ_RESULTADOS"
        [ $? -eq 0 ] && PURGED_COUNT=$((PURGED_COUNT + 1)) || ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
fi

# ============================================
# Estado final
# ============================================

print_header "PURGA COMPLETADA"

if [ "$ERROR_COUNT" -eq 0 ]; then
    print_success "Todas las colas purgadas exitosamente"
else
    print_warning "Se purgaron $PURGED_COUNT colas con $ERROR_COUNT errores"
fi

echo ""
print_info "Estado final de colas:"
echo ""

for queue in "${ALL_QUEUES[@]}"; do
    size=$(get_queue_size "$queue")
    if [ -n "$size" ] && [ "$size" != "0" ]; then
        echo -e "  ${YELLOW}$queue${NC}: $size mensajes"
    else
        echo -e "  ${GREEN}$queue${NC}: 0 mensajes"
    fi
done

echo ""
print_info "Para ver el estado en RabbitMQ Management UI:"
echo "  ${YELLOW}http://localhost:15672${NC}"
echo ""
