"""
Dashboard en tiempo real para simulación Monte Carlo.

Muestra estadísticas de productor, consumidores y progreso general
usando Dash y Plotly para visualización interactiva.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go

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
                last_update = self.data_manager.get_last_update()

                # Generar componentes
                modelo_comp = self._create_modelo_info(modelo_info)
                productor_comp = self._create_productor_panel(stats_prod)
                consumidores_comp = self._create_consumidores_table(stats_cons)

                # Generar gráficas
                grafica_progreso = self._create_progreso_gauge(stats_prod)
                grafica_tasas = self._create_tasas_chart(
                    historico_prod, historico_cons
                )
                grafica_colas = self._create_colas_chart(queue_sizes)

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
                       "Error en actualización")

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
