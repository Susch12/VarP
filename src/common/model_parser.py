"""
Parser de archivos de modelo en formato .ini para simulación Monte Carlo.

Lee y valida archivos de configuración que definen:
- Metadata del modelo
- Variables estocásticas con distribuciones
- Función a ejecutar (expresiones o código Python)
- Parámetros de simulación
"""

import ast
import configparser
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field


class ModelParserError(Exception):
    """Excepción para errores de parsing del modelo."""
    pass


@dataclass
class Variable:
    """Representa una variable estocástica del modelo."""
    nombre: str
    tipo: str  # 'float' o 'int'
    distribucion: str  # 'normal', 'uniform', etc.
    parametros: Dict[str, Any]

    def __repr__(self):
        return (f"Variable(nombre='{self.nombre}', tipo='{self.tipo}', "
                f"distribucion='{self.distribucion}', parametros={self.parametros})")


@dataclass
class Modelo:
    """Representa un modelo completo parseado."""
    # Metadata
    nombre: str
    version: str
    descripcion: str = ""
    autor: str = ""
    fecha_creacion: str = ""

    # Variables
    variables: List[Variable] = field(default_factory=list)

    # Función
    tipo_funcion: str = "expresion"  # 'expresion' o 'codigo'
    expresion: Optional[str] = None
    codigo: Optional[str] = None

    # Simulación
    numero_escenarios: int = 1000
    semilla_aleatoria: Optional[int] = None

    def __repr__(self):
        return (f"Modelo(nombre='{self.nombre}', version='{self.version}', "
                f"variables={len(self.variables)}, tipo='{self.tipo_funcion}')")


class ModelParser:
    """
    Parser de archivos de modelo en formato .ini.

    Lee archivos con secciones:
    - [METADATA]: Información del modelo
    - [VARIABLES]: Definición de variables estocásticas
    - [FUNCION]: Función a ejecutar
    - [SIMULACION]: Parámetros de simulación
    """

    REQUIRED_SECTIONS = ['METADATA', 'VARIABLES', 'FUNCION', 'SIMULACION']
    VALID_TIPOS = {'float', 'int'}
    VALID_DISTRIBUCIONES = {
        'normal', 'uniform', 'exponential',  # Fase 1
        'lognormal', 'triangular', 'binomial'  # Fase 3.2
    }

    def __init__(self, filepath: str):
        """
        Inicializa el parser con un archivo de modelo.

        Args:
            filepath: Ruta al archivo .ini del modelo

        Raises:
            ModelParserError: Si el archivo no existe
        """
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise ModelParserError(f"Archivo no encontrado: {filepath}")

        self.config = configparser.ConfigParser(
            allow_no_value=False,
            inline_comment_prefixes='#'
        )

        try:
            self.config.read(self.filepath, encoding='utf-8')
        except Exception as e:
            raise ModelParserError(f"Error leyendo archivo: {e}")

    def parse(self) -> Modelo:
        """
        Parsea el archivo completo y retorna el modelo.

        Returns:
            Instancia de Modelo con toda la información parseada

        Raises:
            ModelParserError: Si hay errores en el formato o validación
        """
        # Verificar secciones requeridas
        self._validate_sections()

        # Parsear cada sección
        metadata = self._parse_metadata()
        variables = self._parse_variables()
        funcion = self._parse_funcion()
        simulacion = self._parse_simulacion()

        # Construir modelo
        modelo = Modelo(
            # Metadata
            nombre=metadata['nombre'],
            version=metadata['version'],
            descripcion=metadata.get('descripcion', ''),
            autor=metadata.get('autor', ''),
            fecha_creacion=metadata.get('fecha_creacion', ''),

            # Variables
            variables=variables,

            # Función
            tipo_funcion=funcion['tipo'],
            expresion=funcion.get('expresion'),
            codigo=funcion.get('codigo'),

            # Simulación
            numero_escenarios=simulacion['numero_escenarios'],
            semilla_aleatoria=simulacion.get('semilla_aleatoria')
        )

        return modelo

    def _validate_sections(self):
        """
        Valida que existan todas las secciones requeridas.

        Raises:
            ModelParserError: Si falta alguna sección
        """
        existing_sections = set(self.config.sections())
        required_sections = set(self.REQUIRED_SECTIONS)
        missing = required_sections - existing_sections

        if missing:
            raise ModelParserError(
                f"Secciones faltantes en archivo: {missing}"
            )

    def _parse_metadata(self) -> Dict[str, str]:
        """
        Parsea la sección [METADATA].

        Returns:
            Diccionario con metadata del modelo

        Raises:
            ModelParserError: Si faltan campos requeridos
        """
        section = 'METADATA'
        metadata = {}

        # Campos requeridos
        try:
            metadata['nombre'] = self.config.get(section, 'nombre').strip()
            metadata['version'] = self.config.get(section, 'version').strip()
        except configparser.NoOptionError as e:
            raise ModelParserError(f"Campo requerido faltante en [METADATA]: {e}")

        # Campos opcionales
        metadata['descripcion'] = self.config.get(
            section, 'descripcion', fallback=''
        ).strip()
        metadata['autor'] = self.config.get(
            section, 'autor', fallback=''
        ).strip()
        metadata['fecha_creacion'] = self.config.get(
            section, 'fecha_creacion', fallback=''
        ).strip()

        return metadata

    def _parse_variables(self) -> List[Variable]:
        """
        Parsea la sección [VARIABLES].

        Formato esperado por línea:
        nombre, tipo, distribucion, param1=val1, param2=val2, ...

        Returns:
            Lista de objetos Variable

        Raises:
            ModelParserError: Si hay errores de formato o validación
        """
        section = 'VARIABLES'
        variables = []

        # Leer archivo línea por línea para la sección VARIABLES
        in_variables_section = False
        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Detectar inicio de sección VARIABLES
                if line == '[VARIABLES]':
                    in_variables_section = True
                    continue

                # Detectar fin de sección (nueva sección o EOF)
                if in_variables_section and line.startswith('['):
                    break

                # Procesar líneas de variables
                if in_variables_section and line and not line.startswith('#'):
                    try:
                        variable = self._parse_variable_raw_line(line)
                        variables.append(variable)
                    except Exception as e:
                        raise ModelParserError(
                            f"Error en línea {line_num} parseando variable: {e}"
                        )

        if not variables:
            raise ModelParserError("No se encontraron variables en [VARIABLES]")

        return variables

    def _parse_variable_raw_line(self, line: str) -> Variable:
        """
        Parsea una línea raw de especificación de variable.

        Args:
            line: Línea completa "nombre, tipo, distribucion, param1=val1, ..."

        Returns:
            Objeto Variable

        Examples:
            _parse_variable_raw_line('x, float, normal, media=0, std=1')
            -> Variable(nombre='x', tipo='float', distribucion='normal',
                       parametros={'media': 0.0, 'std': 1.0})
        """
        # Dividir por comas
        parts = [p.strip() for p in line.split(',')]

        if len(parts) < 3:
            raise ValueError(
                f"Formato inválido. Esperado: nombre, tipo, distribucion, parametros..."
            )

        nombre = parts[0]
        tipo = parts[1].lower()
        distribucion = parts[2].lower()
        param_parts = parts[3:]

        return self._parse_variable_line(nombre, f"{tipo}, {distribucion}, {', '.join(param_parts)}")

    def _parse_variable_line(self, nombre: str, spec: str) -> Variable:
        """
        Parsea una línea de especificación de variable.

        Args:
            nombre: Nombre de la variable
            spec: Especificación "tipo, distribucion, param1=val1, ..."

        Returns:
            Objeto Variable

        Examples:
            _parse_variable_line('x', 'float, normal, media=0, std=1')
            -> Variable(nombre='x', tipo='float', distribucion='normal',
                       parametros={'media': 0.0, 'std': 1.0})
        """
        # Dividir por comas
        parts = [p.strip() for p in spec.split(',')]

        if len(parts) < 2:
            raise ValueError(
                f"Formato inválido. Esperado: tipo, distribucion, parametros..."
            )

        tipo = parts[0].lower()
        distribucion = parts[1].lower()
        param_parts = parts[2:]

        # Validar tipo
        if tipo not in self.VALID_TIPOS:
            raise ValueError(
                f"Tipo '{tipo}' inválido. Válidos: {self.VALID_TIPOS}"
            )

        # Validar distribución
        if distribucion not in self.VALID_DISTRIBUCIONES:
            raise ValueError(
                f"Distribución '{distribucion}' no soportada. "
                f"Válidas: {self.VALID_DISTRIBUCIONES}"
            )

        # Parsear parámetros: "media=0", "std=1"
        parametros = {}
        for param_str in param_parts:
            if '=' not in param_str:
                raise ValueError(
                    f"Parámetro inválido: '{param_str}'. "
                    f"Esperado formato: param=valor"
                )

            param_name, param_value = param_str.split('=', 1)
            param_name = param_name.strip()
            param_value = param_value.strip()

            # Convertir valor a float
            try:
                parametros[param_name] = float(param_value)
            except ValueError:
                raise ValueError(
                    f"Valor del parámetro '{param_name}' no es numérico: '{param_value}'"
                )

        return Variable(
            nombre=nombre,
            tipo=tipo,
            distribucion=distribucion,
            parametros=parametros
        )

    def _parse_funcion(self) -> Dict[str, Any]:
        """
        Parsea la sección [FUNCION].

        Returns:
            Diccionario con tipo y contenido de la función

        Raises:
            ModelParserError: Si hay errores de formato
        """
        section = 'FUNCION'
        funcion = {}

        # Tipo de función
        try:
            tipo = self.config.get(section, 'tipo').strip().lower()
        except configparser.NoOptionError:
            raise ModelParserError(
                "Campo 'tipo' requerido en [FUNCION]"
            )

        if tipo not in ['expresion', 'codigo']:
            raise ModelParserError(
                f"Tipo de función inválido: '{tipo}'. "
                f"Válidos: 'expresion', 'codigo'"
            )

        funcion['tipo'] = tipo

        # Contenido según tipo
        if tipo == 'expresion':
            try:
                expresion = self.config.get(section, 'expresion').strip()
            except configparser.NoOptionError:
                raise ModelParserError(
                    "Campo 'expresion' requerido cuando tipo='expresion'"
                )

            if not expresion:
                raise ModelParserError("Expresión no puede estar vacía")

            funcion['expresion'] = expresion

        elif tipo == 'codigo':
            # Fase 3 - Soporte para código Python
            codigo = self._parse_codigo_multilinea()

            if not codigo:
                raise ModelParserError("Código no puede estar vacío")

            # Fase 3.3: Validar sintaxis Python
            self._validate_python_syntax(codigo)

            # Fase 3.3: Verificar que define variable 'resultado'
            if not self._check_resultado_variable(codigo):
                raise ModelParserError(
                    "El código debe definir una variable 'resultado'\n"
                    "Ejemplo: resultado = x + y"
                )

            funcion['codigo'] = codigo

        return funcion

    def _parse_codigo_multilinea(self) -> str:
        """
        Parsea código Python multilínea de la sección [FUNCION].

        El código debe estar después de una línea 'codigo =' o similar.
        Todas las líneas siguientes hasta el final de la sección son parte del código.

        Returns:
            String con el código completo (preservando indentación)

        Raises:
            ModelParserError: Si no se encuentra código

        Example formato en .ini:
            [FUNCION]
            tipo = codigo
            codigo =
                # Calcular resultado
                suma = x + y
                producto = x * y
                resultado = suma * producto
        """
        codigo_lines = []
        in_funcion_section = False
        found_codigo_marker = False

        with open(self.filepath, 'r', encoding='utf-8') as f:
            for line in f:
                stripped = line.strip()

                # Detectar inicio de sección FUNCION
                if stripped == '[FUNCION]':
                    in_funcion_section = True
                    continue

                # Detectar fin de sección
                if in_funcion_section and stripped.startswith('['):
                    break

                # Buscar marcador 'codigo ='
                if in_funcion_section and not found_codigo_marker:
                    if stripped.startswith('codigo'):
                        # Verificar si hay contenido en la misma línea
                        if '=' in stripped:
                            parts = stripped.split('=', 1)
                            if len(parts) == 2 and parts[1].strip():
                                # Código en la misma línea
                                codigo_lines.append(parts[1].strip())
                        found_codigo_marker = True
                        continue

                # Recolectar líneas de código (después del marcador)
                if in_funcion_section and found_codigo_marker:
                    # Ignorar líneas que son otros parámetros
                    if '=' in stripped and not line.startswith((' ', '\t')):
                        # Es otro parámetro, no parte del código
                        continue

                    # Ignorar comentarios INI completos
                    if stripped.startswith('#') or stripped.startswith(';'):
                        continue

                    # Agregar línea de código (preservar indentación relativa)
                    # Remover indentación común pero preservar indentación relativa
                    codigo_lines.append(line.rstrip())

        if not found_codigo_marker:
            raise ModelParserError(
                "No se encontró 'codigo =' en sección [FUNCION]"
            )

        # Unir líneas y limpiar indentación común
        codigo = '\n'.join(codigo_lines)

        # Remover indentación común (preservando indentación relativa)
        codigo = self._dedent_code(codigo)

        return codigo.strip()

    def _dedent_code(self, code: str) -> str:
        """
        Remueve indentación común del código, preservando indentación relativa.

        Args:
            code: Código con posible indentación común

        Returns:
            Código con indentación común removida

        Example:
            Input:  "    x = 1\n    y = 2\n        z = x + y"
            Output: "x = 1\ny = 2\n    z = x + y"
        """
        if not code:
            return code

        lines = code.split('\n')

        # Encontrar indentación mínima (excluyendo líneas vacías)
        min_indent = float('inf')
        for line in lines:
            if line.strip():  # Ignorar líneas vacías
                # Contar espacios/tabs al inicio
                indent = len(line) - len(line.lstrip())
                min_indent = min(min_indent, indent)

        if min_indent == float('inf'):
            return code

        # Remover indentación común
        dedented_lines = []
        for line in lines:
            if line.strip():
                dedented_lines.append(line[min_indent:])
            else:
                dedented_lines.append('')

        return '\n'.join(dedented_lines)

    def _validate_python_syntax(self, code: str) -> None:
        """
        Valida que el código Python tenga sintaxis correcta.

        Args:
            code: Código Python a validar

        Raises:
            ModelParserError: Si el código tiene errores de sintaxis

        Note:
            Usa ast.parse para validar sintaxis sin ejecutar el código
        """
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise ModelParserError(
                f"Error de sintaxis Python en código:\n"
                f"  Línea {e.lineno}: {e.msg}\n"
                f"  {e.text}"
            )

    def _check_resultado_variable(self, code: str) -> bool:
        """
        Verifica si el código define una variable 'resultado'.

        Args:
            code: Código Python a analizar

        Returns:
            True si el código asigna a 'resultado', False en caso contrario

        Note:
            Analiza el AST para detectar asignaciones a 'resultado'
        """
        try:
            tree = ast.parse(code)

            # Buscar asignaciones en el AST
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    # Revisar targets de la asignación
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == 'resultado':
                            return True
                        # Caso de tuple unpacking: a, resultado = ...
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name) and elt.id == 'resultado':
                                    return True
                # Caso de asignación aumentada: resultado += ...
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name) and node.target.id == 'resultado':
                        return True

            return False
        except SyntaxError:
            # Si hay error de sintaxis, retornar False
            return False

    def _get_assigned_variables(self, code: str) -> Set[str]:
        """
        Obtiene el conjunto de variables asignadas en el código.

        Args:
            code: Código Python a analizar

        Returns:
            Set de nombres de variables asignadas

        Note:
            Analiza el AST para extraer todas las asignaciones
        """
        try:
            tree = ast.parse(code)
            variables = set()

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            variables.add(target.id)
                        elif isinstance(target, ast.Tuple):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    variables.add(elt.id)
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name):
                        variables.add(node.target.id)

            return variables
        except SyntaxError:
            return set()

    def _parse_simulacion(self) -> Dict[str, Any]:
        """
        Parsea la sección [SIMULACION].

        Returns:
            Diccionario con parámetros de simulación

        Raises:
            ModelParserError: Si hay errores de formato
        """
        section = 'SIMULACION'
        simulacion = {}

        # Número de escenarios (requerido)
        try:
            num_escenarios = self.config.getint(section, 'numero_escenarios')
        except configparser.NoOptionError:
            raise ModelParserError(
                "Campo 'numero_escenarios' requerido en [SIMULACION]"
            )
        except ValueError as e:
            raise ModelParserError(
                f"'numero_escenarios' debe ser un entero: {e}"
            )

        if num_escenarios <= 0:
            raise ModelParserError(
                f"'numero_escenarios' debe ser > 0, obtenido: {num_escenarios}"
            )

        simulacion['numero_escenarios'] = num_escenarios

        # Semilla aleatoria (opcional)
        try:
            semilla = self.config.getint(section, 'semilla_aleatoria')
            simulacion['semilla_aleatoria'] = semilla
        except configparser.NoOptionError:
            simulacion['semilla_aleatoria'] = None
        except ValueError as e:
            raise ModelParserError(
                f"'semilla_aleatoria' debe ser un entero: {e}"
            )

        return simulacion


def parse_model_file(filepath: str) -> Modelo:
    """
    Función de conveniencia para parsear un archivo de modelo.

    Args:
        filepath: Ruta al archivo .ini

    Returns:
        Modelo parseado

    Raises:
        ModelParserError: Si hay errores de parsing

    Examples:
        >>> modelo = parse_model_file('modelos/ejemplo_simple.ini')
        >>> print(modelo.nombre)
        suma_normal
    """
    parser = ModelParser(filepath)
    return parser.parse()


__all__ = [
    'ModelParser',
    'ModelParserError',
    'Modelo',
    'Variable',
    'parse_model_file'
]
