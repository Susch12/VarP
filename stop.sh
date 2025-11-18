#!/bin/bash
# ============================================
# stop.sh - Sistema VarP Monte Carlo
# Fase 5.2: Scripts de automatización
# ============================================
#
# Script para detener y limpiar el sistema VarP.
#
# Uso:
#   ./stop.sh                # Detener servicios
#   ./stop.sh --clean        # Detener y limpiar volumes
#   ./stop.sh --full-clean   # Detener, limpiar volumes e imágenes
#   ./stop.sh --help         # Mostrar ayuda

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
Sistema VarP Monte Carlo - Stop Script

USO:
    ./stop.sh [OPCIONES]

OPCIONES:
    --clean         Detener servicios y eliminar volumes persistentes
    --full-clean    Detener, eliminar volumes e imágenes de Docker
    --force         No pedir confirmación
    --help          Mostrar esta ayuda

EJEMPLOS:
    ./stop.sh                 # Detener servicios (mantener volumes)
    ./stop.sh --clean         # Detener y limpiar volumes
    ./stop.sh --full-clean    # Limpieza completa
    ./stop.sh --clean --force # Limpiar sin confirmación

NOTAS:
    - Sin opciones: Solo detiene los contenedores (volumes se mantienen)
    - --clean: Elimina volumes (se pierde historial de RabbitMQ)
    - --full-clean: Elimina también las imágenes de Docker

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
# Parsear argumentos
# ============================================

CLEAN_VOLUMES=false
FULL_CLEAN=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --clean)
            CLEAN_VOLUMES=true
            shift
            ;;
        --full-clean)
            CLEAN_VOLUMES=true
            FULL_CLEAN=true
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

print_header "DETENIENDO SISTEMA VarP"

# Verificar que docker-compose está instalado
if ! command -v docker-compose &> /dev/null; then
    print_error "docker-compose no está instalado"
    exit 1
fi

# ============================================
# Confirmar acciones destructivas
# ============================================

if [ "$CLEAN_VOLUMES" = true ] && [ "$FORCE" = false ]; then
    print_warning "Esta acción eliminará volumes persistentes"
    print_info "Se perderá:"
    echo "  - Datos de RabbitMQ"
    echo "  - Logs de RabbitMQ"
    echo ""

    if ! confirm "¿Continuar?"; then
        print_info "Operación cancelada"
        exit 0
    fi
fi

if [ "$FULL_CLEAN" = true ] && [ "$FORCE" = false ]; then
    print_warning "Esta acción eliminará también las imágenes de Docker"
    print_info "Será necesario reconstruir con: ./start.sh --build"
    echo ""

    if ! confirm "¿Continuar?"; then
        print_info "Operación cancelada"
        exit 0
    fi
fi

# ============================================
# Detener servicios
# ============================================

print_header "DETENIENDO SERVICIOS"

print_info "Deteniendo contenedores..."

if [ "$CLEAN_VOLUMES" = true ]; then
    # Detener y eliminar volumes
    docker-compose down -v
    print_success "Servicios detenidos y volumes eliminados"
else
    # Solo detener
    docker-compose down
    print_success "Servicios detenidos (volumes preservados)"
fi

# ============================================
# Limpiar imágenes (si se solicitó)
# ============================================

if [ "$FULL_CLEAN" = true ]; then
    print_header "LIMPIANDO IMÁGENES"

    print_info "Eliminando imágenes de VarP..."

    # Eliminar imágenes del proyecto
    docker-compose down --rmi local

    print_success "Imágenes eliminadas"
fi

# ============================================
# Estado final
# ============================================

print_header "LIMPIEZA COMPLETADA"

# Verificar que no quedan contenedores corriendo
RUNNING_CONTAINERS=$(docker-compose ps -q 2>/dev/null | wc -l)

if [ "$RUNNING_CONTAINERS" -eq 0 ]; then
    print_success "No hay contenedores corriendo"
else
    print_warning "Hay $RUNNING_CONTAINERS contenedor(es) aún corriendo"
    docker-compose ps
fi

# Mostrar volumes restantes
if [ "$CLEAN_VOLUMES" = false ]; then
    print_info "Volumes persistentes (no eliminados):"
    docker volume ls | grep varp || echo "  Ninguno"
fi

echo ""
print_info "Sistema detenido exitosamente"
echo ""
print_info "Para reiniciar:"
echo "  ${YELLOW}./start.sh${NC}"
echo ""

if [ "$FULL_CLEAN" = true ]; then
    print_warning "Imágenes eliminadas. Próximo inicio requerirá build:"
    echo "  ${YELLOW}./start.sh --build${NC}"
    echo ""
fi
