# Fase 3.1: Ejecutor de Código Python Seguro - COMPLETADO ✅

## Resumen

Se ha implementado un **ejecutor de código Python seguro** usando RestrictedPython que permite ejecutar código Python arbitrario de forma controlada y segura. El sistema incluye timeout configurable, whitelist de imports, namespace seguro y protección contra código malicioso.

## Nuevas Funcionalidades

### 1. PythonExecutor con RestrictedPython

Ejecutor seguro de código Python con las siguientes características:
- Compilación con `RestrictedPython` para bloquear operaciones peligrosas
- Timeout configurable (default: 30 segundos)
- Whitelist estricta de módulos permitidos
- Namespace seguro con `safe_globals`
- Guards personalizados para iteraciones y operaciones in-place

### 2. Whitelist de Imports

Módulos permitidos:
- **math**: Funciones matemáticas estándar de Python
- **numpy** (como `np`): Operaciones numéricas avanzadas

Funciones numpy disponibles globalmente (sin import):
- **Trigonométricas**: `sin`, `cos`, `tan`, `arcsin`, `arccos`, `arctan`, `arctan2`
- **Hiperbólicas**: `sinh`, `cosh`, `tanh`
- **Exponenciales**: `exp`, `log`, `log10`, `log2`, `sqrt`
- **Redondeo**: `floor`, `ceil`, `round`
- **Agregación**: `sum`, `mean`, `median`, `std`, `var`, `min`, `max`
- **Potencias**: `power`, `square`
- **Otros**: `abs`, `sign`, `clip`

### 3. Características de Seguridad

**Bloqueados automáticamente**:
- ❌ Imports no autorizados (os, sys, subprocess, socket, pathlib, etc.)
- ❌ Operaciones de archivo (`open`, lectura/escritura)
- ❌ Ejecución de comandos del sistema
- ❌ Acceso a red (sockets)
- ❌ Funciones peligrosas (`eval`, `exec`)
- ❌ Acceso directo a `__builtins__`
- ❌ Variables que comienzan con `_` (como `__import__`)

**Permitidos**:
- ✅ Operaciones matemáticas y numéricas
- ✅ Estructuras de control (if, for, while)
- ✅ Listas, tuplas, dicts, sets
- ✅ Funciones definidas por el usuario
- ✅ Comprehensions
- ✅ Operadores in-place (+=, -=, etc.)

### 4. Timeout Configurable

- Previene loops infinitos y código muy lento
- Default: 30 segundos
- Configurable por instancia de executor
- Usa threading para implementación multiplataforma
- Lanza `TimeoutException` si se excede el límite

### 5. ModelParser Extendido

El parser ahora soporta `tipo='codigo'` además de `tipo='expresion'`:

```ini
[FUNCION]
tipo = codigo
codigo =
    # Código Python multilínea
    # Debe definir variable 'resultado'

    import math
    distancia = math.sqrt(x**2 + y**2)
    angulo = math.atan2(y, x)
    resultado = distancia * angulo
```

Características del parsing:
- Soporte para código multilínea
- Preservación de indentación relativa
- Dedentación automática de indentación común
- Validación de sintaxis en tiempo de parse

### 6. Consumer Actualizado

El consumer ahora maneja dos tipos de funciones:

**tipo='expresion'** (Fase 1):
```python
# Usa SafeExpressionEvaluator
resultado = evaluator.evaluate("x + y", {'x': 1, 'y': 2})
```

**tipo='codigo'** (Fase 3.1):
```python
# Usa PythonExecutor con timeout de 30s
resultado = python_executor.execute(codigo, variables={'x': 1, 'y': 2})
```

Manejo de excepciones:
- `TimeoutException`: NACK sin requeue (código muy lento)
- `SecurityException`: NACK sin requeue (código no seguro)
- `ExpressionEvaluationError`: NACK sin requeue
- Otras excepciones: NACK con requeue

## Arquitectura

### Flujo de Ejecución de Código

```
┌─────────────────────────────────────────────────────────────┐
│                   ModelParser                                │
│                                                             │
│  Archivo .ini con tipo='codigo'                             │
│  → _parse_funcion()                                         │
│  → _parse_codigo_multilinea()                               │
│  → _dedent_code()                                           │
│  → Modelo.codigo                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ JSON via RabbitMQ
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Consumer._cargar_modelo()                       │
│                                                             │
│  if tipo_funcion == 'codigo':                               │
│      self.python_executor = PythonExecutor(timeout=30.0)    │
│      self.codigo = modelo_msg['funcion']['codigo']          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Por cada escenario
                     ▼
┌─────────────────────────────────────────────────────────────┐
│            Consumer._ejecutar_modelo()                       │
│                                                             │
│  if tipo_funcion == 'codigo':                               │
│      resultado = python_executor.execute(                   │
│          code=self.codigo,                                  │
│          variables=escenario['valores'],                    │
│          result_var='resultado'                             │
│      )                                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           PythonExecutor.execute()                           │
│                                                             │
│  1. Preparar namespace seguro (safe_globals)                │
│  2. Agregar guards (_getiter_, _inplacevar_)                │
│  3. Inyectar variables del usuario                          │
│  4. Compilar con compile_restricted_exec                    │
│  5. Ejecutar en thread con timeout                          │
│  6. Extraer variable 'resultado'                            │
│  7. Retornar resultado o lanzar excepción                   │
└─────────────────────────────────────────────────────────────┘
```

## Cambios en Archivos

### `src/common/python_executor.py` (NUEVO)

**Clases principales**:
```python
class PythonExecutor:
    """Ejecutor de código Python seguro."""

    ALLOWED_IMPORTS = {'math': math, 'np': np, 'numpy': np}
    ALLOWED_NUMPY_FUNCS = {
        'sqrt': np.sqrt, 'sin': np.sin, 'cos': np.cos, ...
    }

    def __init__(self, timeout: float = 30.0)
    def compile_code(self, code: str) -> Any
    def execute(self, code: str, variables: Dict) -> Any
    def execute_expression(self, expression: str, variables: Dict) -> Any
```

**Excepciones**:
```python
class TimeoutException(Exception): pass
class SecurityException(Exception): pass
```

**Funciones de conveniencia**:
```python
safe_execute(code, variables, timeout=30.0)
safe_eval(expression, variables, timeout=30.0)
timeout_decorator(seconds=30.0)  # Decorador
```

**Guards personalizados**:
```python
# _getiter_: Permite iteración sobre tipos seguros
def safe_iter(obj):
    if isinstance(obj, (list, tuple, range, str, dict, set, np.ndarray)):
        return iter(obj)
    raise TypeError(...)

# _inplacevar_: Permite operaciones in-place (+=, -=, etc.)
def inplacevar(op, x, y):
    return op(x, y)
```

### `src/common/model_parser.py` (MODIFICADO)

**Nuevos métodos**:
```python
def _parse_codigo_multilinea(self) -> str:
    """
    Parsea código Python multilínea de la sección [FUNCION].
    Lee líneas después de 'codigo =' hasta el final de la sección.
    """

def _dedent_code(self, code: str) -> str:
    """
    Remueve indentación común preservando indentación relativa.
    """
```

**Modificado**:
```python
def _parse_funcion(self) -> Dict[str, Any]:
    if tipo == 'expresion':
        # ... código existente
    elif tipo == 'codigo':
        codigo = self._parse_codigo_multilinea()
        if not codigo:
            raise ModelParserError("Código no puede estar vacío")
        funcion['codigo'] = codigo
```

### `src/consumer/consumer.py` (MODIFICADO)

**Nuevas importaciones**:
```python
from src.common.python_executor import (
    PythonExecutor,
    TimeoutException,
    SecurityException
)
```

**Nuevos atributos**:
```python
self.tipo_funcion: Optional[str] = None
self.python_executor: Optional[PythonExecutor] = None
self.codigo: Optional[str] = None
```

**Método `_cargar_modelo()` extendido**:
```python
if self.tipo_funcion == 'expresion':
    self.expresion = self.modelo_msg['funcion']['expresion']
    self.evaluator = SafeExpressionEvaluator()
elif self.tipo_funcion == 'codigo':
    self.codigo = self.modelo_msg['funcion']['codigo']
    self.python_executor = PythonExecutor(timeout=30.0)
```

**Método `_ejecutar_modelo()` extendido**:
```python
if self.tipo_funcion == 'expresion':
    resultado = self.evaluator.evaluate(self.expresion, valores)
elif self.tipo_funcion == 'codigo':
    resultado = self.python_executor.execute(
        code=self.codigo,
        variables=valores,
        result_var='resultado'
    )
```

**Exception handling extendido**:
```python
except TimeoutException as e:
    logger.error(f"Timeout ejecutando código: {e}")
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

except SecurityException as e:
    logger.error(f"Código bloqueado por seguridad: {e}")
    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
```

## Validación

### Test de Validación (`test_fase_3_1.py`)

Valida 11 aspectos:

1. ✅ Código Python básico seguro (suma, condicionales, loops)
2. ✅ Timeout para código lento
3. ✅ Bloqueo de imports no permitidos (os, sys, subprocess, pathlib, socket)
4. ✅ Bloqueo de operaciones de archivo
5. ✅ Bloqueo de `__builtins__` peligrosos (eval, exec, __import__)
6. ✅ Imports permitidos (math, numpy)
7. ✅ Funciones numpy en namespace global
8. ✅ Parsing de modelo con tipo='codigo'
9. ✅ Integración con Consumer (código seguro)
10. ✅ Código malicioso bloqueado
11. ✅ Resumen completo del sistema

### Ejecutar Test

```bash
python test_fase_3_1.py
```

**Resultado esperado**: ✅ TODOS LOS TESTS PASARON EXITOSAMENTE

## Uso del Sistema

### 1. Crear Modelo con Código Python

Archivo: `modelos/ejemplo_codigo_python.ini`

```ini
[METADATA]
nombre = distancia_euclidiana
version = 1.0
descripcion = Calcula distancia euclidiana con código Python

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    # Calcular distancia euclidiana
    import math
    distancia = math.sqrt(x**2 + y**2)

    # Calcular ángulo
    angulo = math.atan2(y, x)

    # Resultado
    resultado = distancia * angulo

[SIMULACION]
numero_escenarios = 1000
```

### 2. Ejecutar Productor

```bash
python run_producer.py --modelo modelos/ejemplo_codigo_python.ini --escenarios 1000
```

### 3. Ejecutar Consumidores

```bash
python run_consumer.py --id C1 &
python run_consumer.py --id C2 &
python run_consumer.py --id C3 &
```

Los consumidores detectarán automáticamente que el modelo es tipo='codigo' y usarán el PythonExecutor seguro.

### 4. Uso Directo de PythonExecutor

```python
from src.common.python_executor import PythonExecutor, safe_execute, safe_eval

# Método 1: Usando la clase
executor = PythonExecutor(timeout=30.0)

codigo = """
import math
distancia = math.sqrt(x**2 + y**2)
resultado = distancia
"""

resultado = executor.execute(codigo, variables={'x': 3, 'y': 4})
print(resultado)  # 5.0

# Método 2: Función de conveniencia
resultado = safe_execute(
    "resultado = x + y",
    variables={'x': 1, 'y': 2},
    timeout=5.0
)
print(resultado)  # 3

# Método 3: Evaluar expresión
resultado = safe_eval("x**2 + y**2", variables={'x': 3, 'y': 4})
print(resultado)  # 25
```

## Ejemplos de Código Seguro

### Ejemplo 1: Cálculos Matemáticos

```python
codigo = """
import math

# Calcular valor absoluto de suma
suma = x + y
abs_suma = abs(suma)

# Aplicar función trigonométrica
resultado = math.sin(abs_suma)
"""
```

### Ejemplo 2: Uso de NumPy

```python
codigo = """
import numpy as np

# Crear array
valores = np.array([x, y, z])

# Calcular estadísticas
media = np.mean(valores)
std = np.std(valores)

# Resultado combinado
resultado = media + std
"""
```

### Ejemplo 3: Lógica Condicional

```python
codigo = """
import math

# Calcular distancia
dist = math.sqrt(x**2 + y**2)

# Aplicar lógica
if dist > 5:
    resultado = dist * 2
elif dist > 2:
    resultado = dist * 1.5
else:
    resultado = dist
"""
```

### Ejemplo 4: Loops y Agregación

```python
codigo = """
# Generar secuencia
suma = 0
for i in range(int(n)):
    suma += i * x

resultado = suma / n
"""
```

## Ejemplos de Código Bloqueado

### ❌ Import No Autorizado

```python
# BLOQUEADO: SecurityException
import os
resultado = os.getcwd()
```

### ❌ Operaciones de Archivo

```python
# BLOQUEADO: NameError (open no definido)
with open('/etc/passwd', 'r') as f:
    contenido = f.read()
resultado = len(contenido)
```

### ❌ Ejecución de Comandos

```python
# BLOQUEADO: SecurityException
import subprocess
salida = subprocess.run(['ls'], capture_output=True)
resultado = salida.returncode
```

### ❌ Eval/Exec

```python
# BLOQUEADO: SecurityException (Eval/Exec calls not allowed)
codigo_str = "x + y"
resultado = eval(codigo_str)
```

### ❌ Acceso a Red

```python
# BLOQUEADO: SecurityException
import socket
s = socket.socket()
s.connect(('google.com', 80))
resultado = 1
```

### ❌ Timeout

```python
# BLOQUEADO: TimeoutException (después de 30s)
suma = 0
while True:  # Loop infinito
    suma += 1
resultado = suma
```

## Características Técnicas

### Thread-Safety

El executor usa threading para implementar timeout:
```python
def execute(self, code, variables):
    def target():
        exec(compiled_code, exec_namespace)

    thread = threading.Thread(target=target)
    thread.daemon = True
    thread.start()
    thread.join(timeout=self.timeout)

    if thread.is_alive():
        raise TimeoutException(...)
```

### RestrictedPython Guards

Guards necesarios para funcionalidad completa:
```python
namespace['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
namespace['_unpack_sequence_'] = guarded_unpack_sequence
namespace['_getiter_'] = safe_iter  # Para loops
namespace['_inplacevar_'] = inplacevar  # Para +=, -=, etc.
```

### Namespace Seguro

Construcción del namespace:
```python
namespace = safe_globals.copy()  # Base de RestrictedPython
namespace['__builtins__'] = safe_builtins  # Builtins seguros
namespace.update(ALLOWED_IMPORTS)  # math, numpy
namespace.update(ALLOWED_NUMPY_FUNCS)  # sqrt, sin, cos, etc.
namespace['__import__'] = _safe_import  # Import controlado
```

### Compilación Segura

```python
compile_result = compile_restricted_exec(
    source=code,
    filename='<string>'
)

if compile_result.errors:
    raise SecurityException(...)

if compile_result.code is None:
    raise SecurityException(...)

return compile_result.code
```

## Dependencias

**Nuevas dependencias**:
- `RestrictedPython>=6.0`: Compilación segura de código Python

**Ya existentes**:
- `numpy>=1.24.0`: Operaciones numéricas
- `pika>=1.3.0`: RabbitMQ client

## Limitaciones

### Limitaciones de Seguridad

1. **No es 100% hermético**: Aunque RestrictedPython bloquea muchas operaciones peligrosas, no es imposible encontrar formas de saltarse las restricciones con código muy creativo.

2. **CPU-bound**: El timeout usa threading, que en Python no interrumpe threads bloqueados en operaciones CPU-bound. Código extremadamente intensivo puede tardar un poco más que el timeout.

3. **Memoria**: No hay límite de memoria configurado. Código que crea estructuras muy grandes puede consumir mucha RAM.

### Limitaciones Funcionales

1. **Solo stdlib y numpy**: No se pueden usar otras librerías (pandas, scikit-learn, etc.)

2. **No multithreading/multiprocessing**: El código ejecutado no puede crear sus propios threads o procesos.

3. **No I/O**: Sin acceso a archivos, red, base de datos.

4. **No persistencia entre escenarios**: Cada escenario se ejecuta en un namespace limpio.

## Troubleshooting

### Código no ejecuta correctamente

**Problema**: `ValueError: Variable 'resultado' no encontrada`

**Solución**: Asegurarte que el código define una variable `resultado`:
```python
# ❌ Incorrecto (no define resultado)
suma = x + y

# ✅ Correcto
suma = x + y
resultado = suma
```

### Imports no funcionan

**Problema**: `SecurityException: Import de módulo 'X' no permitido`

**Solución**: Solo `math` y `numpy` están permitidos. Para otras funciones, usa las disponibles globalmente:
```python
# ❌ Incorrecto
import numpy as np
resultado = np.sqrt(x)

# ✅ Correcto (sqrt disponible globalmente)
resultado = sqrt(x)

# ✅ También correcto
import numpy as np
resultado = np.sqrt(x)  # numpy sí está permitido
```

### Timeout muy corto

**Problema**: `TimeoutException` para código legítimo

**Solución**: Incrementar timeout al crear el executor:
```python
executor = PythonExecutor(timeout=60.0)  # 60 segundos
```

O en el consumer (modificar código):
```python
self.python_executor = PythonExecutor(timeout=60.0)
```

### Operaciones in-place fallan

**Problema**: `NameError: name '_inplacevar_' is not defined`

**Solución**: Esto está implementado en el namespace. Si falla, verificar que el namespace incluye:
```python
namespace['_inplacevar_'] = inplacevar
```

## Próximos Pasos (Fase 3.2+)

Posibles mejoras para futuras fases:

- [ ] Más distribuciones estadísticas (beta, gamma, lognormal, poisson, etc.)
- [ ] Límites de memoria configurables
- [ ] Sandboxing más robusto (contenedores, VMs)
- [ ] Soporte para más librerías científicas (pandas, scikit-learn)
- [ ] Caché de código compilado para mejor performance
- [ ] Profiling de código para optimización
- [ ] Visualización de dependencias entre variables
- [ ] Análisis estático de código antes de ejecución

## Conclusión

✅ **Fase 3.1 completada exitosamente**

El sistema ahora soporta:
- ✅ Ejecución segura de código Python arbitrario
- ✅ Timeout configurable para prevenir código lento
- ✅ Whitelist de imports (math, numpy)
- ✅ Protección contra código malicioso
- ✅ Integración completa con productor/consumer
- ✅ Parsing extendido de modelos .ini
- ✅ Tests comprehensivos de seguridad

El sistema está listo para ejecutar simulaciones Monte Carlo con código Python complejo de forma segura y distribuida.
