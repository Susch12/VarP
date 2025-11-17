"""
Tests para el generador de distribuciones de probabilidad.
"""

import pytest
import numpy as np
from src.common.distributions import (
    DistributionGenerator,
    DistributionError,
    create_generator
)


class TestDistributionGenerator:
    """Tests para la clase DistributionGenerator."""

    def test_initialization_with_seed(self):
        """Test: Inicialización con semilla para reproducibilidad."""
        gen1 = DistributionGenerator(seed=42)
        gen2 = DistributionGenerator(seed=42)

        val1 = gen1.generate('normal', {'media': 0, 'std': 1})
        val2 = gen2.generate('normal', {'media': 0, 'std': 1})

        assert val1 == val2, "Misma semilla debe generar mismo valor"

    def test_initialization_without_seed(self):
        """Test: Inicialización sin semilla genera valores diferentes."""
        gen1 = DistributionGenerator()
        gen2 = DistributionGenerator()

        vals1 = [gen1.generate('normal', {'media': 0, 'std': 1}) for _ in range(10)]
        vals2 = [gen2.generate('normal', {'media': 0, 'std': 1}) for _ in range(10)]

        # Es extremadamente improbable que sean iguales
        assert vals1 != vals2, "Sin semilla debe generar valores diferentes"


class TestNormalDistribution:
    """Tests para distribución Normal."""

    def test_generate_normal_basic(self):
        """Test: Generación básica de distribución normal."""
        gen = DistributionGenerator(seed=42)
        value = gen.generate('normal', {'media': 0, 'std': 1})

        assert isinstance(value, float)
        assert -5 < value < 5  # 99.7% de valores están en ±3 std

    def test_generate_normal_mean_std(self):
        """Test: Verificar media y std de muestra grande."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('normal', {'media': 10, 'std': 2}, 10000)

        mean = np.mean(values)
        std = np.std(values)

        assert abs(mean - 10) < 0.1, f"Media esperada ~10, obtenida {mean}"
        assert abs(std - 2) < 0.1, f"Std esperada ~2, obtenida {std}"

    def test_generate_normal_invalid_std(self):
        """Test: Error con desviación estándar inválida."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="Desviación estándar"):
            gen.generate('normal', {'media': 0, 'std': 0})

        with pytest.raises(DistributionError, match="Desviación estándar"):
            gen.generate('normal', {'media': 0, 'std': -1})

    def test_generate_normal_missing_params(self):
        """Test: Error con parámetros faltantes."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="Parámetro faltante"):
            gen.generate('normal', {'media': 0})  # Falta 'std'

        with pytest.raises(DistributionError, match="Parámetro faltante"):
            gen.generate('normal', {'std': 1})  # Falta 'media'


class TestUniformDistribution:
    """Tests para distribución Uniforme."""

    def test_generate_uniform_basic(self):
        """Test: Generación básica de distribución uniforme."""
        gen = DistributionGenerator(seed=42)
        value = gen.generate('uniform', {'min': 0, 'max': 10})

        assert isinstance(value, float)
        assert 0 <= value <= 10

    def test_generate_uniform_range(self):
        """Test: Verificar que valores estén en rango."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('uniform', {'min': -5, 'max': 5}, 1000)

        assert all(-5 <= v <= 5 for v in values)
        assert min(values) < -4  # Debe explorar todo el rango
        assert max(values) > 4

    def test_generate_uniform_mean(self):
        """Test: Media de uniforme debe ser (min+max)/2."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('uniform', {'min': 0, 'max': 10}, 10000)

        mean = np.mean(values)
        expected_mean = 5.0

        assert abs(mean - expected_mean) < 0.1, f"Media esperada ~5, obtenida {mean}"

    def test_generate_uniform_invalid_range(self):
        """Test: Error con rango inválido."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="min debe ser < max"):
            gen.generate('uniform', {'min': 10, 'max': 5})

        with pytest.raises(DistributionError, match="min debe ser < max"):
            gen.generate('uniform', {'min': 5, 'max': 5})

    def test_generate_uniform_missing_params(self):
        """Test: Error con parámetros faltantes."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="Parámetro faltante"):
            gen.generate('uniform', {'min': 0})  # Falta 'max'


class TestExponentialDistribution:
    """Tests para distribución Exponencial."""

    def test_generate_exponential_basic(self):
        """Test: Generación básica de distribución exponencial."""
        gen = DistributionGenerator(seed=42)
        value = gen.generate('exponential', {'lambda': 1.0})

        assert isinstance(value, float)
        assert value >= 0  # Exponencial solo valores positivos

    def test_generate_exponential_with_lambda(self):
        """Test: Generación usando parámetro lambda."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('exponential', {'lambda': 2.0}, 10000)

        mean = np.mean(values)
        expected_mean = 1.0 / 2.0  # E[X] = 1/lambda

        assert abs(mean - expected_mean) < 0.02, \
            f"Media esperada ~{expected_mean}, obtenida {mean}"

    def test_generate_exponential_with_scale(self):
        """Test: Generación usando parámetro scale."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('exponential', {'scale': 0.5}, 10000)

        mean = np.mean(values)
        expected_mean = 0.5  # E[X] = scale

        assert abs(mean - expected_mean) < 0.02, \
            f"Media esperada ~{expected_mean}, obtenida {mean}"

    def test_generate_exponential_positive_values(self):
        """Test: Todos los valores deben ser positivos."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('exponential', {'lambda': 1.5}, 1000)

        assert all(v >= 0 for v in values), "Exponencial debe generar valores >= 0"

    def test_generate_exponential_invalid_lambda(self):
        """Test: Error con lambda inválida."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="lambda debe ser > 0"):
            gen.generate('exponential', {'lambda': 0})

        with pytest.raises(DistributionError, match="lambda debe ser > 0"):
            gen.generate('exponential', {'lambda': -1})

    def test_generate_exponential_missing_params(self):
        """Test: Error con parámetros faltantes."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="Se requiere 'lambda' o 'scale'"):
            gen.generate('exponential', {})


class TestTypeConversion:
    """Tests para conversión de tipos."""

    def test_generate_float_type(self):
        """Test: Generación con tipo float (default)."""
        gen = DistributionGenerator(seed=42)
        value = gen.generate('normal', {'media': 0, 'std': 1}, tipo='float')

        assert isinstance(value, float)

    def test_generate_int_type(self):
        """Test: Generación con tipo int."""
        gen = DistributionGenerator(seed=42)
        value = gen.generate('normal', {'media': 10, 'std': 1}, tipo='int')

        assert isinstance(value, int)

    def test_generate_int_rounding(self):
        """Test: Conversión a int redondea correctamente."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('uniform', {'min': 0, 'max': 10}, 100, tipo='int')

        assert all(isinstance(v, (int, np.integer)) for v in values)
        assert all(0 <= v <= 10 for v in values)


class TestBatchGeneration:
    """Tests para generación en batch."""

    def test_generate_batch_size(self):
        """Test: Batch genera cantidad correcta de valores."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('normal', {'media': 0, 'std': 1}, 100)

        assert len(values) == 100

    def test_generate_batch_returns_array(self):
        """Test: Batch retorna numpy array."""
        gen = DistributionGenerator(seed=42)
        values = gen.generate_batch('normal', {'media': 0, 'std': 1}, 50)

        assert isinstance(values, np.ndarray)

    def test_generate_batch_reproducible(self):
        """Test: Batch con misma semilla es reproducible."""
        gen1 = DistributionGenerator(seed=42)
        gen2 = DistributionGenerator(seed=42)

        batch1 = gen1.generate_batch('uniform', {'min': 0, 'max': 1}, 50)
        batch2 = gen2.generate_batch('uniform', {'min': 0, 'max': 1}, 50)

        assert np.array_equal(batch1, batch2)


class TestUnsupportedDistribution:
    """Tests para distribuciones no soportadas."""

    def test_unsupported_distribution(self):
        """Test: Error al usar distribución no soportada."""
        gen = DistributionGenerator()

        with pytest.raises(DistributionError, match="no soportada"):
            gen.generate('lognormal', {'mu': 0, 'sigma': 1})  # Fase 3

        with pytest.raises(DistributionError, match="no soportada"):
            gen.generate('beta', {'alpha': 2, 'beta': 5})


class TestDistributionInfo:
    """Tests para información de distribuciones."""

    def test_get_normal_info(self):
        """Test: Obtener info de distribución normal."""
        gen = DistributionGenerator()
        info = gen.get_distribution_info('normal')

        assert 'nombre' in info
        assert 'parametros' in info
        assert info['parametros'] == ['media', 'std']

    def test_get_uniform_info(self):
        """Test: Obtener info de distribución uniforme."""
        gen = DistributionGenerator()
        info = gen.get_distribution_info('uniform')

        assert 'nombre' in info
        assert 'parametros' in info
        assert info['parametros'] == ['min', 'max']

    def test_get_exponential_info(self):
        """Test: Obtener info de distribución exponencial."""
        gen = DistributionGenerator()
        info = gen.get_distribution_info('exponential')

        assert 'nombre' in info
        assert 'parametros' in info
        assert 'lambda' in info['parametros']

    def test_get_unknown_distribution_info(self):
        """Test: Info de distribución desconocida retorna dict vacío."""
        gen = DistributionGenerator()
        info = gen.get_distribution_info('unknown')

        assert info == {}


class TestFactoryFunction:
    """Tests para función factory."""

    def test_create_generator(self):
        """Test: Factory crea instancia correcta."""
        gen = create_generator(seed=42)

        assert isinstance(gen, DistributionGenerator)
        assert gen.seed == 42

    def test_create_generator_without_seed(self):
        """Test: Factory sin semilla."""
        gen = create_generator()

        assert isinstance(gen, DistributionGenerator)
        assert gen.seed is None
