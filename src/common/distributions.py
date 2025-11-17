"""
Generador de valores aleatorios basados en distribuciones de probabilidad.

Soporta múltiples distribuciones para variables estocásticas en simulaciones
Monte Carlo. Fase 1 incluye: Normal, Uniforme, Exponencial.
"""

import numpy as np
from typing import Dict, Any, Union
from scipy import stats


class DistributionError(Exception):
    """Excepción para errores en generación de distribuciones."""
    pass


class DistributionGenerator:
    """
    Generador de valores aleatorios basados en distribuciones de probabilidad.

    Soporta:
    - Fase 1: Normal, Uniforme, Exponencial
    - Fase 3: Lognormal, Triangular, Binomial (futuro)
    """

    # Distribuciones soportadas en Fase 1
    SUPPORTED_DISTRIBUTIONS = {
        'normal', 'uniform', 'exponential'
    }

    def __init__(self, seed: int = None):
        """
        Inicializa el generador de distribuciones.

        Args:
            seed: Semilla para reproducibilidad (opcional)
        """
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def generate(self, distribution: str, params: Dict[str, Any],
                 tipo: str = 'float') -> Union[float, int]:
        """
        Genera un valor aleatorio según la distribución especificada.

        Args:
            distribution: Nombre de la distribución ('normal', 'uniform', etc.)
            params: Parámetros de la distribución
            tipo: Tipo de dato ('float' o 'int')

        Returns:
            Valor aleatorio generado

        Raises:
            DistributionError: Si la distribución no es soportada o
                             los parámetros son inválidos

        Examples:
            >>> gen = DistributionGenerator(seed=42)
            >>> gen.generate('normal', {'media': 0, 'std': 1})
            0.4967141530112327

            >>> gen.generate('uniform', {'min': 0, 'max': 10})
            7.203244934421581
        """
        distribution = distribution.lower()

        if distribution not in self.SUPPORTED_DISTRIBUTIONS:
            raise DistributionError(
                f"Distribución '{distribution}' no soportada. "
                f"Soportadas: {self.SUPPORTED_DISTRIBUTIONS}"
            )

        try:
            # Generar valor según distribución
            if distribution == 'normal':
                value = self._generate_normal(params)
            elif distribution == 'uniform':
                value = self._generate_uniform(params)
            elif distribution == 'exponential':
                value = self._generate_exponential(params)
            else:
                raise DistributionError(f"Distribución '{distribution}' no implementada")

            # Convertir a tipo solicitado
            if tipo == 'int':
                return int(round(value))
            else:
                return float(value)

        except KeyError as e:
            raise DistributionError(
                f"Parámetro faltante para distribución '{distribution}': {e}"
            )
        except (ValueError, TypeError) as e:
            raise DistributionError(
                f"Error en parámetros de '{distribution}': {e}"
            )

    def _generate_normal(self, params: Dict[str, Any]) -> float:
        """
        Genera valor de distribución Normal (Gaussiana).

        Args:
            params: {'media': float, 'std': float}

        Returns:
            Valor aleatorio ~ N(media, std)
        """
        media = float(params['media'])
        std = float(params['std'])

        if std <= 0:
            raise ValueError("Desviación estándar debe ser > 0")

        return np.random.normal(media, std)

    def _generate_uniform(self, params: Dict[str, Any]) -> float:
        """
        Genera valor de distribución Uniforme.

        Args:
            params: {'min': float, 'max': float}

        Returns:
            Valor aleatorio ~ U(min, max)
        """
        min_val = float(params['min'])
        max_val = float(params['max'])

        if min_val >= max_val:
            raise ValueError("min debe ser < max")

        return np.random.uniform(min_val, max_val)

    def _generate_exponential(self, params: Dict[str, Any]) -> float:
        """
        Genera valor de distribución Exponencial.

        Args:
            params: {'lambda': float} o {'scale': float}

        Returns:
            Valor aleatorio ~ Exp(lambda)

        Note:
            Acepta 'lambda' o 'scale' donde scale = 1/lambda
        """
        # scipy.stats usa 'scale' = 1/lambda
        if 'lambda' in params:
            lambda_val = float(params['lambda'])
            if lambda_val <= 0:
                raise ValueError("lambda debe ser > 0")
            scale = 1.0 / lambda_val
        elif 'scale' in params:
            scale = float(params['scale'])
            if scale <= 0:
                raise ValueError("scale debe ser > 0")
        else:
            raise KeyError("Se requiere 'lambda' o 'scale'")

        return np.random.exponential(scale)

    def generate_batch(self, distribution: str, params: Dict[str, Any],
                       size: int, tipo: str = 'float') -> np.ndarray:
        """
        Genera múltiples valores de una distribución eficientemente.

        Args:
            distribution: Nombre de la distribución
            params: Parámetros de la distribución
            size: Cantidad de valores a generar
            tipo: Tipo de dato ('float' o 'int')

        Returns:
            Array numpy con los valores generados

        Examples:
            >>> gen = DistributionGenerator(seed=42)
            >>> values = gen.generate_batch('normal', {'media': 0, 'std': 1}, 1000)
            >>> len(values)
            1000
            >>> abs(values.mean() - 0) < 0.1  # Media cercana a 0
            True
        """
        values = np.array([
            self.generate(distribution, params, tipo)
            for _ in range(size)
        ])
        return values

    def get_distribution_info(self, distribution: str) -> Dict[str, Any]:
        """
        Retorna información sobre una distribución.

        Args:
            distribution: Nombre de la distribución

        Returns:
            Diccionario con info de la distribución
        """
        info = {
            'normal': {
                'nombre': 'Normal (Gaussiana)',
                'parametros': ['media', 'std'],
                'descripcion': 'Distribución simétrica campana de Gauss',
                'ejemplo': "{'media': 0, 'std': 1}"
            },
            'uniform': {
                'nombre': 'Uniforme',
                'parametros': ['min', 'max'],
                'descripcion': 'Probabilidad constante en [min, max]',
                'ejemplo': "{'min': 0, 'max': 10}"
            },
            'exponential': {
                'nombre': 'Exponencial',
                'parametros': ['lambda'],
                'descripcion': 'Distribución de tiempos entre eventos',
                'ejemplo': "{'lambda': 1.5}"
            }
        }

        return info.get(distribution.lower(), {})


# Factory function para conveniencia
def create_generator(seed: int = None) -> DistributionGenerator:
    """
    Crea una instancia de DistributionGenerator.

    Args:
        seed: Semilla para reproducibilidad

    Returns:
        Instancia de DistributionGenerator
    """
    return DistributionGenerator(seed=seed)


__all__ = [
    'DistributionGenerator',
    'DistributionError',
    'create_generator'
]
