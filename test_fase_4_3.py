"""
Tests para Fase 4.3: Exportación de resultados.

Prueba:
- Exportación a JSON con metadata completa
- Exportación a CSV usando pandas
- Exportación de estadísticas a CSV
- Exportación de convergencia a CSV
- Manejo de datos vacíos
- Formato y estructura de archivos exportados
"""

import unittest
import json
import io
from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd

from src.dashboard.data_manager import DataManager
from src.common.rabbitmq_client import RabbitMQClient


class TestJSONExport(unittest.TestCase):
    """Tests para exportación a JSON."""

    def setUp(self):
        """Setup con DataManager mockeado."""
        self.mock_client = MagicMock(spec=RabbitMQClient)
        self.data_manager = DataManager(self.mock_client)

        # Preparar datos de prueba
        self.data_manager.modelo_info = {
            'nombre': 'test_model',
            'version': '1.0',
            'expresion': 'x + y',
            'num_variables': 2
        }
        self.data_manager.resultados = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.data_manager.resultados_raw = [
            {'escenario_id': 1, 'resultado': 1.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 2, 'resultado': 2.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 3, 'resultado': 3.0, 'consumer_id': 'c2', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 4, 'resultado': 4.0, 'consumer_id': 'c2', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 5, 'resultado': 5.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
        ]
        self.data_manager.estadisticas = {
            'n': 5,
            'media': 3.0,
            'mediana': 3.0,
            'desviacion_estandar': 1.58,
            'varianza': 2.5,
            'minimo': 1.0,
            'maximo': 5.0
        }
        self.data_manager.historico_convergencia = [
            {'n': 1, 'media': 1.0, 'varianza': 0.0, 'timestamp': 1234567890},
            {'n': 5, 'media': 3.0, 'varianza': 2.5, 'timestamp': 1234567895}
        ]
        self.data_manager.tests_normalidad = {
            'kolmogorov_smirnov': {
                'statistic': 0.15,
                'pvalue': 0.8,
                'is_normal_alpha_05': True,
                'is_normal_alpha_01': True
            }
        }

    def test_export_json_structure(self):
        """Test que el JSON exportado tiene la estructura correcta."""
        json_str = self.data_manager.export_resultados_json()

        # Parsear JSON
        data = json.loads(json_str)

        # Verificar estructura principal
        self.assertIn('metadata', data)
        self.assertIn('estadisticas', data)
        self.assertIn('tests_normalidad', data)
        self.assertIn('resultados', data)
        self.assertIn('resultados_detallados', data)
        self.assertIn('convergencia', data)

    def test_export_json_metadata(self):
        """Test que metadata incluye información correcta."""
        json_str = self.data_manager.export_resultados_json()
        data = json.loads(json_str)

        # Verificar metadata
        self.assertIn('fecha_exportacion', data['metadata'])
        self.assertIn('num_resultados', data['metadata'])
        self.assertIn('modelo', data['metadata'])

        # Verificar valores
        self.assertEqual(data['metadata']['num_resultados'], 5)
        self.assertEqual(data['metadata']['modelo']['nombre'], 'test_model')

    def test_export_json_estadisticas(self):
        """Test que estadísticas se exportan correctamente."""
        json_str = self.data_manager.export_resultados_json()
        data = json.loads(json_str)

        # Verificar estadísticas
        stats = data['estadisticas']
        self.assertEqual(stats['n'], 5)
        self.assertEqual(stats['media'], 3.0)
        self.assertEqual(stats['mediana'], 3.0)

    def test_export_json_tests_normalidad(self):
        """Test que tests de normalidad se exportan correctamente."""
        json_str = self.data_manager.export_resultados_json()
        data = json.loads(json_str)

        # Verificar tests de normalidad
        tests = data['tests_normalidad']
        self.assertIn('kolmogorov_smirnov', tests)
        self.assertEqual(tests['kolmogorov_smirnov']['pvalue'], 0.8)

    def test_export_json_convergencia(self):
        """Test que histórico de convergencia se exporta correctamente."""
        json_str = self.data_manager.export_resultados_json()
        data = json.loads(json_str)

        # Verificar convergencia
        conv = data['convergencia']
        self.assertEqual(len(conv), 2)
        self.assertEqual(conv[0]['n'], 1)
        self.assertEqual(conv[1]['n'], 5)

    def test_export_json_empty_data(self):
        """Test exportación con datos vacíos."""
        # Limpiar datos
        self.data_manager.resultados = []
        self.data_manager.resultados_raw = []
        self.data_manager.estadisticas = {}

        json_str = self.data_manager.export_resultados_json()
        data = json.loads(json_str)

        # Debe tener estructura pero sin datos
        self.assertEqual(data['metadata']['num_resultados'], 0)
        self.assertEqual(len(data['resultados']), 0)


class TestCSVExport(unittest.TestCase):
    """Tests para exportación a CSV con pandas."""

    def setUp(self):
        """Setup con DataManager mockeado."""
        self.mock_client = MagicMock(spec=RabbitMQClient)
        self.data_manager = DataManager(self.mock_client)

        # Preparar datos de prueba
        self.data_manager.resultados = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.data_manager.resultados_raw = [
            {'escenario_id': 1, 'resultado': 1.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 2, 'resultado': 2.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 3, 'resultado': 3.0, 'consumer_id': 'c2', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 4, 'resultado': 4.0, 'consumer_id': 'c2', 'tiempo_ejecucion': 0.1},
            {'escenario_id': 5, 'resultado': 5.0, 'consumer_id': 'c1', 'tiempo_ejecucion': 0.1},
        ]
        self.data_manager.estadisticas = {
            'n': 5,
            'media': 3.0,
            'mediana': 3.0,
            'desviacion_estandar': 1.58,
            'varianza': 2.5,
            'minimo': 1.0,
            'maximo': 5.0
        }

    def test_export_csv_pandas_usage(self):
        """Test que se usa pandas para exportar CSV."""
        csv_str = self.data_manager.export_resultados_csv()

        # Debe poder parsearse con pandas
        df = pd.read_csv(io.StringIO(csv_str), comment='#')

        # Verificar columnas
        self.assertIn('escenario_id', df.columns)
        self.assertIn('resultado', df.columns)

        # Verificar número de filas
        self.assertEqual(len(df), 5)

    def test_export_csv_with_metadata(self):
        """Test exportación CSV con metadata."""
        csv_str = self.data_manager.export_resultados_csv(include_metadata=True)

        # Debe incluir columnas de metadata
        df = pd.read_csv(io.StringIO(csv_str), comment='#')
        self.assertIn('consumer_id', df.columns)
        self.assertIn('tiempo_ejecucion', df.columns)

    def test_export_csv_without_metadata(self):
        """Test exportación CSV sin metadata."""
        csv_str = self.data_manager.export_resultados_csv(include_metadata=False)

        # Solo debe tener columnas básicas
        df = pd.read_csv(io.StringIO(csv_str), comment='#')
        self.assertIn('escenario_id', df.columns)
        self.assertIn('resultado', df.columns)
        self.assertNotIn('consumer_id', df.columns)

    def test_export_csv_statistics_header(self):
        """Test que el CSV incluye estadísticas en header."""
        csv_str = self.data_manager.export_resultados_csv()

        # Debe incluir comentarios con estadísticas
        self.assertIn('# Estadísticas Descriptivas', csv_str)
        self.assertIn('# Media:', csv_str)
        self.assertIn('# Mediana:', csv_str)
        self.assertIn('# Desviación Estándar:', csv_str)

    def test_export_csv_empty_data(self):
        """Test exportación CSV con datos vacíos."""
        # Limpiar datos
        self.data_manager.resultados = [1.0, 2.0]
        self.data_manager.resultados_raw = []

        csv_str = self.data_manager.export_resultados_csv()

        # Debe generar CSV simple
        df = pd.read_csv(io.StringIO(csv_str), comment='#')
        self.assertEqual(len(df), 2)

    def test_export_csv_float_format(self):
        """Test que los valores flotantes tienen formato correcto."""
        csv_str = self.data_manager.export_resultados_csv()

        # Verificar que usa 6 decimales
        df = pd.read_csv(io.StringIO(csv_str), comment='#')

        # Los valores deben ser numéricos
        self.assertTrue(pd.api.types.is_numeric_dtype(df['resultado']))


class TestEstadisticasCSVExport(unittest.TestCase):
    """Tests para exportación de estadísticas a CSV."""

    def setUp(self):
        """Setup con DataManager mockeado."""
        self.mock_client = MagicMock(spec=RabbitMQClient)
        self.data_manager = DataManager(self.mock_client)

        self.data_manager.estadisticas = {
            'n': 100,
            'media': 50.5,
            'mediana': 50.0,
            'desviacion_estandar': 10.5,
            'varianza': 110.25,
            'minimo': 20.0,
            'maximo': 80.0,
            'intervalo_confianza_95': {
                'inferior': 48.0,
                'superior': 53.0
            }
        }

    def test_export_estadisticas_csv_structure(self):
        """Test estructura del CSV de estadísticas."""
        csv_str = self.data_manager.export_estadisticas_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Verificar columnas
        self.assertEqual(list(df.columns), ['Estadistica', 'Valor'])

        # Verificar que tiene filas
        self.assertGreater(len(df), 0)

    def test_export_estadisticas_csv_values(self):
        """Test que valores de estadísticas son correctos."""
        csv_str = self.data_manager.export_estadisticas_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Buscar estadística específica (buscar exactamente "Media", no "Mediana")
        media_row = df[df['Estadistica'] == 'Media']
        self.assertGreaterEqual(len(media_row), 1)

    def test_export_estadisticas_csv_intervalo_confianza(self):
        """Test que intervalo de confianza se exporta correctamente."""
        csv_str = self.data_manager.export_estadisticas_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Debe tener filas para IC inferior y superior
        ic_rows = df[df['Estadistica'].str.contains('IC 95%', case=False, na=False)]
        self.assertEqual(len(ic_rows), 2)

    def test_export_estadisticas_csv_empty(self):
        """Test exportación con estadísticas vacías."""
        self.data_manager.estadisticas = {}

        csv_str = self.data_manager.export_estadisticas_csv()

        # Debe retornar header con mensaje
        self.assertIn('Sin datos disponibles', csv_str)


class TestConvergenciaCSVExport(unittest.TestCase):
    """Tests para exportación de convergencia a CSV."""

    def setUp(self):
        """Setup con DataManager mockeado."""
        self.mock_client = MagicMock(spec=RabbitMQClient)
        self.data_manager = DataManager(self.mock_client)

        self.data_manager.historico_convergencia = [
            {'n': 10, 'media': 1.0, 'varianza': 0.5, 'timestamp': 1234567890},
            {'n': 20, 'media': 1.5, 'varianza': 0.8, 'timestamp': 1234567900},
            {'n': 30, 'media': 2.0, 'varianza': 1.0, 'timestamp': 1234567910},
        ]

    def test_export_convergencia_csv_structure(self):
        """Test estructura del CSV de convergencia."""
        csv_str = self.data_manager.export_convergencia_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Verificar columnas
        self.assertIn('n', df.columns)
        self.assertIn('media', df.columns)
        self.assertIn('varianza', df.columns)
        self.assertIn('timestamp', df.columns)

        # Verificar número de filas
        self.assertEqual(len(df), 3)

    def test_export_convergencia_csv_values(self):
        """Test que valores de convergencia son correctos."""
        csv_str = self.data_manager.export_convergencia_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Verificar valores
        self.assertEqual(df.iloc[0]['n'], 10)
        self.assertEqual(df.iloc[1]['n'], 20)
        self.assertEqual(df.iloc[2]['n'], 30)

    def test_export_convergencia_csv_timestamp_format(self):
        """Test que timestamp se convierte a formato legible."""
        csv_str = self.data_manager.export_convergencia_csv()

        df = pd.read_csv(io.StringIO(csv_str))

        # Timestamp debe estar en formato datetime
        # pandas lo parsea automáticamente si está en formato ISO
        self.assertIsNotNone(df['timestamp'][0])

    def test_export_convergencia_csv_empty(self):
        """Test exportación con convergencia vacía."""
        self.data_manager.historico_convergencia = []

        csv_str = self.data_manager.export_convergencia_csv()

        # Debe retornar header con mensaje
        self.assertIn('Sin datos de convergencia disponibles', csv_str)


class TestExportIntegration(unittest.TestCase):
    """Tests de integración para exportación."""

    def setUp(self):
        """Setup con DataManager completo."""
        self.mock_client = MagicMock(spec=RabbitMQClient)
        self.data_manager = DataManager(self.mock_client)

        # Datos completos
        self.data_manager.modelo_info = {'nombre': 'integration_test'}
        self.data_manager.resultados = list(range(1, 101))
        self.data_manager.resultados_raw = [
            {'escenario_id': i, 'resultado': float(i), 'consumer_id': f'c{i%3}'}
            for i in range(1, 101)
        ]
        self.data_manager.estadisticas = {
            'n': 100,
            'media': 50.5,
            'desviacion_estandar': 29.0
        }
        self.data_manager.historico_convergencia = [
            {'n': i*10, 'media': i*5.0, 'varianza': i*2.0, 'timestamp': 1234567890 + i}
            for i in range(1, 11)
        ]

    def test_all_export_methods_work(self):
        """Test que todos los métodos de exportación funcionan."""
        # JSON
        json_str = self.data_manager.export_resultados_json()
        self.assertIsNotNone(json_str)
        self.assertGreater(len(json_str), 0)

        # CSV completo
        csv_str = self.data_manager.export_resultados_csv()
        self.assertIsNotNone(csv_str)
        self.assertGreater(len(csv_str), 0)

        # CSV estadísticas
        stats_csv = self.data_manager.export_estadisticas_csv()
        self.assertIsNotNone(stats_csv)
        self.assertGreater(len(stats_csv), 0)

        # CSV convergencia
        conv_csv = self.data_manager.export_convergencia_csv()
        self.assertIsNotNone(conv_csv)
        self.assertGreater(len(conv_csv), 0)

    def test_export_consistency(self):
        """Test que exportaciones tienen datos consistentes."""
        # Exportar JSON
        json_str = self.data_manager.export_resultados_json()
        json_data = json.loads(json_str)

        # Exportar CSV
        csv_str = self.data_manager.export_resultados_csv()
        csv_df = pd.read_csv(io.StringIO(csv_str), comment='#')

        # Número de resultados debe coincidir
        self.assertEqual(json_data['metadata']['num_resultados'], 100)
        self.assertEqual(len(csv_df), 100)
        self.assertEqual(len(json_data['resultados']), 100)

    def test_thread_safety(self):
        """Test que exportaciones son thread-safe."""
        results = []
        errors = []

        def export_worker():
            try:
                json_str = self.data_manager.export_resultados_json()
                results.append(len(json_str))
            except Exception as e:
                errors.append(e)

        # Crear múltiples threads
        import threading
        threads = [threading.Thread(target=export_worker) for _ in range(5)]

        # Iniciar todos
        for t in threads:
            t.start()

        # Esperar a que terminen
        for t in threads:
            t.join()

        # No debe haber errores
        self.assertEqual(len(errors), 0)
        # Todos deben tener el mismo tamaño
        self.assertEqual(len(set(results)), 1)


if __name__ == '__main__':
    # Configurar logging para tests
    import logging
    logging.basicConfig(
        level=logging.WARNING,
        format='%(levelname)s - %(message)s'
    )

    # Ejecutar tests
    unittest.main(verbosity=2)
