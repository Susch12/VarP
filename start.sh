#!/bin/bash
# ============================================
# start.sh - Sistema VarP Monte Carlo
# Fase 5.2: Scripts de automatización
# ============================================
#
# Script para levantar todo el sistema VarP con Docker Compose.
#
# Uso:
#   ./start.sh                    # Iniciar con 1 consumidor
#   ./start.sh 5                  # Iniciar con 5 consumidores
#   ./start.sh --build            # Reconstruir imágenes y iniciar
#   ./start.sh --help             # Mostrar ayuda

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
Sistema VarP Monte Carlo - Start Script

USO:
    ./start.sh [OPCIONES] [CONSUMIDORES]

OPCIONES:
    --build         Reconstruir imágenes de Docker antes de iniciar
    --dev           Modo desarrollo (monta código fuente)
    --help          Mostrar esta ayuda

ARGUMENTOS:
    CONSUMIDORES    Número de consumidores a iniciar (default: 1)

EJEMPLOS:
    ./start.sh                    # Iniciar con 1 consumidor
    ./start.sh 5                  # Iniciar con 5 consumidores
    ./start.sh --build            # Reconstruir e iniciar
    ./start.sh --build 3          # Reconstruir e iniciar con 3 consumidores

URLS:
    Dashboard:        http://localhost:8050
    RabbitMQ Admin:   http://localhost:15672 (admin/password)

EOF
    exit 0
}

# ============================================
# Parsear argumentos
# ============================================

BUILD=false
DEV_MODE=false
NUM_CONSUMERS=1

while [[ $# -gt 0 ]]; do
    case $1 in
        --build)
            BUILD=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        --help|-h)
            show_help
            ;;
        [0-9]*)
            NUM_CONSUMERS=$1
            shift
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

print_header "INICIANDO SISTEMA VarP"

# Verificar que docker está instalado
if ! command -v docker &> /dev/null; then
    print_error "Docker no está instalado"
    echo "Instalar desde: https://docs.docker.com/get-docker/"
    exit 1
fi

print_success "Docker encontrado: $(docker --version)"

# Verificar que docker-compose está instalado
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose no está instalado"
    echo "Instalar desde: https://docs.docker.com/compose/install/"
    exit 1
fi

print_success "docker-compose encontrado: $(docker-compose --version)"

# Verificar que .env existe
if [ ! -f .env ]; then
    print_warning "Archivo .env no encontrado"
    print_info "Copiando .env.example a .env..."
    cp .env.example .env
    print_success ".env creado desde .env.example"
fi

# Verificar que docker daemon está corriendo
if ! docker info &> /dev/null; then
    print_error "Docker daemon no está corriendo"
    echo "Iniciar Docker Desktop o el servicio de Docker"
    exit 1
fi

print_success "Docker daemon corriendo"

# ============================================
# Build (si se solicitó)
# ============================================

if [ "$BUILD" = true ]; then
    print_header "CONSTRUYENDO IMÁGENES"

    print_info "Construyendo imágenes de Docker..."
    docker-compose build

    print_success "Imágenes construidas exitosamente"
fi

# ============================================
# Iniciar servicios
# ============================================

print_header "INICIANDO SERVICIOS"

print_info "Iniciando servicios con Docker Compose..."

if [ "$NUM_CONSUMERS" -eq 1 ]; then
    # 1 consumidor (default)
    docker-compose up -d
else
    # Múltiples consumidores
    print_info "Escalando a $NUM_CONSUMERS consumidores..."
    docker-compose up -d --scale consumer=$NUM_CONSUMERS
fi

print_success "Servicios iniciados"

# ============================================
# Esperar a que servicios estén listos
# ============================================

print_header "ESPERANDO SERVICIOS"

print_info "Esperando a RabbitMQ..."
sleep 5

# Verificar que RabbitMQ está corriendo
RABBITMQ_STATUS=$(docker-compose ps -q rabbitmq | xargs docker inspect -f '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")

if [ "$RABBITMQ_STATUS" != "healthy" ]; then
    print_warning "RabbitMQ aún no está listo (estado: $RABBITMQ_STATUS)"
    print_info "Esperando hasta 60 segundos..."

    for i in {1..12}; do
        sleep 5
        RABBITMQ_STATUS=$(docker-compose ps -q rabbitmq | xargs docker inspect -f '{{.State.Health.Status}}' 2>/dev/null || echo "unknown")

        if [ "$RABBITMQ_STATUS" = "healthy" ]; then
            print_success "RabbitMQ está listo"
            break
        fi

        echo -n "."
    done

    if [ "$RABBITMQ_STATUS" != "healthy" ]; then
        print_error "RabbitMQ no está listo después de 60s"
        print_info "Ver logs con: docker-compose logs rabbitmq"
        exit 1
    fi
else
    print_success "RabbitMQ está listo"
fi

# ============================================
# Verificar estado de servicios
# ============================================

print_header "ESTADO DE SERVICIOS"

docker-compose ps

# ============================================
# Información de acceso
# ============================================

print_header "SISTEMA INICIADO"

print_success "Sistema VarP corriendo exitosamente"
echo ""
print_info "URLs de acceso:"
echo "  Dashboard:      ${GREEN}http://localhost:8050${NC}"
echo "  RabbitMQ Admin: ${GREEN}http://localhost:15672${NC}"
echo "    Usuario:      admin"
echo "    Password:     password"
echo ""
print_info "Servicios corriendo:"
echo "  - RabbitMQ:     1 instancia"
echo "  - Producer:     1 instancia"
echo "  - Consumer:     $NUM_CONSUMERS instancia(s)"
echo "  - Dashboard:    1 instancia"
echo ""
print_info "Comandos útiles:"
echo "  Ver logs:       ${YELLOW}docker-compose logs -f${NC}"
echo "  Ver dashboard:  ${YELLOW}docker-compose logs -f dashboard${NC}"
echo "  Detener:        ${YELLOW}./stop.sh${NC}"
echo "  Limpiar colas:  ${YELLOW}./clean_queues.sh${NC}"
echo ""
