"""
Dashboard en tiempo real para simulación Monte Carlo.

Muestra estadísticas de productor, consumidores y progreso general
usando Dash y Plotly para visualización interactiva.
"""

import logging
import json
import csv
import io
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime

import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import plotly.figure_factory as ff

from src.dashboard.data_manager import DataManager
from src.common.rabbitmq_client import RabbitMQClient

logger = logging.getLogger(__name__)


class MonteCarloDashboard:
    """
    Dashboard web para monitoreo en tiempo real de simulación Monte Carlo.

    Componentes:
    - Panel de información del modelo
    - Panel de productor (progreso, tasa, ETA)
    - Tabla de consumidores (stats individuales)
    - Gráfica de progreso (gauge)
    - Gráfica de tasas de procesamiento (línea temporal)
    - Gráfica de estado de colas (barras)
    """

    def __init__(self, rabbitmq_client: RabbitMQClient,
                 update_interval: int = 2000):
        """
        Inicializa el dashboard.

        Args:
            rabbitmq_client: Cliente conectado de RabbitMQ
            update_interval: Intervalo de actualización en ms (default: 2000 = 2s)
        """
        self.data_manager = DataManager(rabbitmq_client)
        self.update_interval = update_interval

        # Crear aplicación Dash
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP],
            title="Dashboard Monte Carlo"
        )

        # Configurar layout
        self.app.layout = self._create_layout()

        # Registrar callbacks
        self._register_callbacks()

    def _create_layout(self) -> dbc.Container:
        """
        Crea el layout principal del dashboard.

        Returns:
            Container de Bootstrap con todos los componentes
        """
        return dbc.Container([
            # Interval para auto-actualización
            dcc.Interval(
                id='interval-component',
                interval=self.update_interval,
                n_intervals=0
            ),

            # Header
            dbc.Row([
                dbc.Col([
                    html.H1("🎲 Dashboard Monte Carlo", className="text-primary"),
                    html.P(
                        "Monitoreo en tiempo real de simulación distribuida",
                        className="text-muted"
                    ),
                    html.Hr()
                ])
            ]),

            # Información del modelo
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📊 Información del Modelo")),
                        dbc.CardBody(id='modelo-info')
                    ])
                ])
            ], className="mb-4"),

            # Panel de Productor
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("🏭 Productor")),
                        dbc.CardBody(id='productor-panel')
                    ])
                ])
            ], className="mb-4"),

            # Tabla de Consumidores
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("⚙️ Consumidores")),
                        dbc.CardBody(id='consumidores-panel')
                    ])
                ])
            ], className="mb-4"),

            # Gráficas
            dbc.Row([
                # Progreso
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Progreso General")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-progreso')
                        ])
                    ])
                ], width=4),

                # Tasa de procesamiento
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Tasa de Procesamiento")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-tasas')
                        ])
                    ])
                ], width=8),
            ], className="mb-4"),

            # Estado de colas
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Estado de Colas")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-colas')
                        ])
                    ])
                ])
            ], className="mb-4"),

            # Divider
            html.Hr(),
            html.H2("📈 Análisis de Resultados", className="text-primary mt-4 mb-4"),

            # Panel de Estadísticas
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📊 Estadísticas Descriptivas")),
                        dbc.CardBody(id='estadisticas-panel')
                    ])
                ])
            ], className="mb-4"),

            # Gráficas de resultados
            dbc.Row([
                # Histograma
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Distribución de Resultados")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-histograma')
                        ])
                    ])
                ], width=8),

                # Box plot
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Box Plot")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-boxplot')
                        ])
                    ])
                ], width=4),
            ], className="mb-4"),

            # Panel de Exportación
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("💾 Exportar Datos")),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.P("Exportar resultados y estadísticas:", className="mb-3"),
                                    dbc.ButtonGroup([
                                        dbc.Button(
                                            "📄 Descargar CSV",
                                            id="btn-export-csv",
                                            color="primary",
                                            className="mr-2"
                                        ),
                                        dbc.Button(
                                            "📋 Descargar JSON",
                                            id="btn-export-json",
                                            color="info"
                                        ),
                                    ]),
                                    dcc.Download(id="download-csv"),
                                    dcc.Download(id="download-json"),
                                ])
                            ])
                        ])
                    ])
                ])
            ], className="mb-4"),

            # Divider - Análisis Avanzado
            html.Hr(),
            html.H2("🔬 Análisis Avanzado", className="text-primary mt-4 mb-4"),

            # Gráficas de Convergencia
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Convergencia de Media")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-convergencia-media')
                        ])
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Convergencia de Varianza")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-convergencia-varianza')
                        ])
                    ])
                ], width=6),
            ], className="mb-4"),

            # Tests de Normalidad y Q-Q Plot
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("🧪 Tests de Normalidad")),
                        dbc.CardBody(id='tests-normalidad-panel')
                    ])
                ], width=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("Q-Q Plot")),
                        dbc.CardBody([
                            dcc.Graph(id='grafica-qqplot')
                        ])
                    ])
                ], width=6),
            ], className="mb-4"),

            # Logs del Sistema
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("📋 Logs del Sistema")),
                        dbc.CardBody(id='logs-panel', style={'maxHeight': '300px', 'overflowY': 'auto'})
                    ])
                ])
            ], className="mb-4"),

            # Footer con última actualización
            dbc.Row([
                dbc.Col([
                    html.Hr(),
                    html.P(id='last-update', className="text-muted text-center")
                ])
            ])

        ], fluid=True, className="p-4")

    def _register_callbacks(self) -> None:
        """Registra todos los callbacks del dashboard."""

        @self.app.callback(
            [
                Output('modelo-info', 'children'),
                Output('productor-panel', 'children'),
                Output('consumidores-panel', 'children'),
                Output('grafica-progreso', 'figure'),
                Output('grafica-tasas', 'figure'),
                Output('grafica-colas', 'figure'),
                Output('estadisticas-panel', 'children'),
                Output('grafica-histograma', 'figure'),
                Output('grafica-boxplot', 'figure'),
                Output('grafica-convergencia-media', 'figure'),
                Output('grafica-convergencia-varianza', 'figure'),
                Output('tests-normalidad-panel', 'children'),
                Output('grafica-qqplot', 'figure'),
                Output('logs-panel', 'children'),
                Output('last-update', 'children')
            ],
            [Input('interval-component', 'n_intervals')]
        )
        def update_dashboard(n: int):
            """
            Actualiza todos los componentes del dashboard.

            Args:
                n: Número de intervalos transcurridos

            Returns:
                Tupla con todos los componentes actualizados
            """
            try:
                # Obtener datos del DataManager
                summary = self.data_manager.get_summary()
                modelo_info = self.data_manager.get_modelo_info()
                stats_prod = self.data_manager.get_stats_productor()
                stats_cons = self.data_manager.get_stats_consumidores()
                historico_prod = self.data_manager.get_historico_productor()
                historico_cons = self.data_manager.get_historico_consumidores()
                queue_sizes = self.data_manager.get_queue_sizes()
                estadisticas = self.data_manager.get_estadisticas()
                resultados = self.data_manager.get_resultados()
                historico_conv = self.data_manager.get_historico_convergencia()
                tests_normalidad = self.data_manager.get_tests_normalidad()
                logs = self.data_manager.get_logs_sistema()
                last_update = self.data_manager.get_last_update()

                # Generar componentes
                modelo_comp = self._create_modelo_info(modelo_info)
                productor_comp = self._create_productor_panel(stats_prod)
                consumidores_comp = self._create_consumidores_table(stats_cons)

                # Generar gráficas de monitoreo
                grafica_progreso = self._create_progreso_gauge(stats_prod)
                grafica_tasas = self._create_tasas_chart(
                    historico_prod, historico_cons
                )
                grafica_colas = self._create_colas_chart(queue_sizes)

                # Generar componentes de análisis de resultados
                estadisticas_comp = self._create_estadisticas_panel(estadisticas)
                grafica_histograma = self._create_histograma_chart(resultados)
                grafica_boxplot = self._create_boxplot_chart(resultados)

                # Generar componentes de análisis avanzado (Fase 2.3)
                grafica_conv_media = self._create_convergencia_media_chart(historico_conv)
                grafica_conv_var = self._create_convergencia_varianza_chart(historico_conv)
                tests_norm_comp = self._create_tests_normalidad_panel(tests_normalidad)
                grafica_qqplot = self._create_qqplot_chart(resultados, estadisticas)
                logs_comp = self._create_logs_panel(logs)

                # Última actualización
                if last_update:
                    last_update_text = f"Última actualización: {last_update.strftime('%H:%M:%S')}"
                else:
                    last_update_text = "Esperando datos..."

                return (
                    modelo_comp,
                    productor_comp,
                    consumidores_comp,
                    grafica_progreso,
                    grafica_tasas,
                    grafica_colas,
                    estadisticas_comp,
                    grafica_histograma,
                    grafica_boxplot,
                    grafica_conv_media,
                    grafica_conv_var,
                    tests_norm_comp,
                    grafica_qqplot,
                    logs_comp,
                    last_update_text
                )

            except Exception as e:
                logger.error(f"Error actualizando dashboard: {e}", exc_info=True)
                error_msg = html.Div([
                    html.P(f"Error: {e}", className="text-danger")
                ])
                empty_fig = go.Figure()
                return (error_msg, error_msg, error_msg,
                       empty_fig, empty_fig, empty_fig,
                       error_msg, empty_fig, empty_fig,
                       empty_fig, empty_fig, error_msg, empty_fig, error_msg,
                       "Error en actualización")

        # Callback para exportar CSV
        @self.app.callback(
            Output('download-csv', 'data'),
            [Input('btn-export-csv', 'n_clicks')],
            prevent_initial_call=True
        )
        def export_csv(n_clicks):
            """Exporta resultados a CSV."""
            try:
                resultados_raw = self.data_manager.get_resultados_raw()
                estadisticas = self.data_manager.get_estadisticas()

                if not resultados_raw:
                    return None

                # Crear CSV en memoria
                output = io.StringIO()
                writer = csv.writer(output)

                # Header
                writer.writerow(['escenario_id', 'consumer_id', 'resultado', 'tiempo_ejecucion'])

                # Datos
                for res in resultados_raw:
                    writer.writerow([
                        res.get('escenario_id'),
                        res.get('consumer_id'),
                        res.get('resultado'),
                        res.get('tiempo_ejecucion')
                    ])

                # Agregar estadísticas al final
                writer.writerow([])
                writer.writerow(['ESTADISTICAS'])
                for key, value in estadisticas.items():
                    if isinstance(value, dict):
                        writer.writerow([key, json.dumps(value)])
                    else:
                        writer.writerow([key, value])

                # Retornar para descarga
                return dict(
                    content=output.getvalue(),
                    filename=f"resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

            except Exception as e:
                logger.error(f"Error exportando CSV: {e}")
                return None

        # Callback para exportar JSON
        @self.app.callback(
            Output('download-json', 'data'),
            [Input('btn-export-json', 'n_clicks')],
            prevent_initial_call=True
        )
        def export_json(n_clicks):
            """Exporta resultados y estadísticas a JSON."""
            try:
                resultados_raw = self.data_manager.get_resultados_raw()
                estadisticas = self.data_manager.get_estadisticas()
                modelo_info = self.data_manager.get_modelo_info()
                stats_prod = self.data_manager.get_stats_productor()
                stats_cons = self.data_manager.get_stats_consumidores()

                # Crear estructura JSON
                data = {
                    'metadata': {
                        'fecha_exportacion': datetime.now().isoformat(),
                        'num_resultados': len(resultados_raw)
                    },
                    'modelo': modelo_info,
                    'productor': stats_prod,
                    'consumidores': stats_cons,
                    'estadisticas': estadisticas,
                    'resultados': resultados_raw
                }

                # Retornar para descarga
                return dict(
                    content=json.dumps(data, indent=2),
                    filename=f"simulacion_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

            except Exception as e:
                logger.error(f"Error exportando JSON: {e}")
                return None

    def _create_modelo_info(self, modelo_info: Dict[str, Any]) -> html.Div:
        """
        Crea panel de información del modelo.

        Args:
            modelo_info: Información del modelo

        Returns:
            Componente Div con información
        """
        if not modelo_info:
            return html.P("No hay información del modelo disponible",
                         className="text-muted")

        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Strong("Nombre: "),
                    html.Span(modelo_info.get('nombre', 'N/A'))
                ], width=3),
                dbc.Col([
                    html.Strong("Versión: "),
                    html.Span(modelo_info.get('version', 'N/A'))
                ], width=2),
                dbc.Col([
                    html.Strong("Variables: "),
                    html.Span(str(modelo_info.get('num_variables', 0)))
                ], width=2),
                dbc.Col([
                    html.Strong("Tipo: "),
                    html.Span(modelo_info.get('tipo_funcion', 'N/A'))
                ], width=2),
            ]),
            html.Hr(),
            dbc.Row([
                dbc.Col([
                    html.Strong("Expresión: "),
                    html.Code(modelo_info.get('expresion', 'N/A'),
                             className="text-primary")
                ])
            ])
        ])

    def _create_productor_panel(self, stats_prod: Dict[str, Any]) -> html.Div:
        """
        Crea panel de estadísticas del productor.

        Args:
            stats_prod: Estadísticas del productor

        Returns:
            Componente Div con stats del productor
        """
        if not stats_prod:
            return html.P("No hay estadísticas del productor disponibles",
                         className="text-muted")

        progreso = stats_prod.get('progreso', 0) * 100
        escenarios_generados = stats_prod.get('escenarios_generados', 0)
        total_escenarios = stats_prod.get('total_escenarios', 0)
        tasa = stats_prod.get('tasa_generacion', 0)
        eta = stats_prod.get('tiempo_estimado_restante', 0)
        estado = stats_prod.get('estado', 'desconocido')

        # Color del progreso
        if progreso >= 100:
            progress_color = "success"
        elif progreso >= 50:
            progress_color = "info"
        else:
            progress_color = "warning"

        return html.Div([
            # Barra de progreso
            dbc.Row([
                dbc.Col([
                    html.Label("Progreso:"),
                    dbc.Progress(
                        value=progreso,
                        label=f"{progreso:.1f}%",
                        color=progress_color,
                        className="mb-3",
                        style={"height": "30px"}
                    )
                ])
            ]),

            # Métricas
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{escenarios_generados:,}", className="text-primary"),
                        html.P("Escenarios Generados", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_escenarios:,}", className="text-info"),
                        html.P("Total Esperado", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H4(f"{tasa:.1f} esc/s", className="text-success"),
                        html.P("Tasa de Generación", className="text-muted")
                    ], className="text-center")
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.H4(f"{eta:.1f}s", className="text-warning"),
                        html.P("ETA", className="text-muted")
                    ], className="text-center")
                ], width=3),
            ]),

            html.Hr(),

            # Estado
            dbc.Row([
                dbc.Col([
                    html.Strong("Estado: "),
                    dbc.Badge(
                        estado.upper(),
                        color="success" if estado == "completado" else "primary",
                        className="ml-2"
                    )
                ])
            ])
        ])

    def _create_consumidores_table(self, stats_cons: Dict[str, Dict[str, Any]]) -> html.Div:
        """
        Crea tabla de estadísticas de consumidores.

        Args:
            stats_cons: Diccionario con stats de cada consumidor

        Returns:
            Componente Div con tabla de consumidores
        """
        if not stats_cons:
            return html.P("No hay consumidores activos", className="text-muted")

        # Preparar datos para la tabla
        data = []
        for consumer_id, stats in stats_cons.items():
            data.append({
                'ID': consumer_id,
                'Procesados': f"{stats.get('escenarios_procesados', 0):,}",
                'Tasa (esc/s)': f"{stats.get('tasa_procesamiento', 0):.2f}",
                'Último (ms)': f"{stats.get('tiempo_ultimo_escenario', 0) * 1000:.2f}",
                'Promedio (ms)': f"{stats.get('tiempo_promedio', 0) * 1000:.2f}",
                'Tiempo Activo': f"{stats.get('tiempo_activo', 0):.1f}s",
                'Estado': stats.get('estado', 'desconocido').upper()
            })

        # Ordenar por ID
        data.sort(key=lambda x: x['ID'])

        # Calcular totales
        total_procesados = sum(
            int(s.get('escenarios_procesados', 0))
            for s in stats_cons.values()
        )
        tasa_total = sum(
            s.get('tasa_procesamiento', 0)
            for s in stats_cons.values()
        )

        return html.Div([
            # Resumen
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H5(f"{len(stats_cons)}", className="text-primary"),
                        html.P("Consumidores Activos", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H5(f"{total_procesados:,}", className="text-success"),
                        html.P("Total Procesados", className="text-muted")
                    ], className="text-center")
                ], width=4),
                dbc.Col([
                    html.Div([
                        html.H5(f"{tasa_total:.1f} esc/s", className="text-info"),
                        html.P("Tasa Total", className="text-muted")
                    ], className="text-center")
                ], width=4),
            ], className="mb-3"),

            # Tabla
            dash_table.DataTable(
                data=data,
                columns=[{"name": col, "id": col} for col in data[0].keys()],
                style_cell={
                    'textAlign': 'left',
                    'padding': '10px'
                },
                style_header={
                    'backgroundColor': 'rgb(230, 230, 230)',
                    'fontWeight': 'bold'
                },
                style_data_conditional=[
                    {
                        'if': {'column_id': 'Estado', 'filter_query': '{Estado} = ACTIVO'},
                        'backgroundColor': 'rgb(220, 255, 220)',
                        'color': 'green'
                    }
                ]
            )
        ])

    def _create_progreso_gauge(self, stats_prod: Dict[str, Any]) -> go.Figure:
        """
        Crea gráfica de gauge de progreso.

        Args:
            stats_prod: Estadísticas del productor

        Returns:
            Figura de Plotly con gauge
        """
        progreso = stats_prod.get('progreso', 0) * 100 if stats_prod else 0

        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=progreso,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Progreso (%)"},
            delta={'reference': 100},
            gauge={
                'axis': {'range': [None, 100]},
                'bar': {'color': "darkblue"},
                'steps': [
                    {'range': [0, 50], 'color': "lightgray"},
                    {'range': [50, 80], 'color': "gray"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))

        fig.update_layout(
            height=250,
            margin=dict(l=20, r=20, t=40, b=20)
        )

        return fig

    def _create_tasas_chart(self, historico_prod: List[Dict[str, Any]],
                           historico_cons: Dict[str, List[Dict[str, Any]]]) -> go.Figure:
        """
        Crea gráfica de líneas temporales de tasas de procesamiento.

        Args:
            historico_prod: Histórico del productor
            historico_cons: Histórico de consumidores

        Returns:
            Figura de Plotly con líneas temporales
        """
        fig = go.Figure()

        # Línea del productor
        if historico_prod:
            fig.add_trace(go.Scatter(
                x=list(range(len(historico_prod))),
                y=[h.get('tasa_generacion', 0) for h in historico_prod],
                mode='lines',
                name='Productor',
                line=dict(color='blue', width=2)
            ))

        # Líneas de consumidores
        colors = ['green', 'orange', 'purple', 'red', 'cyan', 'magenta']
        for idx, (consumer_id, historico) in enumerate(historico_cons.items()):
            if historico:
                color = colors[idx % len(colors)]
                fig.add_trace(go.Scatter(
                    x=list(range(len(historico))),
                    y=[h.get('tasa_procesamiento', 0) for h in historico],
                    mode='lines',
                    name=consumer_id,
                    line=dict(color=color, width=1.5)
                ))

        fig.update_layout(
            xaxis_title="Tiempo (muestras)",
            yaxis_title="Tasa (esc/s)",
            height=250,
            margin=dict(l=40, r=20, t=20, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        return fig

    def _create_colas_chart(self, queue_sizes: Dict[str, int]) -> go.Figure:
        """
        Crea gráfica de barras del estado de las colas.

        Args:
            queue_sizes: Tamaños de las colas

        Returns:
            Figura de Plotly con barras
        """
        if not queue_sizes:
            return go.Figure()

        queues = list(queue_sizes.keys())
        sizes = list(queue_sizes.values())

        fig = go.Figure([go.Bar(
            x=queues,
            y=sizes,
            text=sizes,
            textposition='auto',
            marker_color=['blue', 'green', 'orange', 'red', 'purple']
        )])

        fig.update_layout(
            xaxis_title="Cola",
            yaxis_title="Mensajes",
            height=250,
            margin=dict(l=40, r=20, t=20, b=80),
            xaxis={'tickangle': -45}
        )

        return fig

    def _create_estadisticas_panel(self, estadisticas: Dict[str, Any]) -> html.Div:
        """
        Crea panel de estadísticas descriptivas.

        Args:
            estadisticas: Diccionario con estadísticas

        Returns:
            Componente Div con estadísticas
        """
        if not estadisticas:
            return html.P("No hay resultados disponibles todavía. Las estadísticas aparecerán cuando los consumidores procesen escenarios.",
                         className="text-muted")

        # Extraer valores
        n = estadisticas.get('n', 0)
        media = estadisticas.get('media', 0)
        mediana = estadisticas.get('mediana', 0)
        std = estadisticas.get('desviacion_estandar', 0)
        varianza = estadisticas.get('varianza', 0)
        minimo = estadisticas.get('minimo', 0)
        maximo = estadisticas.get('maximo', 0)
        p25 = estadisticas.get('percentil_25', 0)
        p75 = estadisticas.get('percentil_75', 0)
        p95 = estadisticas.get('percentil_95', 0)
        p99 = estadisticas.get('percentil_99', 0)
        ic_95 = estadisticas.get('intervalo_confianza_95', {})

        return html.Div([
            # Primera fila: métricas principales
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{n:,}", className="text-primary"),
                        html.P("Resultados", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{media:.6f}", className="text-success"),
                        html.P("Media", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{mediana:.6f}", className="text-info"),
                        html.P("Mediana", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{std:.6f}", className="text-warning"),
                        html.P("Desv. Estándar", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{minimo:.6f}", className="text-secondary"),
                        html.P("Mínimo", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{maximo:.6f}", className="text-secondary"),
                        html.P("Máximo", className="text-muted")
                    ], className="text-center")
                ], width=2),
            ], className="mb-4"),

            html.Hr(),

            # Segunda fila: percentiles
            dbc.Row([
                dbc.Col([
                    html.Strong("Percentiles:"),
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.Span("P25: ", className="text-muted"),
                        html.Span(f"{p25:.6f}")
                    ])
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.Span("P75: ", className="text-muted"),
                        html.Span(f"{p75:.6f}")
                    ])
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.Span("P95: ", className="text-muted"),
                        html.Span(f"{p95:.6f}")
                    ])
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.Span("P99: ", className="text-muted"),
                        html.Span(f"{p99:.6f}")
                    ])
                ], width=2),
            ], className="mb-3"),

            # Tercera fila: intervalo de confianza
            dbc.Row([
                dbc.Col([
                    html.Strong("Intervalo de Confianza 95%:"),
                ], width=3),
                dbc.Col([
                    html.Div([
                        html.Span("[ "),
                        html.Span(f"{ic_95.get('inferior', 0):.6f}", className="text-primary"),
                        html.Span(" , "),
                        html.Span(f"{ic_95.get('superior', 0):.6f}", className="text-primary"),
                        html.Span(" ]")
                    ])
                ], width=9),
            ], className="mb-3"),

            # Cuarta fila: varianza
            dbc.Row([
                dbc.Col([
                    html.Strong("Varianza:"),
                ], width=3),
                dbc.Col([
                    html.Span(f"{varianza:.6f}")
                ], width=9),
            ])
        ])

    def _create_histograma_chart(self, resultados: List[float]) -> go.Figure:
        """
        Crea histograma de distribución de resultados.

        Args:
            resultados: Lista de resultados

        Returns:
            Figura de Plotly con histograma
        """
        if not resultados or len(resultados) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay resultados disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                height=400,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            return fig

        # Crear histograma
        fig = go.Figure()

        fig.add_trace(go.Histogram(
            x=resultados,
            nbinsx=min(50, max(10, len(resultados) // 20)),  # Bins adaptativo
            marker_color='steelblue',
            opacity=0.75,
            name='Resultados'
        ))

        # Calcular y agregar línea de media
        media = sum(resultados) / len(resultados)
        fig.add_vline(
            x=media,
            line_dash="dash",
            line_color="red",
            annotation_text=f"Media: {media:.4f}",
            annotation_position="top"
        )

        fig.update_layout(
            xaxis_title="Valor",
            yaxis_title="Frecuencia",
            height=400,
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=False,
            bargap=0.05
        )

        return fig

    def _create_boxplot_chart(self, resultados: List[float]) -> go.Figure:
        """
        Crea box plot de resultados.

        Args:
            resultados: Lista de resultados

        Returns:
            Figura de Plotly con box plot
        """
        if not resultados or len(resultados) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay resultados",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                height=400,
                margin=dict(l=40, r=20, t=20, b=40),
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            return fig

        fig = go.Figure()

        fig.add_trace(go.Box(
            y=resultados,
            name='Resultados',
            marker_color='steelblue',
            boxmean='sd'  # Mostrar media y desviación estándar
        ))

        fig.update_layout(
            yaxis_title="Valor",
            height=400,
            margin=dict(l=40, r=20, t=20, b=40),
            showlegend=False
        )

        return fig

    def _create_convergencia_media_chart(self, historico_conv: List[Dict[str, Any]]) -> go.Figure:
        """
        Crea gráfica de convergencia de la media vs tiempo.

        Args:
            historico_conv: Histórico de convergencia

        Returns:
            Figura de Plotly con línea de convergencia
        """
        if not historico_conv or len(historico_conv) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay datos de convergencia disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(height=300, margin=dict(l=40, r=20, t=20, b=40))
            return fig

        n_values = [h['n'] for h in historico_conv]
        media_values = [h['media'] for h in historico_conv]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=n_values,
            y=media_values,
            mode='lines+markers',
            name='Media',
            line=dict(color='blue', width=2),
            marker=dict(size=6)
        ))

        # Línea horizontal en y=0 (valor esperado teórico)
        if len(media_values) > 0:
            fig.add_hline(
                y=0,
                line_dash="dash",
                line_color="red",
                annotation_text="Media teórica = 0",
                annotation_position="right"
            )

        fig.update_layout(
            xaxis_title="Número de resultados (n)",
            yaxis_title="Media",
            height=300,
            margin=dict(l=40, r=20, t=20, b=40),
            showlegend=True
        )

        return fig

    def _create_convergencia_varianza_chart(self, historico_conv: List[Dict[str, Any]]) -> go.Figure:
        """
        Crea gráfica de convergencia de la varianza vs tiempo.

        Args:
            historico_conv: Histórico de convergencia

        Returns:
            Figura de Plotly con línea de convergencia
        """
        if not historico_conv or len(historico_conv) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay datos de convergencia disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(height=300, margin=dict(l=40, r=20, t=20, b=40))
            return fig

        n_values = [h['n'] for h in historico_conv]
        var_values = [h['varianza'] for h in historico_conv]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=n_values,
            y=var_values,
            mode='lines+markers',
            name='Varianza',
            line=dict(color='green', width=2),
            marker=dict(size=6)
        ))

        # Línea horizontal en y=2 (valor esperado teórico: Var(X+Y) = Var(X) + Var(Y) = 1 + 1 = 2)
        if len(var_values) > 0:
            fig.add_hline(
                y=2,
                line_dash="dash",
                line_color="red",
                annotation_text="Varianza teórica = 2",
                annotation_position="right"
            )

        fig.update_layout(
            xaxis_title="Número de resultados (n)",
            yaxis_title="Varianza",
            height=300,
            margin=dict(l=40, r=20, t=20, b=40),
            showlegend=True
        )

        return fig

    def _create_tests_normalidad_panel(self, tests_normalidad: Dict[str, Any]) -> html.Div:
        """
        Crea panel con resultados de tests de normalidad.

        Args:
            tests_normalidad: Resultados de tests

        Returns:
            Componente Div con tests
        """
        if not tests_normalidad:
            return html.P("Tests de normalidad se calcularán cuando haya al menos 20 resultados.",
                         className="text-muted")

        ks_test = tests_normalidad.get('kolmogorov_smirnov', {})
        sw_test = tests_normalidad.get('shapiro_wilk')
        n = tests_normalidad.get('n', 0)

        return html.Div([
            # Información general
            dbc.Row([
                dbc.Col([
                    html.H6(f"Basado en {n:,} resultados", className="text-muted")
                ])
            ], className="mb-3"),

            # Test Kolmogorov-Smirnov
            dbc.Row([
                dbc.Col([
                    html.H6("📊 Test Kolmogorov-Smirnov", className="text-primary"),
                    html.Hr(),
                    html.P([
                        html.Strong("Estadístico: "),
                        html.Span(f"{ks_test.get('statistic', 0):.6f}")
                    ]),
                    html.P([
                        html.Strong("p-value: "),
                        html.Span(f"{ks_test.get('pvalue', 0):.6f}")
                    ]),
                    html.P([
                        html.Strong("Conclusión (α=0.05): "),
                        dbc.Badge(
                            "NORMAL" if ks_test.get('is_normal_alpha_05') else "NO NORMAL",
                            color="success" if ks_test.get('is_normal_alpha_05') else "danger"
                        )
                    ]),
                    html.P([
                        html.Strong("Conclusión (α=0.01): "),
                        dbc.Badge(
                            "NORMAL" if ks_test.get('is_normal_alpha_01') else "NO NORMAL",
                            color="success" if ks_test.get('is_normal_alpha_01') else "danger"
                        )
                    ]),
                ])
            ], className="mb-3"),

            # Test Shapiro-Wilk (si está disponible)
            dbc.Row([
                dbc.Col([
                    html.H6("📊 Test Shapiro-Wilk", className="text-primary"),
                    html.Hr(),
                    html.Div([
                        html.P([
                            html.Strong("Estadístico: "),
                            html.Span(f"{sw_test.get('statistic', 0):.6f}" if sw_test else "N/A (n > 5000)")
                        ]),
                        html.P([
                            html.Strong("p-value: "),
                            html.Span(f"{sw_test.get('pvalue', 0):.6f}" if sw_test else "N/A")
                        ]),
                        html.P([
                            html.Strong("Conclusión (α=0.05): "),
                            dbc.Badge(
                                "NORMAL" if sw_test and sw_test.get('is_normal_alpha_05') else "NO NORMAL" if sw_test else "N/A",
                                color="success" if sw_test and sw_test.get('is_normal_alpha_05') else "danger" if sw_test else "secondary"
                            )
                        ]) if sw_test else html.P("Test no disponible para n > 5000", className="text-muted"),
                    ])
                ])
            ])
        ])

    def _create_qqplot_chart(self, resultados: List[float], estadisticas: Dict[str, Any]) -> go.Figure:
        """
        Crea Q-Q plot comparando resultados con distribución normal teórica.

        Args:
            resultados: Lista de resultados
            estadisticas: Estadísticas calculadas

        Returns:
            Figura de Plotly con Q-Q plot
        """
        if not resultados or len(resultados) < 20:
            fig = go.Figure()
            fig.add_annotation(
                text="Q-Q Plot requiere al menos 20 resultados",
                xref="paper", yref="paper",
                x=0.5, y=0.5,
                showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(height=400, margin=dict(l=40, r=20, t=20, b=40))
            return fig

        # Ordenar resultados
        resultados_sorted = np.sort(resultados)

        # Calcular cuantiles teóricos de N(0, 1)
        n = len(resultados_sorted)
        theoretical_quantiles = stats.norm.ppf(np.linspace(0.01, 0.99, n))

        # Estandarizar resultados (para comparar con N(0,1))
        if estadisticas:
            media = estadisticas.get('media', 0)
            std = estadisticas.get('desviacion_estandar', 1)
            if std > 0:
                resultados_estandarizados = (resultados_sorted - media) / std
            else:
                resultados_estandarizados = resultados_sorted
        else:
            resultados_estandarizados = resultados_sorted

        fig = go.Figure()

        # Puntos Q-Q
        fig.add_trace(go.Scatter(
            x=theoretical_quantiles,
            y=resultados_estandarizados,
            mode='markers',
            name='Cuantiles observados',
            marker=dict(size=6, color='steelblue')
        ))

        # Línea de referencia (y = x)
        min_val = min(theoretical_quantiles.min(), resultados_estandarizados.min())
        max_val = max(theoretical_quantiles.max(), resultados_estandarizados.max())
        fig.add_trace(go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode='lines',
            name='Referencia (normalidad perfecta)',
            line=dict(color='red', dash='dash', width=2)
        ))

        fig.update_layout(
            xaxis_title="Cuantiles teóricos (N(0,1))",
            yaxis_title="Cuantiles observados (estandarizados)",
            height=400,
            margin=dict(l=40, r=20, t=40, b=40),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )

        return fig

    def _create_logs_panel(self, logs: List[Dict[str, Any]]) -> html.Div:
        """
        Crea panel de logs del sistema.

        Args:
            logs: Lista de logs

        Returns:
            Componente Div con logs
        """
        if not logs or len(logs) == 0:
            return html.P("No hay logs disponibles todavía.", className="text-muted")

        # Ordenar logs por timestamp (más reciente primero)
        logs_sorted = sorted(logs, key=lambda x: x['timestamp'], reverse=True)

        # Crear filas de logs
        log_rows = []
        for log in logs_sorted[:20]:  # Solo mostrar últimos 20
            timestamp = log['timestamp'].strftime('%H:%M:%S')
            level = log['level']
            message = log['message']

            # Color según nivel
            if level == 'error':
                badge_color = 'danger'
            elif level == 'warning':
                badge_color = 'warning'
            else:
                badge_color = 'info'

            log_rows.append(
                dbc.Row([
                    dbc.Col([
                        html.Small(timestamp, className="text-muted")
                    ], width=2),
                    dbc.Col([
                        dbc.Badge(level.upper(), color=badge_color, className="mr-2")
                    ], width=2),
                    dbc.Col([
                        html.Small(message)
                    ], width=8),
                ], className="mb-2")
            )

        return html.Div(log_rows)

    def start(self, host: str = '0.0.0.0', port: int = 8050,
              debug: bool = False) -> None:
        """
        Inicia el dashboard.

        Args:
            host: Host donde correr el servidor (default: 0.0.0.0)
            port: Puerto donde correr el servidor (default: 8050)
            debug: Modo debug de Dash (default: False)
        """
        logger.info(f"Iniciando dashboard en http://{host}:{port}")

        # Iniciar DataManager
        self.data_manager.start()

        try:
            # Iniciar servidor Dash
            self.app.run_server(host=host, port=port, debug=debug)
        finally:
            # Detener DataManager al salir
            self.data_manager.stop()
            logger.info("Dashboard detenido")


def create_dashboard(rabbitmq_client: RabbitMQClient,
                     update_interval: int = 2000) -> MonteCarloDashboard:
    """
    Factory function para crear el dashboard.

    Args:
        rabbitmq_client: Cliente conectado de RabbitMQ
        update_interval: Intervalo de actualización en ms

    Returns:
        Instancia de MonteCarloDashboard
    """
    return MonteCarloDashboard(rabbitmq_client, update_interval)


__all__ = ['MonteCarloDashboard', 'create_dashboard']
