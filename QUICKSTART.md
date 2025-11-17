# 🚀 Quick Start - VarP

Sistema de Simulación Monte Carlo Distribuido

## Setup Inicial (5 minutos)

### Opción 1: Script Automático (Recomendado)

```bash
./setup.sh
```

### Opción 2: Manual

```bash
# 1. Crear virtualenv
python3 -m venv venv
source venv/bin/activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Levantar RabbitMQ
docker-compose up -d rabbitmq

# 4. Verificar RabbitMQ (esperar 30s)
curl -u admin:password http://localhost:15672/api/overview
```

## Verificar Instalación

### RabbitMQ Management UI
- **URL**: http://localhost:15672
- **Usuario**: admin
- **Contraseña**: password

### Estado del Sistema
```bash
# Ver logs de RabbitMQ
docker-compose logs -f rabbitmq

# Detener RabbitMQ
docker-compose down

# Reiniciar RabbitMQ
docker-compose restart rabbitmq
```

## Estructura del Proyecto

```
VarP/
├── src/
│   ├── producer/       # Generador de escenarios
│   ├── consumer/       # Ejecutor de modelos
│   ├── dashboard/      # Visualización
│   ├── common/         # Código compartido
│   └── utils/          # Utilidades
├── modelos/            # Archivos de modelo (.ini)
├── tests/              # Tests unitarios
├── docker/             # Dockerfiles
└── docker-compose.yml  # Orquestación
```

## Próximos Pasos

### Fase 1.2: Parser y Distribuciones
- [ ] Implementar parser de archivos .ini
- [ ] Implementar generador de distribuciones
- [ ] Tests unitarios

### Fase 1.3: Productor Básico
- [ ] Conexión a RabbitMQ
- [ ] Publicación de modelo
- [ ] Generación de escenarios

### Fase 1.4: Consumidor Básico
- [ ] Lectura de modelo
- [ ] Evaluador de expresiones AST
- [ ] Ejecución y resultados

## Comandos Útiles

### Desarrollo
```bash
# Activar virtualenv
source venv/bin/activate

# Ejecutar tests
pytest tests/ -v

# Formatear código
black src/

# Linting
flake8 src/
```

### Docker
```bash
# Ver servicios
docker-compose ps

# Logs
docker-compose logs -f

# Limpiar todo
docker-compose down -v
```

## Ejemplo de Modelo

Ver `modelos/ejemplo_simple.ini` para un ejemplo básico de suma de variables normales.

## Ayuda

- **README principal**: Ver [README.md](README.md) para documentación completa
- **Issues**: Reportar problemas en GitHub
- **Logs**: Revisar `docker-compose logs rabbitmq`
