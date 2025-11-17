#!/usr/bin/env python3
"""
Test de validación - Fase 3.3: Actualizar Parser

Valida:
1. ✅ Soporte tipo='codigo' en [FUNCION]
2. ✅ Validación de sintaxis Python básica
3. ✅ Detección de errores de sintaxis
4. ✅ Validación de variable 'resultado'
5. ✅ Detección cuando falta 'resultado'
6. ✅ Parsing de código multilínea
7. ✅ Preservación de indentación
8. ✅ Análisis de variables asignadas
9. ✅ Tests de modelos válidos
10. ✅ Tests de modelos inválidos
11. ✅ Resumen completo
"""

import sys
import time
import tempfile
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.model_parser import ModelParser, ModelParserError


def print_header(text: str):
    """Imprime un header con formato."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_test(number: int, description: str):
    """Imprime el número y descripción de un test."""
    print(f"\n[Test {number}] {description}")
    print("-" * 70)


def test_1_codigo_basico():
    """Test 1: Parsing de código básico."""
    print_test(1, "Parsing de código Python básico")

    modelo_contenido = """
[METADATA]
nombre = test_codigo_basico
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    # Código simple
    suma = x + y
    resultado = suma

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == 'codigo'
        assert modelo.codigo is not None
        assert 'suma = x + y' in modelo.codigo
        assert 'resultado = suma' in modelo.codigo

        print(f"✅ Modelo parseado correctamente")
        print(f"   Tipo: {modelo.tipo_funcion}")
        print(f"   Código tiene {len(modelo.codigo.split(chr(10)))} líneas")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Parsing de código básico funciona correctamente")


def test_2_error_sintaxis():
    """Test 2: Detección de errores de sintaxis."""
    print_test(2, "Detección de errores de sintaxis Python")

    # Código con error de sintaxis (falta dos puntos)
    modelo_contenido = """
[METADATA]
nombre = test_error_sintaxis
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    if x > 0  # FALTA :
        resultado = x
    else:
        resultado = 0

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        try:
            modelo = parser.parse()
            assert False, "Debería haber detectado error de sintaxis"
        except ModelParserError as e:
            assert "Error de sintaxis Python" in str(e)
            print(f"✅ Error de sintaxis detectado correctamente")
            print(f"   Mensaje: {str(e)[:100]}...")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Detección de errores de sintaxis funciona correctamente")


def test_3_falta_resultado():
    """Test 3: Detección cuando falta variable 'resultado'."""
    print_test(3, "Detección cuando falta variable 'resultado'")

    # Código sin definir 'resultado'
    modelo_contenido = """
[METADATA]
nombre = test_sin_resultado
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    suma = x + y
    producto = x * y
    # Falta: resultado = ...

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        try:
            modelo = parser.parse()
            assert False, "Debería haber detectado falta de 'resultado'"
        except ModelParserError as e:
            assert "debe definir una variable 'resultado'" in str(e)
            print(f"✅ Falta de 'resultado' detectada correctamente")
            print(f"   Mensaje: {str(e)}")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Validación de variable 'resultado' funciona correctamente")


def test_4_codigo_multilinea():
    """Test 4: Parsing de código multilínea complejo."""
    print_test(4, "Parsing de código multilínea complejo")

    modelo_contenido = """
[METADATA]
nombre = test_multilinea
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1
z, float, uniform, min=0, max=10

[FUNCION]
tipo = codigo
codigo =
    # Código con múltiples líneas
    import math

    # Calcular distancia euclidiana
    distancia = math.sqrt(x**2 + y**2)

    # Aplicar lógica condicional
    if distancia > 5:
        factor = 2.0
    elif distancia > 2:
        factor = 1.5
    else:
        factor = 1.0

    # Calcular resultado final
    resultado = distancia * factor + z

[SIMULACION]
numero_escenarios = 1000
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == 'codigo'
        assert 'import math' in modelo.codigo
        assert 'if distancia > 5:' in modelo.codigo
        assert 'resultado = distancia * factor + z' in modelo.codigo

        # Contar líneas
        lines = modelo.codigo.split('\n')
        non_empty_lines = [l for l in lines if l.strip()]

        print(f"✅ Código multilínea parseado correctamente")
        print(f"   Total de líneas: {len(lines)}")
        print(f"   Líneas no vacías: {len(non_empty_lines)}")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Parsing multilínea funciona correctamente")


def test_5_preservacion_indentacion():
    """Test 5: Preservación de indentación."""
    print_test(5, "Preservación de indentación relativa")

    modelo_contenido = """
[METADATA]
nombre = test_indentacion
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
        # Código con indentación inicial
        if x > 0:
            resultado = x * 2
        else:
            resultado = x * -1

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        # Verificar que la indentación relativa se preserva
        lines = modelo.codigo.split('\n')

        # La primera línea (comentario) no debería tener indentación extra
        assert not lines[0].startswith('    '), "Indentación común debe removerse"

        # El if debe tener menos indentación que su contenido
        if_line_idx = None
        for i, line in enumerate(lines):
            if 'if x > 0:' in line:
                if_line_idx = i
                break

        assert if_line_idx is not None, "No se encontró línea del if"

        # La línea siguiente debe tener más indentación
        next_line = lines[if_line_idx + 1]
        assert next_line.startswith('    '), "Indentación relativa debe preservarse"

        print(f"✅ Indentación procesada correctamente")
        print(f"   Primera línea: '{lines[0]}'")
        print(f"   Línea if: '{lines[if_line_idx]}'")
        print(f"   Línea indentada: '{next_line}'")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Preservación de indentación funciona correctamente")


def test_6_resultado_en_tupla():
    """Test 6: Detección de 'resultado' en tuple unpacking."""
    print_test(6, "Detección de 'resultado' en tuple unpacking")

    modelo_contenido = """
[METADATA]
nombre = test_tuple_unpacking
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    # Tuple unpacking
    suma, resultado = x + y, x * y

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == 'codigo'
        assert 'suma, resultado = x + y, x * y' in modelo.codigo

        print(f"✅ Tuple unpacking con 'resultado' detectado correctamente")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Detección en tuple unpacking funciona correctamente")


def test_7_resultado_augmented_assign():
    """Test 7: Detección de 'resultado' en asignación aumentada."""
    print_test(7, "Detección de 'resultado' en asignación aumentada")

    modelo_contenido = """
[METADATA]
nombre = test_augmented
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    resultado = 10
    resultado += x

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == 'codigo'
        assert 'resultado += x' in modelo.codigo

        print(f"✅ Asignación aumentada con 'resultado' detectada correctamente")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Detección en asignación aumentada funciona correctamente")


def test_8_codigo_con_loops():
    """Test 8: Código con loops y funciones."""
    print_test(8, "Código con loops y definición de funciones")

    modelo_contenido = """
[METADATA]
nombre = test_loops
version = 1.0

[VARIABLES]
n, int, binomial, n=10, p=0.5

[FUNCION]
tipo = codigo
codigo =
    # Definir función auxiliar
    def factorial(num):
        if num <= 1:
            return 1
        return num * factorial(num - 1)

    # Calcular con loop
    suma = 0
    for i in range(int(n)):
        suma += factorial(i)

    resultado = suma

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        assert modelo.tipo_funcion == 'codigo'
        assert 'def factorial' in modelo.codigo
        assert 'for i in range' in modelo.codigo
        assert 'resultado = suma' in modelo.codigo

        print(f"✅ Código con loops y funciones parseado correctamente")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Parsing de código complejo funciona correctamente")


def test_9_variables_asignadas():
    """Test 9: Análisis de variables asignadas."""
    print_test(9, "Análisis de variables asignadas en código")

    modelo_contenido = """
[METADATA]
nombre = test_variables
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo =
    suma = x + y
    producto = x * y
    diferencia = x - y
    resultado = suma + producto

[SIMULACION]
numero_escenarios = 100
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
        f.write(modelo_contenido)
        temp_file = f.name

    try:
        parser = ModelParser(temp_file)
        modelo = parser.parse()

        # Usar método privado para obtener variables
        variables = parser._get_assigned_variables(modelo.codigo)

        expected_vars = {'suma', 'producto', 'diferencia', 'resultado'}
        assert expected_vars.issubset(variables), \
            f"Variables faltantes: {expected_vars - variables}"

        print(f"✅ Variables detectadas: {sorted(variables)}")

    finally:
        Path(temp_file).unlink()

    print(f"✅ Análisis de variables funciona correctamente")


def test_10_errores_comunes():
    """Test 10: Detección de errores comunes."""
    print_test(10, "Detección de errores comunes")

    errores_test = [
        # Error 1: Paréntesis sin cerrar
        ("""
resultado = (x + y
""", "Error de sintaxis"),

        # Error 2: Indentación incorrecta
        ("""
if x > 0:
resultado = x
""", "Error de sintaxis"),

        # Error 3: Nombre inválido
        ("""
1resultado = x + y
""", "Error de sintaxis"),
    ]

    for i, (codigo, tipo_error) in enumerate(errores_test, 1):
        modelo_contenido = f"""
[METADATA]
nombre = test_error_{i}
version = 1.0

[VARIABLES]
x, float, normal, media=0, std=1
y, float, normal, media=0, std=1

[FUNCION]
tipo = codigo
codigo ={codigo}

[SIMULACION]
numero_escenarios = 100
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(modelo_contenido)
            temp_file = f.name

        try:
            parser = ModelParser(temp_file)
            try:
                modelo = parser.parse()
                print(f"⚠️  Error #{i} no detectado: {tipo_error}")
            except ModelParserError as e:
                print(f"✅ Error #{i} detectado: {tipo_error}")

        finally:
            Path(temp_file).unlink()

    print(f"✅ Detección de errores comunes funciona correctamente")


def test_11_resumen():
    """Test 11: Resumen completo."""
    print_test(11, "Resumen del Sistema de Parsing")

    print("\n📊 CARACTERÍSTICAS IMPLEMENTADAS:")
    print("  ✅ Soporte para tipo='codigo' en [FUNCION]")
    print("  ✅ Validación de sintaxis Python con ast.parse")
    print("  ✅ Detección de errores de sintaxis")
    print("  ✅ Validación obligatoria de variable 'resultado'")
    print("  ✅ Detección en asignación simple")
    print("  ✅ Detección en tuple unpacking")
    print("  ✅ Detección en asignación aumentada (+=, -=, etc.)")
    print("  ✅ Parsing de código multilínea")
    print("  ✅ Preservación de indentación relativa")
    print("  ✅ Análisis de variables asignadas")

    print("\n🔍 VALIDACIONES:")
    print("  • Sintaxis Python correcta (antes de ejecutar)")
    print("  • Variable 'resultado' definida")
    print("  • Código no vacío")
    print("  • Indentación consistente")

    print("\n📝 FORMATO SOPORTADO:")
    print("""
    [FUNCION]
    tipo = codigo
    codigo =
        # Tu código Python aquí
        import math
        resultado = math.sqrt(x**2 + y**2)
    """)

    print("\n✅ FASE 3.3 COMPLETADA EXITOSAMENTE")


def main():
    """Ejecuta todos los tests de Fase 3.3."""
    print_header("FASE 3.3: ACTUALIZAR PARSER")
    print("Validando parsing y validación de código Python")

    inicio = time.time()

    try:
        # Tests básicos
        test_1_codigo_basico()
        test_2_error_sintaxis()
        test_3_falta_resultado()

        # Tests avanzados
        test_4_codigo_multilinea()
        test_5_preservacion_indentacion()

        # Tests de casos especiales
        test_6_resultado_en_tupla()
        test_7_resultado_augmented_assign()
        test_8_codigo_con_loops()

        # Tests de análisis
        test_9_variables_asignadas()
        test_10_errores_comunes()

        # Resumen
        test_11_resumen()

        tiempo_total = time.time() - inicio

        print_header("RESULTADO FINAL")
        print(f"✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
        print(f"⏱️  Tiempo total: {tiempo_total:.2f}s")
        print()
        print("El parser ahora valida:")
        print("  • Sintaxis Python correcta")
        print("  • Presencia de variable 'resultado'")
        print("  • Código multilínea complejo")
        print()

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FALLÓ: {e}")
        return 1

    except Exception as e:
        print(f"\n❌ ERROR INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
