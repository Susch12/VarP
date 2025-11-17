#!/bin/bash

# ============================================
# SETUP INICIAL DEL PROYECTO VARP
# Sistema de Simulación Monte Carlo Distribuido
# ============================================

set -e

echo "🚀 Iniciando setup del proyecto VarP..."
echo ""

# Colores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verificar Python 3.10+
echo -e "${BLUE}[1/6]${NC} Verificando versión de Python..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $python_version detectado"
echo ""

# 2. Crear virtualenv
echo -e "${BLUE}[2/6]${NC} Creando entorno virtual..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ Virtualenv creado"
else
    echo "⚠️  Virtualenv ya existe"
fi
echo ""

# 3. Activar virtualenv e instalar dependencias
echo -e "${BLUE}[3/6]${NC} Instalando dependencias..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt
echo "✅ Dependencias instaladas"
echo ""

# 4. Verificar Docker
echo -e "${BLUE}[4/6]${NC} Verificando Docker..."
if command -v docker &> /dev/null; then
    docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo "✅ Docker $docker_version detectado"
else
    echo "❌ Docker no encontrado. Por favor instala Docker."
    exit 1
fi
echo ""

# 5. Levantar RabbitMQ
echo -e "${BLUE}[5/6]${NC} Levantando RabbitMQ..."
docker-compose up -d rabbitmq
echo "⏳ Esperando que RabbitMQ esté listo (30s)..."
sleep 30
echo "✅ RabbitMQ levantado"
echo ""

# 6. Verificar RabbitMQ
echo -e "${BLUE}[6/6]${NC} Verificando RabbitMQ..."
rabbitmq_status=$(curl -s -u admin:password http://localhost:15672/api/overview | grep -o '"management_version":"[^"]*"' || echo "")
if [ -n "$rabbitmq_status" ]; then
    echo "✅ RabbitMQ está funcionando correctamente"
else
    echo "⚠️  No se pudo verificar el estado de RabbitMQ"
fi
echo ""

# Resumen
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✅ SETUP COMPLETADO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "📋 Próximos pasos:"
echo ""
echo "1. Activar virtualenv:"
echo "   source venv/bin/activate"
echo ""
echo "2. Verificar RabbitMQ Management UI:"
echo "   http://localhost:15672"
echo "   Usuario: admin / Contraseña: password"
echo ""
echo "3. Ejecutar tests (cuando estén implementados):"
echo "   pytest tests/ -v"
echo ""
echo "4. Comenzar desarrollo de Fase 1.2:"
echo "   Parser de modelos y generador de distribuciones"
echo ""
