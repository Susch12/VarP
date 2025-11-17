"""
Dashboard para monitoreo en tiempo real de simulación Monte Carlo.

Componentes:
- DataManager: Gestor de datos en background que consume estadísticas de RabbitMQ
- MonteCarloDashboard: Aplicación Dash con visualización en tiempo real
"""

from src.dashboard.data_manager import DataManager
from src.dashboard.app import MonteCarloDashboard, create_dashboard

__all__ = [
    'DataManager',
    'MonteCarloDashboard',
    'create_dashboard'
]
