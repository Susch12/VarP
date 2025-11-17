"""
Evaluador de expresiones matemáticas de forma segura usando AST.

Permite ejecutar expresiones matemáticas sin riesgos de seguridad,
validando que solo se usen operaciones y funciones permitidas.
"""

import ast
import operator
import math
from typing import Dict, Any, Set


class ExpressionEvaluationError(Exception):
    """Excepción para errores en evaluación de expresiones."""
    pass


class SafeExpressionEvaluator:
    """
    Evaluador seguro de expresiones matemáticas usando AST.

    Solo permite operaciones matemáticas básicas y funciones seguras.
    No permite imports, asignaciones, llamadas a funciones arbitrarias, etc.
    """

    # Operadores binarios permitidos
    ALLOWED_OPERATORS = {
        ast.Add: operator.add,       # +
        ast.Sub: operator.sub,       # -
        ast.Mult: operator.mul,      # *
        ast.Div: operator.truediv,   # /
        ast.FloorDiv: operator.floordiv,  # //
        ast.Mod: operator.mod,       # %
        ast.Pow: operator.pow,       # **
    }

    # Operadores unarios permitidos
    ALLOWED_UNARY_OPS = {
        ast.UAdd: operator.pos,      # +x
        ast.USub: operator.neg,      # -x
    }

    # Operadores de comparación permitidos
    ALLOWED_COMPARE_OPS = {
        ast.Eq: operator.eq,         # ==
        ast.NotEq: operator.ne,      # !=
        ast.Lt: operator.lt,         # <
        ast.LtE: operator.le,        # <=
        ast.Gt: operator.gt,         # >
        ast.GtE: operator.ge,        # >=
    }

    # Funciones matemáticas permitidas
    ALLOWED_FUNCTIONS = {
        # Funciones básicas
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,

        # Funciones de math
        'sqrt': math.sqrt,
        'pow': math.pow,
        'exp': math.exp,
        'log': math.log,
        'log10': math.log10,
        'log2': math.log2,

        # Trigonométricas
        'sin': math.sin,
        'cos': math.cos,
        'tan': math.tan,
        'asin': math.asin,
        'acos': math.acos,
        'atan': math.atan,
        'atan2': math.atan2,

        # Hiperbólicas
        'sinh': math.sinh,
        'cosh': math.cosh,
        'tanh': math.tanh,

        # Otras
        'ceil': math.ceil,
        'floor': math.floor,
        'trunc': math.trunc,
        'degrees': math.degrees,
        'radians': math.radians,
    }

    # Constantes permitidas
    ALLOWED_CONSTANTS = {
        'pi': math.pi,
        'e': math.e,
        'tau': math.tau,
        'inf': math.inf,
        'nan': math.nan,
    }

    def __init__(self):
        """Inicializa el evaluador."""
        pass

    def evaluate(self, expression: str, variables: Dict[str, Any]) -> Any:
        """
        Evalúa una expresión matemática de forma segura.

        Args:
            expression: Expresión matemática como string
            variables: Diccionario con valores de variables

        Returns:
            Resultado de evaluar la expresión

        Raises:
            ExpressionEvaluationError: Si la expresión no es válida o segura

        Examples:
            >>> evaluator = SafeExpressionEvaluator()
            >>> evaluator.evaluate('x + y', {'x': 2, 'y': 3})
            5
            >>> evaluator.evaluate('x**2 + y**2', {'x': 3, 'y': 4})
            25
            >>> evaluator.evaluate('sqrt(x)', {'x': 16})
            4.0
        """
        try:
            # Parsear expresión a AST
            tree = ast.parse(expression, mode='eval')

            # Validar que solo use operaciones permitidas
            self._validate_ast(tree)

            # Evaluar
            return self._eval_node(tree.body, variables)

        except SyntaxError as e:
            raise ExpressionEvaluationError(f"Error de sintaxis en expresión: {e}")
        except Exception as e:
            raise ExpressionEvaluationError(f"Error evaluando expresión: {e}")

    def _validate_ast(self, tree: ast.AST) -> None:
        """
        Valida que el AST solo contenga nodos permitidos.

        Args:
            tree: AST a validar

        Raises:
            ExpressionEvaluationError: Si contiene nodos no permitidos
        """
        for node in ast.walk(tree):
            node_type = type(node).__name__

            # Nodos siempre permitidos
            allowed_nodes = {
                'Module', 'Expr', 'Expression',
                'Load', 'Store',
                'Num', 'Constant',  # Números y constantes
                'Name',             # Variables
                'BinOp',            # Operaciones binarias
                'UnaryOp',          # Operaciones unarias
                'Compare',          # Comparaciones
                'Call',             # Llamadas a funciones
                'IfExp',            # Expresiones condicionales (x if cond else y)
            }

            if node_type not in allowed_nodes:
                # Verificar si es un operador permitido
                if not (isinstance(node, tuple(self.ALLOWED_OPERATORS.keys())) or
                        isinstance(node, tuple(self.ALLOWED_UNARY_OPS.keys())) or
                        isinstance(node, tuple(self.ALLOWED_COMPARE_OPS.keys()))):
                    raise ExpressionEvaluationError(
                        f"Operación no permitida en expresión: {node_type}"
                    )

    def _eval_node(self, node: ast.AST, variables: Dict[str, Any]) -> Any:
        """
        Evalúa un nodo del AST recursivamente.

        Args:
            node: Nodo AST a evaluar
            variables: Variables disponibles

        Returns:
            Resultado de evaluar el nodo
        """
        # Constantes (números)
        if isinstance(node, ast.Constant):
            return node.value

        # Para compatibilidad con Python < 3.8
        if isinstance(node, ast.Num):
            return node.n

        # Variables
        if isinstance(node, ast.Name):
            var_name = node.id

            # Verificar si es una constante permitida
            if var_name in self.ALLOWED_CONSTANTS:
                return self.ALLOWED_CONSTANTS[var_name]

            # Verificar si es una variable del modelo
            if var_name in variables:
                return variables[var_name]

            raise ExpressionEvaluationError(
                f"Variable '{var_name}' no definida"
            )

        # Operaciones binarias (x + y, x * y, etc.)
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, variables)
            right = self._eval_node(node.right, variables)
            op_type = type(node.op)

            if op_type not in self.ALLOWED_OPERATORS:
                raise ExpressionEvaluationError(
                    f"Operador no permitido: {op_type.__name__}"
                )

            op_func = self.ALLOWED_OPERATORS[op_type]
            return op_func(left, right)

        # Operaciones unarias (+x, -x)
        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand, variables)
            op_type = type(node.op)

            if op_type not in self.ALLOWED_UNARY_OPS:
                raise ExpressionEvaluationError(
                    f"Operador unario no permitido: {op_type.__name__}"
                )

            op_func = self.ALLOWED_UNARY_OPS[op_type]
            return op_func(operand)

        # Comparaciones (x > y, x == y, etc.)
        if isinstance(node, ast.Compare):
            left = self._eval_node(node.left, variables)

            for op, comparator in zip(node.ops, node.comparators):
                right = self._eval_node(comparator, variables)
                op_type = type(op)

                if op_type not in self.ALLOWED_COMPARE_OPS:
                    raise ExpressionEvaluationError(
                        f"Comparador no permitido: {op_type.__name__}"
                    )

                op_func = self.ALLOWED_COMPARE_OPS[op_type]
                result = op_func(left, right)

                if not result:
                    return False

                left = right

            return True

        # Llamadas a funciones (sqrt(x), sin(x), etc.)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionEvaluationError(
                    "Solo se permiten llamadas a funciones simples"
                )

            func_name = node.func.id

            if func_name not in self.ALLOWED_FUNCTIONS:
                raise ExpressionEvaluationError(
                    f"Función '{func_name}' no permitida"
                )

            func = self.ALLOWED_FUNCTIONS[func_name]

            # Evaluar argumentos
            args = [self._eval_node(arg, variables) for arg in node.args]

            # No permitir keyword arguments por seguridad
            if node.keywords:
                raise ExpressionEvaluationError(
                    "No se permiten argumentos con nombre"
                )

            return func(*args)

        # Expresiones condicionales (x if cond else y)
        if isinstance(node, ast.IfExp):
            test = self._eval_node(node.test, variables)
            if test:
                return self._eval_node(node.body, variables)
            else:
                return self._eval_node(node.orelse, variables)

        raise ExpressionEvaluationError(
            f"Tipo de nodo no soportado: {type(node).__name__}"
        )


# Factory function para conveniencia
def evaluate_expression(expression: str, variables: Dict[str, Any]) -> Any:
    """
    Función de conveniencia para evaluar una expresión.

    Args:
        expression: Expresión matemática
        variables: Variables disponibles

    Returns:
        Resultado de la evaluación

    Examples:
        >>> evaluate_expression('x + y', {'x': 2, 'y': 3})
        5
    """
    evaluator = SafeExpressionEvaluator()
    return evaluator.evaluate(expression, variables)


__all__ = [
    'SafeExpressionEvaluator',
    'ExpressionEvaluationError',
    'evaluate_expression'
]
