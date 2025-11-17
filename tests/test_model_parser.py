"""
Tests para el parser de modelos .ini
"""

import pytest
import tempfile
from pathlib import Path
from src.common.model_parser import (
    ModelParser,
    ModelParserError,
    Modelo,
    Variable,
    parse_model_file
)


# Fixture: archivo de modelo válido
@pytest.fixture
def valid_model_file(tmp_path):
    """Crea un archivo de modelo válido para tests."""
    content = """
[METADATA]
nombre = test_modelo
version = 1.0
descripcion = Modelo de prueba
autor = Test Suite
fecha_creacion = 2025-01-17

[VARIABLES]
x, float, normal, media=0, std=1
y, float, uniform, min=0, max=10

[FUNCION]
tipo = expresion
expresion = x + y

[SIMULACION]
numero_escenarios = 1000
semilla_aleatoria = 42
"""
    filepath = tmp_path / "test_model.ini"
    filepath.write_text(content)
    return str(filepath)


# Fixture: archivo de modelo mínimo
@pytest.fixture
def minimal_model_file(tmp_path):
    """Crea un archivo de modelo mínimo."""
    content = """
[METADATA]
nombre = minimal
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x**2

[SIMULACION]
numero_escenarios = 100
"""
    filepath = tmp_path / "minimal.ini"
    filepath.write_text(content)
    return str(filepath)


class TestModelParserInitialization:
    """Tests para inicialización del parser."""

    def test_initialization_with_valid_file(self, valid_model_file):
        """Test: Inicialización con archivo válido."""
        parser = ModelParser(valid_model_file)
        assert parser.filepath.exists()

    def test_initialization_with_nonexistent_file(self):
        """Test: Error al inicializar con archivo inexistente."""
        with pytest.raises(ModelParserError, match="Archivo no encontrado"):
            ModelParser("/path/to/nonexistent/file.ini")


class TestMetadataParsing:
    """Tests para parsing de sección METADATA."""

    def test_parse_metadata_all_fields(self, valid_model_file):
        """Test: Parsear metadata con todos los campos."""
        parser = ModelParser(valid_model_file)
        modelo = parser.parse()

        assert modelo.nombre == "test_modelo"
        assert modelo.version == "1.0"
        assert modelo.descripcion == "Modelo de prueba"
        assert modelo.autor == "Test Suite"
        assert modelo.fecha_creacion == "2025-01-17"

    def test_parse_metadata_minimal(self, minimal_model_file):
        """Test: Parsear metadata con campos mínimos."""
        parser = ModelParser(minimal_model_file)
        modelo = parser.parse()

        assert modelo.nombre == "minimal"
        assert modelo.version == "1.0"
        assert modelo.descripcion == ""
        assert modelo.autor == ""
        assert modelo.fecha_creacion == ""

    def test_parse_metadata_missing_required_field(self, tmp_path):
        """Test: Error al faltar campo requerido."""
        content = """
[METADATA]
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "missing_name.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Campo requerido faltante"):
            parser.parse()


class TestVariablesParsing:
    """Tests para parsing de sección VARIABLES."""

    def test_parse_variables_basic(self, valid_model_file):
        """Test: Parsear variables básicas."""
        parser = ModelParser(valid_model_file)
        modelo = parser.parse()

        assert len(modelo.variables) == 2

        # Primera variable
        var_x = modelo.variables[0]
        assert var_x.nombre == "x"
        assert var_x.tipo == "float"
        assert var_x.distribucion == "normal"
        assert var_x.parametros == {'media': 0.0, 'std': 1.0}

        # Segunda variable
        var_y = modelo.variables[1]
        assert var_y.nombre == "y"
        assert var_y.tipo == "float"
        assert var_y.distribucion == "uniform"
        assert var_y.parametros == {'min': 0.0, 'max': 10.0}

    def test_parse_variable_exponential(self, tmp_path):
        """Test: Parsear variable con distribución exponencial."""
        content = """
[METADATA]
nombre = exp_model
version = 1.0

[VARIABLES]
t, float, exponential, lambda=2.5

[FUNCION]
tipo = expresion
expresion = t

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "exp_model.ini"
        filepath.write_text(content)

        modelo = parse_model_file(str(filepath))
        assert len(modelo.variables) == 1
        var = modelo.variables[0]
        assert var.distribucion == "exponential"
        assert var.parametros == {'lambda': 2.5}

    def test_parse_variable_int_type(self, tmp_path):
        """Test: Parsear variable con tipo int."""
        content = """
[METADATA]
nombre = int_model
version = 1.0

[VARIABLES]
n, int, uniform, min=1, max=100

[FUNCION]
tipo = expresion
expresion = n * 2

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "int_model.ini"
        filepath.write_text(content)

        modelo = parse_model_file(str(filepath))
        var = modelo.variables[0]
        assert var.tipo == "int"

    def test_parse_variables_invalid_type(self, tmp_path):
        """Test: Error con tipo inválido."""
        content = """
[METADATA]
nombre = bad_type
version = 1.0

[VARIABLES]
x, string, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "bad_type.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Tipo.*inválido"):
            parser.parse()

    def test_parse_variables_unsupported_distribution(self, tmp_path):
        """Test: Error con distribución no soportada en Fase 1."""
        content = """
[METADATA]
nombre = bad_dist
version = 1.0

[VARIABLES]
x, float, lognormal, mu=0, sigma=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "bad_dist.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="no soportada en Fase 1"):
            parser.parse()

    def test_parse_variables_invalid_param_format(self, tmp_path):
        """Test: Error con formato de parámetro inválido."""
        content = """
[METADATA]
nombre = bad_param
version = 1.0

[VARIABLES]
x, float, normal, media=0, std

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "bad_param.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Parámetro inválido"):
            parser.parse()

    def test_parse_variables_non_numeric_param(self, tmp_path):
        """Test: Error con valor de parámetro no numérico."""
        content = """
[METADATA]
nombre = bad_value
version = 1.0

[VARIABLES]
x, float, normal, media=abc, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "bad_value.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="no es numérico"):
            parser.parse()

    def test_parse_variables_empty_section(self, tmp_path):
        """Test: Error con sección VARIABLES vacía."""
        content = """
[METADATA]
nombre = empty_vars
version = 1.0

[VARIABLES]

[FUNCION]
tipo = expresion
expresion = 1 + 1

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "empty_vars.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="No se encontraron variables"):
            parser.parse()


class TestFunctionParsing:
    """Tests para parsing de sección FUNCION."""

    def test_parse_function_expresion(self, valid_model_file):
        """Test: Parsear función tipo expresion."""
        parser = ModelParser(valid_model_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == "expresion"
        assert modelo.expresion == "x + y"
        assert modelo.codigo is None

    def test_parse_function_complex_expresion(self, tmp_path):
        """Test: Parsear expresión compleja."""
        content = """
[METADATA]
nombre = complex_expr
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, uniform, min=0, max=10

[FUNCION]
tipo = expresion
expresion = (x**2 + y) / (x + 1)

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "complex.ini"
        filepath.write_text(content)

        modelo = parse_model_file(str(filepath))
        assert modelo.expresion == "(x**2 + y) / (x + 1)"

    def test_parse_function_missing_type(self, tmp_path):
        """Test: Error al faltar campo tipo."""
        content = """
[METADATA]
nombre = no_type
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "no_type.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="'tipo' requerido"):
            parser.parse()

    def test_parse_function_invalid_type(self, tmp_path):
        """Test: Error con tipo de función inválido."""
        content = """
[METADATA]
nombre = bad_func_type
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = lambda
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "bad_func_type.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Tipo de función inválido"):
            parser.parse()

    def test_parse_function_codigo_not_supported(self, tmp_path):
        """Test: Error con tipo codigo en Fase 1."""
        content = """
[METADATA]
nombre = codigo_fase1
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo = def modelo(x): return x**2

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "codigo.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="no soportado en Fase 1"):
            parser.parse()

    def test_parse_function_empty_expresion(self, tmp_path):
        """Test: Error con expresión vacía."""
        content = """
[METADATA]
nombre = empty_expr
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion =

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "empty_expr.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="no puede estar vacía"):
            parser.parse()


class TestSimulationParsing:
    """Tests para parsing de sección SIMULACION."""

    def test_parse_simulation_with_seed(self, valid_model_file):
        """Test: Parsear simulación con semilla."""
        parser = ModelParser(valid_model_file)
        modelo = parser.parse()

        assert modelo.numero_escenarios == 1000
        assert modelo.semilla_aleatoria == 42

    def test_parse_simulation_without_seed(self, minimal_model_file):
        """Test: Parsear simulación sin semilla."""
        parser = ModelParser(minimal_model_file)
        modelo = parser.parse()

        assert modelo.numero_escenarios == 100
        assert modelo.semilla_aleatoria is None

    def test_parse_simulation_missing_numero_escenarios(self, tmp_path):
        """Test: Error al faltar numero_escenarios."""
        content = """
[METADATA]
nombre = no_scenarios
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
"""
        filepath = tmp_path / "no_scenarios.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="'numero_escenarios' requerido"):
            parser.parse()

    def test_parse_simulation_invalid_numero_escenarios(self, tmp_path):
        """Test: Error con numero_escenarios no entero."""
        content = """
[METADATA]
nombre = bad_scenarios
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = abc
"""
        filepath = tmp_path / "bad_scenarios.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="debe ser un entero"):
            parser.parse()

    def test_parse_simulation_zero_escenarios(self, tmp_path):
        """Test: Error con numero_escenarios <= 0."""
        content = """
[METADATA]
nombre = zero_scenarios
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 0
"""
        filepath = tmp_path / "zero.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="debe ser > 0"):
            parser.parse()


class TestMissingSections:
    """Tests para secciones faltantes."""

    def test_missing_metadata_section(self, tmp_path):
        """Test: Error al faltar sección METADATA."""
        content = """
[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = expresion
expresion = x

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "no_metadata.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Secciones faltantes"):
            parser.parse()

    def test_missing_variables_section(self, tmp_path):
        """Test: Error al faltar sección VARIABLES."""
        content = """
[METADATA]
nombre = no_vars
version = 1.0

[FUNCION]
tipo = expresion
expresion = 1 + 1

[SIMULACION]
numero_escenarios = 100
"""
        filepath = tmp_path / "no_vars.ini"
        filepath.write_text(content)

        parser = ModelParser(str(filepath))
        with pytest.raises(ModelParserError, match="Secciones faltantes"):
            parser.parse()


class TestFactoryFunction:
    """Tests para función parse_model_file."""

    def test_parse_model_file_success(self, valid_model_file):
        """Test: Función factory parse con éxito."""
        modelo = parse_model_file(valid_model_file)

        assert isinstance(modelo, Modelo)
        assert modelo.nombre == "test_modelo"
        assert len(modelo.variables) == 2

    def test_parse_model_file_error(self):
        """Test: Función factory propaga errores."""
        with pytest.raises(ModelParserError):
            parse_model_file("/nonexistent/file.ini")


class TestRealWorldModel:
    """Tests con el modelo de ejemplo real del proyecto."""

    def test_parse_ejemplo_simple(self):
        """Test: Parsear modelos/ejemplo_simple.ini."""
        # Asumiendo que estamos en el directorio raíz del proyecto
        filepath = "modelos/ejemplo_simple.ini"

        # Verificar si existe
        if not Path(filepath).exists():
            pytest.skip(f"Archivo {filepath} no encontrado")

        modelo = parse_model_file(filepath)

        # Validar modelo
        assert modelo.nombre == "suma_normal"
        assert modelo.version == "1.0"
        assert len(modelo.variables) == 2
        assert modelo.tipo_funcion == "expresion"
        assert modelo.expresion == "x + y"
        assert modelo.numero_escenarios == 1000
        assert modelo.semilla_aleatoria == 42
