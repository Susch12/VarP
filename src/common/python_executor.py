"""
Ejecutor de código Python seguro usando RestrictedPython.

Este módulo permite ejecutar código Python arbitrario de forma segura con:
- Timeout configurable (por defecto 30 segundos)
- Whitelist de imports permitidos (math, numpy)
- Namespace seguro con safe_globals
- Protección contra código malicioso
"""

import signal
import math
import threading
from typing import Dict, Any, Optional, Callable
from functools import wraps
from RestrictedPython import compile_restricted_exec, safe_globals
from RestrictedPython.Guards import (
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
    safe_globals as restricted_safe_globals
)
import numpy as np


class TimeoutException(Exception):
    """Excepción lanzada cuando el código excede el timeout."""
    pass


class SecurityException(Exception):
    """Excepción lanzada cuando se detecta código potencialmente malicioso."""
    pass


class PythonExecutor:
    """
    Ejecutor de código Python seguro con RestrictedPython.

    Características:
    - Timeout configurable (default: 30s)
    - Whitelist de imports (math, numpy)
    - Namespace seguro
    - Protección contra operaciones peligrosas
    """

    # Whitelist de módulos permitidos
    ALLOWED_IMPORTS = {
        'math': math,
        'np': np,
        'numpy': np
    }

    # Funciones matemáticas permitidas de numpy
    ALLOWED_NUMPY_FUNCS = {
        # Operaciones básicas
        'abs': np.abs,
        'sqrt': np.sqrt,
        'exp': np.exp,
        'log': np.log,
        'log10': np.log10,
        'log2': np.log2,

        # Trigonométricas
        'sin': np.sin,
        'cos': np.cos,
        'tan': np.tan,
        'arcsin': np.arcsin,
        'arccos': np.arccos,
        'arctan': np.arctan,
        'arctan2': np.arctan2,

        # Hiperbólicas
        'sinh': np.sinh,
        'cosh': np.cosh,
        'tanh': np.tanh,

        # Redondeo
        'floor': np.floor,
        'ceil': np.ceil,
        'round': np.round,

        # Agregación
        'sum': np.sum,
        'mean': np.mean,
        'median': np.median,
        'std': np.std,
        'var': np.var,
        'min': np.min,
        'max': np.max,

        # Potencias
        'power': np.power,
        'square': np.square,

        # Otros
        'sign': np.sign,
        'clip': np.clip,
    }

    def __init__(self, timeout: float = 30.0):
        """
        Inicializa el ejecutor de Python seguro.

        Args:
            timeout: Tiempo máximo de ejecución en segundos (default: 30.0)
        """
        self.timeout = timeout
        self._safe_namespace = self._create_safe_namespace()

    def _create_safe_namespace(self) -> Dict[str, Any]:
        """
        Crea un namespace seguro con imports permitidos.

        Returns:
            Dict con el namespace seguro
        """
        # Comenzar con safe_globals de RestrictedPython
        namespace = safe_globals.copy()

        # Agregar guards necesarios para RestrictedPython
        namespace['_iter_unpack_sequence_'] = guarded_iter_unpack_sequence
        namespace['_unpack_sequence_'] = guarded_unpack_sequence

        # Crear una copia de safe_builtins y agregar __import__
        custom_builtins = safe_builtins.copy()
        custom_builtins['__import__'] = self._safe_import

        namespace['__builtins__'] = custom_builtins

        # _getiter_ para iteraciones seguras (permite iterar sobre listas, tuplas, range, etc.)
        def safe_iter(obj):
            """Permite iteración sobre objetos seguros."""
            # Permitir iteración sobre tipos básicos y numpy arrays
            if isinstance(obj, (list, tuple, range, str, dict, set, frozenset, np.ndarray)):
                return iter(obj)
            # Permitir iteradores
            if hasattr(obj, '__iter__'):
                return iter(obj)
            raise TypeError(f"Iteration over {type(obj).__name__} not allowed")

        namespace['_getiter_'] = safe_iter

        # _inplacevar_ para operaciones in-place como +=, -=, *=, etc.
        import operator
        def inplacevar(op, x, y):
            """Permite operaciones in-place seguras."""
            # op es una string como '+=', necesitamos mapearla
            if callable(op):
                return op(x, y)
            # Si es string, mapear a operador
            op_map = {
                '+=': operator.iadd,
                '-=': operator.isub,
                '*=': operator.imul,
                '/=': operator.itruediv,
                '//=': operator.ifloordiv,
                '%=': operator.imod,
                '**=': operator.ipow,
                '&=': operator.iand,
                '|=': operator.ior,
                '^=': operator.ixor,
                '<<=': operator.ilshift,
                '>>=': operator.irshift,
            }
            if op in op_map:
                return op_map[op](x, y)
            # Si ya es callable, ejecutarlo
            return op(x, y)

        namespace['_inplacevar_'] = inplacevar

        # Agregar módulos permitidos
        namespace.update(self.ALLOWED_IMPORTS)

        # Agregar funciones específicas de numpy al namespace global
        namespace.update(self.ALLOWED_NUMPY_FUNCS)

        # Agregar funciones built-in seguras adicionales
        namespace['abs'] = abs
        namespace['min'] = min
        namespace['max'] = max
        namespace['sum'] = sum
        namespace['len'] = len
        namespace['range'] = range
        namespace['enumerate'] = enumerate
        namespace['zip'] = zip
        namespace['map'] = map
        namespace['filter'] = filter

        return namespace

    def _timeout_handler(self, signum, frame):
        """Handler para la señal de timeout."""
        raise TimeoutException(f"Ejecución excedió el timeout de {self.timeout}s")

    def _safe_import(self, name: str, *args, **kwargs):
        """
        Función de import segura que solo permite módulos en whitelist.

        Args:
            name: Nombre del módulo a importar

        Returns:
            El módulo si está en la whitelist

        Raises:
            SecurityException: Si el módulo no está permitido
        """
        if name in self.ALLOWED_IMPORTS:
            return self.ALLOWED_IMPORTS[name]
        else:
            raise SecurityException(
                f"Import de módulo '{name}' no permitido. "
                f"Módulos permitidos: {list(self.ALLOWED_IMPORTS.keys())}"
            )

    def compile_code(self, code: str, filename: str = "<string>") -> Any:
        """
        Compila código Python usando RestrictedPython.

        Args:
            code: Código Python a compilar
            filename: Nombre del archivo (para mensajes de error)

        Returns:
            Código compilado

        Raises:
            SyntaxError: Si el código tiene errores de sintaxis
            SecurityException: Si el código contiene operaciones no permitidas
        """
        try:
            # Compilar con RestrictedPython
            compile_result = compile_restricted_exec(
                source=code,
                filename=filename
            )

            # Verificar si hubo errores
            if compile_result.errors:
                error_msg = "\n".join(compile_result.errors)
                raise SecurityException(
                    f"Código contiene operaciones no permitidas:\n{error_msg}"
                )

            # Verificar que el código fue compilado exitosamente
            if compile_result.code is None:
                raise SecurityException(
                    "Error compilando código: compilación falló sin errores específicos"
                )

            return compile_result.code

        except SyntaxError as e:
            raise SyntaxError(f"Error de sintaxis en el código: {e}")

    def execute(
        self,
        code: str,
        variables: Optional[Dict[str, Any]] = None,
        result_var: str = 'resultado'
    ) -> Any:
        """
        Ejecuta código Python de forma segura con timeout.

        Args:
            code: Código Python a ejecutar
            variables: Variables a inyectar en el namespace
            result_var: Nombre de la variable que contiene el resultado

        Returns:
            El valor de la variable result_var después de la ejecución

        Raises:
            TimeoutException: Si la ejecución excede el timeout
            SecurityException: Si el código contiene operaciones no permitidas
            Exception: Cualquier excepción lanzada por el código
        """
        # Preparar namespace
        exec_namespace = self._safe_namespace.copy()

        # Inyectar variables del usuario
        if variables:
            exec_namespace.update(variables)

        # Compilar código
        compiled_code = self.compile_code(code)

        # Ejecutar con timeout
        exception_container = [None]
        result_container = [None]

        def target():
            """Función objetivo para el thread."""
            try:
                exec(compiled_code, exec_namespace)
                # Extraer resultado
                if result_var in exec_namespace:
                    result_container[0] = exec_namespace[result_var]
                else:
                    exception_container[0] = ValueError(
                        f"Variable '{result_var}' no encontrada después de la ejecución"
                    )
            except Exception as e:
                exception_container[0] = e

        # Crear y ejecutar thread con timeout
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=self.timeout)

        # Verificar si el thread terminó
        if thread.is_alive():
            # Thread aún corriendo = timeout
            raise TimeoutException(
                f"Ejecución excedió el timeout de {self.timeout}s"
            )

        # Verificar si hubo excepciones
        if exception_container[0] is not None:
            raise exception_container[0]

        return result_container[0]

    def execute_expression(
        self,
        expression: str,
        variables: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Ejecuta una expresión Python simple y retorna su resultado.

        Esta es una versión simplificada de execute() para expresiones simples
        que no requieren asignación a una variable resultado.

        Args:
            expression: Expresión Python a evaluar
            variables: Variables a inyectar en el namespace

        Returns:
            El resultado de evaluar la expresión

        Raises:
            TimeoutException: Si la ejecución excede el timeout
            SecurityException: Si el código contiene operaciones no permitidas
            Exception: Cualquier excepción lanzada por el código
        """
        # Envolver expresión en asignación
        code = f"resultado = {expression}"
        return self.execute(code, variables=variables, result_var='resultado')


def timeout_decorator(seconds: float = 30.0) -> Callable:
    """
    Decorador para agregar timeout a funciones.

    Args:
        seconds: Tiempo máximo de ejecución en segundos

    Returns:
        Decorador configurado

    Example:
        @timeout_decorator(5.0)
        def slow_function():
            time.sleep(10)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            result_container = [None]
            exception_container = [None]

            def target():
                try:
                    result_container[0] = func(*args, **kwargs)
                except Exception as e:
                    exception_container[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout=seconds)

            if thread.is_alive():
                raise TimeoutException(f"Función excedió el timeout de {seconds}s")

            if exception_container[0] is not None:
                raise exception_container[0]

            return result_container[0]

        return wrapper
    return decorator


# Instancia global con configuración por defecto
default_executor = PythonExecutor(timeout=30.0)


def safe_execute(
    code: str,
    variables: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0
) -> Any:
    """
    Función de conveniencia para ejecutar código Python de forma segura.

    Args:
        code: Código Python a ejecutar
        variables: Variables a inyectar
        timeout: Timeout en segundos

    Returns:
        Resultado de la ejecución

    Example:
        result = safe_execute(
            "resultado = x + y",
            variables={'x': 1, 'y': 2}
        )
    """
    executor = PythonExecutor(timeout=timeout)
    return executor.execute(code, variables=variables)


def safe_eval(
    expression: str,
    variables: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0
) -> Any:
    """
    Función de conveniencia para evaluar expresiones Python de forma segura.

    Args:
        expression: Expresión Python a evaluar
        variables: Variables a inyectar
        timeout: Timeout en segundos

    Returns:
        Resultado de evaluar la expresión

    Example:
        result = safe_eval("x + y", variables={'x': 1, 'y': 2})
    """
    executor = PythonExecutor(timeout=timeout)
    return executor.execute_expression(expression, variables=variables)
