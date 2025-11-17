#!/usr/bin/env python3
"""
Test de validación - Fase 3.2: Distribuciones Adicionales

Valida las 6 distribuciones soportadas:
1. ✅ Normal (Fase 1)
2. ✅ Uniforme (Fase 1)
3. ✅ Exponencial (Fase 1)
4. ✅ Lognormal (Fase 3.2)
5. ✅ Triangular (Fase 3.2)
6. ✅ Binomial (Fase 3.2)
"""

import sys
import time
import numpy as np
from pathlib import Path
from scipy import stats

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.common.distributions import DistributionGenerator, DistributionError


def print_header(text: str):
    """Imprime un header con formato."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_test(number: int, description: str):
    """Imprime el número y descripción de un test."""
    print(f"\n[Test {number}] {description}")
    print("-" * 70)


def test_1_normal():
    """Test 1: Distribución Normal."""
    print_test(1, "Distribución Normal ~ N(0, 1)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra grande
    n_samples = 10000
    values = gen.generate_batch('normal', {'media': 0, 'std': 1}, n_samples)

    # Validar estadísticas
    media = np.mean(values)
    std = np.std(values)

    print(f"  Muestras: {n_samples}")
    print(f"  Media esperada: 0.0, obtenida: {media:.4f}")
    print(f"  Std esperada: 1.0, obtenida: {std:.4f}")

    assert abs(media - 0.0) < 0.05, f"Media fuera de rango: {media}"
    assert abs(std - 1.0) < 0.05, f"Std fuera de rango: {std}"

    # Test de normalidad (Shapiro-Wilk)
    # Para muestras grandes usar solo subset
    subset = values[:5000]
    _, p_value = stats.shapiro(subset)

    print(f"  Test Shapiro-Wilk: p-value = {p_value:.4f}")

    if p_value > 0.05:
        print(f"✅ Distribución Normal validada (p > 0.05)")
    else:
        print(f"⚠️  Advertencia: p-value < 0.05, pero aceptable para muestra grande")

    print(f"✅ Distribución Normal funciona correctamente")


def test_2_uniform():
    """Test 2: Distribución Uniforme."""
    print_test(2, "Distribución Uniforme ~ U(0, 10)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra
    n_samples = 10000
    values = gen.generate_batch('uniform', {'min': 0, 'max': 10}, n_samples)

    # Validar estadísticas
    media = np.mean(values)
    media_teorica = (0 + 10) / 2.0  # 5.0
    varianza = np.var(values)
    varianza_teorica = ((10 - 0) ** 2) / 12.0  # 8.333...

    print(f"  Muestras: {n_samples}")
    print(f"  Media esperada: {media_teorica:.4f}, obtenida: {media:.4f}")
    print(f"  Varianza esperada: {varianza_teorica:.4f}, obtenida: {varianza:.4f}")

    assert abs(media - media_teorica) < 0.1, f"Media fuera de rango: {media}"
    assert abs(varianza - varianza_teorica) < 0.5, f"Varianza fuera de rango: {varianza}"

    # Validar rango
    assert np.min(values) >= 0, f"Valor mínimo < 0: {np.min(values)}"
    assert np.max(values) <= 10, f"Valor máximo > 10: {np.max(values)}"

    # Test de uniformidad (Kolmogorov-Smirnov)
    ks_stat, ks_p = stats.kstest(values, 'uniform', args=(0, 10))

    print(f"  Test KS: p-value = {ks_p:.4f}")

    if ks_p > 0.05:
        print(f"✅ Distribución Uniforme validada (p > 0.05)")
    else:
        print(f"⚠️  Advertencia: p-value < 0.05")

    print(f"✅ Distribución Uniforme funciona correctamente")


def test_3_exponential():
    """Test 3: Distribución Exponencial."""
    print_test(3, "Distribución Exponencial ~ Exp(λ=1.5)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra
    n_samples = 10000
    lambda_val = 1.5
    values = gen.generate_batch('exponential', {'lambda': lambda_val}, n_samples)

    # Validar estadísticas
    media = np.mean(values)
    media_teorica = 1.0 / lambda_val  # 0.6667
    std = np.std(values)
    std_teorica = 1.0 / lambda_val  # 0.6667

    print(f"  Muestras: {n_samples}")
    print(f"  λ: {lambda_val}")
    print(f"  Media esperada: {media_teorica:.4f}, obtenida: {media:.4f}")
    print(f"  Std esperada: {std_teorica:.4f}, obtenida: {std:.4f}")

    assert abs(media - media_teorica) < 0.05, f"Media fuera de rango: {media}"
    assert abs(std - std_teorica) < 0.05, f"Std fuera de rango: {std}"

    # Validar que todos los valores son positivos
    assert np.min(values) >= 0, f"Valor mínimo < 0: {np.min(values)}"

    print(f"✅ Distribución Exponencial funciona correctamente")


def test_4_lognormal():
    """Test 4: Distribución Lognormal."""
    print_test(4, "Distribución Lognormal ~ LogNormal(μ=0, σ=1)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra
    n_samples = 10000
    mu = 0
    sigma = 1
    values = gen.generate_batch('lognormal', {'mu': mu, 'sigma': sigma}, n_samples)

    # Validar estadísticas
    # Para lognormal: media = exp(mu + sigma^2/2)
    media_teorica = np.exp(mu + sigma**2 / 2)  # exp(0.5) = 1.6487
    media = np.mean(values)

    # Varianza = (exp(sigma^2) - 1) * exp(2*mu + sigma^2)
    varianza_teorica = (np.exp(sigma**2) - 1) * np.exp(2*mu + sigma**2)
    varianza = np.var(values)

    print(f"  Muestras: {n_samples}")
    print(f"  μ: {mu}, σ: {sigma}")
    print(f"  Media esperada: {media_teorica:.4f}, obtenida: {media:.4f}")
    print(f"  Varianza esperada: {varianza_teorica:.4f}, obtenida: {varianza:.4f}")

    assert abs(media - media_teorica) < 0.2, f"Media fuera de rango: {media}"
    assert abs(varianza - varianza_teorica) < 1.0, f"Varianza fuera de rango: {varianza}"

    # Validar que todos los valores son positivos
    assert np.min(values) > 0, f"Lognormal debe ser > 0, obtenido min: {np.min(values)}"

    # Validar que el log de los valores sigue una distribución normal
    log_values = np.log(values)
    log_media = np.mean(log_values)
    log_std = np.std(log_values)

    print(f"  Log(valores) - Media: {log_media:.4f} (esperado {mu})")
    print(f"  Log(valores) - Std: {log_std:.4f} (esperado {sigma})")

    assert abs(log_media - mu) < 0.1, f"Log media fuera de rango: {log_media}"
    assert abs(log_std - sigma) < 0.1, f"Log std fuera de rango: {log_std}"

    print(f"✅ Distribución Lognormal funciona correctamente")


def test_5_triangular():
    """Test 5: Distribución Triangular."""
    print_test(5, "Distribución Triangular ~ Tri(0, 5, 10)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra
    n_samples = 10000
    left = 0
    mode = 5
    right = 10
    values = gen.generate_batch(
        'triangular',
        {'left': left, 'mode': mode, 'right': right},
        n_samples
    )

    # Validar estadísticas
    # Media = (a + b + c) / 3
    media_teorica = (left + mode + right) / 3.0  # 5.0
    media = np.mean(values)

    print(f"  Muestras: {n_samples}")
    print(f"  Parámetros: left={left}, mode={mode}, right={right}")
    print(f"  Media esperada: {media_teorica:.4f}, obtenida: {media:.4f}")

    assert abs(media - media_teorica) < 0.1, f"Media fuera de rango: {media}"

    # Validar rango
    assert np.min(values) >= left, f"Valor mínimo < left: {np.min(values)}"
    assert np.max(values) <= right, f"Valor máximo > right: {np.max(values)}"

    # Contar valores cerca del mode (debería haber más frecuencia)
    # Dividir en bins y verificar que el bin del mode tiene más valores
    bins = np.linspace(left, right, 11)
    hist, _ = np.histogram(values, bins=bins)
    mode_bin_index = 5  # El bin central para mode=5
    max_bin_index = np.argmax(hist)

    print(f"  Bin con más frecuencia: índice {max_bin_index} (esperado ~{mode_bin_index})")

    # El bin con más frecuencia debería estar cerca del mode
    assert abs(max_bin_index - mode_bin_index) <= 1, \
        f"Pico no está cerca del mode: bin {max_bin_index} vs esperado {mode_bin_index}"

    print(f"✅ Distribución Triangular funciona correctamente")


def test_6_binomial():
    """Test 6: Distribución Binomial."""
    print_test(6, "Distribución Binomial ~ Bin(n=10, p=0.5)")

    gen = DistributionGenerator(seed=42)

    # Generar muestra
    n_samples = 10000
    n = 10
    p = 0.5
    values = gen.generate_batch('binomial', {'n': n, 'p': p}, n_samples)

    # Validar estadísticas
    # Media = n * p
    media_teorica = n * p  # 5.0
    media = np.mean(values)

    # Varianza = n * p * (1 - p)
    varianza_teorica = n * p * (1 - p)  # 2.5
    varianza = np.var(values)

    print(f"  Muestras: {n_samples}")
    print(f"  Parámetros: n={n}, p={p}")
    print(f"  Media esperada: {media_teorica:.4f}, obtenida: {media:.4f}")
    print(f"  Varianza esperada: {varianza_teorica:.4f}, obtenida: {varianza:.4f}")

    assert abs(media - media_teorica) < 0.1, f"Media fuera de rango: {media}"
    assert abs(varianza - varianza_teorica) < 0.2, f"Varianza fuera de rango: {varianza}"

    # Validar rango (debe estar entre 0 y n)
    assert np.min(values) >= 0, f"Valor mínimo < 0: {np.min(values)}"
    assert np.max(values) <= n, f"Valor máximo > n: {np.max(values)}"

    # Validar que todos son enteros
    assert np.all(values == np.floor(values)), "Binomial debe retornar enteros"

    print(f"✅ Distribución Binomial funciona correctamente")


def test_7_validacion_parametros():
    """Test 7: Validación de parámetros inválidos."""
    print_test(7, "Validación de parámetros inválidos")

    gen = DistributionGenerator(seed=42)

    # Test 7a: Normal con std negativo
    try:
        gen.generate('normal', {'media': 0, 'std': -1})
        assert False, "Debería lanzar error con std < 0"
    except (DistributionError, ValueError) as e:
        print(f"✅ Normal con std < 0 bloqueado: {e}")

    # Test 7b: Uniform con min >= max
    try:
        gen.generate('uniform', {'min': 10, 'max': 5})
        assert False, "Debería lanzar error con min >= max"
    except (DistributionError, ValueError) as e:
        print(f"✅ Uniform con min >= max bloqueado: {e}")

    # Test 7c: Exponential con lambda <= 0
    try:
        gen.generate('exponential', {'lambda': -1})
        assert False, "Debería lanzar error con lambda <= 0"
    except (DistributionError, ValueError) as e:
        print(f"✅ Exponential con lambda <= 0 bloqueado: {e}")

    # Test 7d: Lognormal con sigma <= 0
    try:
        gen.generate('lognormal', {'mu': 0, 'sigma': -1})
        assert False, "Debería lanzar error con sigma <= 0"
    except (DistributionError, ValueError) as e:
        print(f"✅ Lognormal con sigma <= 0 bloqueado: {e}")

    # Test 7e: Triangular con left > mode
    try:
        gen.generate('triangular', {'left': 10, 'mode': 5, 'right': 15})
        assert False, "Debería lanzar error con left > mode"
    except (DistributionError, ValueError) as e:
        print(f"✅ Triangular con left > mode bloqueado: {e}")

    # Test 7f: Binomial con p fuera de rango
    try:
        gen.generate('binomial', {'n': 10, 'p': 1.5})
        assert False, "Debería lanzar error con p > 1"
    except (DistributionError, ValueError) as e:
        print(f"✅ Binomial con p > 1 bloqueado: {e}")

    print(f"✅ Validación de parámetros funciona correctamente")


def test_8_distribuciones_no_soportadas():
    """Test 8: Distribuciones no soportadas."""
    print_test(8, "Distribuciones no soportadas")

    gen = DistributionGenerator(seed=42)

    distribuciones_invalidas = [
        'poisson', 'gamma', 'beta', 'chi2', 'weibull'
    ]

    for dist in distribuciones_invalidas:
        try:
            gen.generate(dist, {})
            assert False, f"Debería lanzar error para distribución '{dist}'"
        except DistributionError as e:
            print(f"✅ Distribución '{dist}' bloqueada correctamente")

    print(f"✅ Rechazo de distribuciones no soportadas funciona correctamente")


def test_9_tipos_int_vs_float():
    """Test 9: Tipos int vs float."""
    print_test(9, "Tipos int vs float")

    gen = DistributionGenerator(seed=42)

    # Test 9a: Normal como float
    value_float = gen.generate('normal', {'media': 5, 'std': 1}, tipo='float')
    assert isinstance(value_float, float), f"Esperado float, obtenido {type(value_float)}"
    print(f"✅ Normal como float: {value_float:.4f}")

    # Test 9b: Normal como int
    value_int = gen.generate('normal', {'media': 5, 'std': 1}, tipo='int')
    assert isinstance(value_int, (int, np.integer)), f"Esperado int, obtenido {type(value_int)}"
    print(f"✅ Normal como int: {value_int}")

    # Test 9c: Binomial como int
    value_bin_int = gen.generate('binomial', {'n': 10, 'p': 0.5}, tipo='int')
    assert isinstance(value_bin_int, (int, np.integer)), f"Esperado int, obtenido {type(value_bin_int)}"
    print(f"✅ Binomial como int: {value_bin_int}")

    print(f"✅ Conversión de tipos funciona correctamente")


def test_10_reproducibilidad():
    """Test 10: Reproducibilidad con seed."""
    print_test(10, "Reproducibilidad con seed")

    # Generador 1 con seed=42
    gen1 = DistributionGenerator(seed=42)
    values1 = [gen1.generate('normal', {'media': 0, 'std': 1}) for _ in range(10)]

    # Generador 2 con mismo seed
    gen2 = DistributionGenerator(seed=42)
    values2 = [gen2.generate('normal', {'media': 0, 'std': 1}) for _ in range(10)]

    # Deben ser idénticos
    for i, (v1, v2) in enumerate(zip(values1, values2)):
        assert abs(v1 - v2) < 1e-10, f"Valores difieren en índice {i}: {v1} vs {v2}"

    print(f"✅ Primer valor gen1: {values1[0]:.6f}")
    print(f"✅ Primer valor gen2: {values2[0]:.6f}")
    print(f"✅ Reproducibilidad con seed funciona correctamente")


def test_11_generate_batch():
    """Test 11: Generación batch."""
    print_test(11, "Generación batch eficiente")

    gen = DistributionGenerator(seed=42)

    # Test batch para cada distribución
    distributions = [
        ('normal', {'media': 0, 'std': 1}),
        ('uniform', {'min': 0, 'max': 10}),
        ('exponential', {'lambda': 1.5}),
        ('lognormal', {'mu': 0, 'sigma': 1}),
        ('triangular', {'left': 0, 'mode': 5, 'right': 10}),
        ('binomial', {'n': 10, 'p': 0.5}),
    ]

    for dist_name, params in distributions:
        values = gen.generate_batch(dist_name, params, size=1000)
        assert len(values) == 1000, f"Esperado 1000 valores, obtenido {len(values)}"
        assert isinstance(values, np.ndarray), f"Esperado np.ndarray, obtenido {type(values)}"
        print(f"✅ Batch para '{dist_name}': {len(values)} valores")

    print(f"✅ Generación batch funciona correctamente")


def test_12_info_distribuciones():
    """Test 12: Información de distribuciones."""
    print_test(12, "Información de distribuciones")

    gen = DistributionGenerator()

    distribuciones = [
        'normal', 'uniform', 'exponential',
        'lognormal', 'triangular', 'binomial'
    ]

    for dist in distribuciones:
        info = gen.get_distribution_info(dist)
        assert 'nombre' in info, f"Falta 'nombre' en info de {dist}"
        assert 'parametros' in info, f"Falta 'parametros' en info de {dist}"
        assert 'descripcion' in info, f"Falta 'descripcion' en info de {dist}"
        assert 'ejemplo' in info, f"Falta 'ejemplo' en info de {dist}"

        print(f"✅ {dist:12} - {info['nombre']}")
        print(f"   Parámetros: {', '.join(info['parametros'])}")
        print(f"   Ejemplo: {info['ejemplo']}")

    print(f"\n✅ Información de distribuciones disponible")


def test_13_resumen():
    """Test 13: Resumen completo."""
    print_test(13, "Resumen del Sistema de Distribuciones")

    print("\n📊 DISTRIBUCIONES SOPORTADAS:")
    print("  Fase 1:")
    print("    1. Normal(media, std) - Distribución Gaussiana")
    print("    2. Uniform(min, max) - Distribución Uniforme")
    print("    3. Exponential(lambda) - Tiempos entre eventos")
    print("\n  Fase 3.2 (NUEVAS):")
    print("    4. Lognormal(mu, sigma) - Variable cuyo log es normal")
    print("    5. Triangular(left, mode, right) - Distribución triangular")
    print("    6. Binomial(n, p) - Número de éxitos en n ensayos")

    print("\n✅ FASE 3.2 COMPLETADA EXITOSAMENTE")
    print("\nTodas las 6 distribuciones están funcionando correctamente.")


def main():
    """Ejecuta todos los tests de Fase 3.2."""
    print_header("FASE 3.2: DISTRIBUCIONES ADICIONALES")
    print("Validando las 6 distribuciones soportadas")

    inicio = time.time()

    try:
        # Tests de distribuciones Fase 1
        test_1_normal()
        test_2_uniform()
        test_3_exponential()

        # Tests de nuevas distribuciones Fase 3.2
        test_4_lognormal()
        test_5_triangular()
        test_6_binomial()

        # Tests de validación
        test_7_validacion_parametros()
        test_8_distribuciones_no_soportadas()
        test_9_tipos_int_vs_float()
        test_10_reproducibilidad()
        test_11_generate_batch()
        test_12_info_distribuciones()

        # Resumen
        test_13_resumen()

        tiempo_total = time.time() - inicio

        print_header("RESULTADO FINAL")
        print(f"✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
        print(f"⏱️  Tiempo total: {tiempo_total:.2f}s")
        print()
        print("Las 6 distribuciones están funcionando correctamente:")
        print("  • Normal, Uniform, Exponential (Fase 1)")
        print("  • Lognormal, Triangular, Binomial (Fase 3.2)")
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
