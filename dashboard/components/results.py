"""
Results panel components.

Contains metric cards, equity curve chart placeholder, and history DataTable.
No callback logic lives here — this module only builds the layout.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

from dashboard.utils import empty_equity_figure


def _metric_card(card_id: str, label: str, icon_class: str, color: str) -> dbc.Col:
    """Helper that returns a single KPI metric card column."""
    return dbc.Col(
        dbc.Card(
            dbc.CardBody(
                [
                    html.Div(
                        html.I(className=f"{icon_class} fs-2 text-{color}"),
                        className="mb-2",
                    ),
                    html.P(label, className="text-muted small mb-1"),
                    html.H4(
                        "—",
                        id=card_id,
                        className=f"fw-bold text-{color} mb-0",
                    ),
                ],
                className="text-center",
            ),
            className="shadow-sm h-100",
        ),
        xs=12,
        sm=6,
        lg=3,
    )


def create_results_panel() -> html.Div:
    """Return the full results panel: KPIs, equity curve chart, history table."""
    return html.Div(
        [
            # ---- KPI metric cards --------------------------------------
            dbc.Row(
                [
                    _metric_card("metric-total-return", "Total Return", "bi bi-graph-up-arrow", "success"),
                    _metric_card("metric-sharpe", "Sharpe Ratio", "bi bi-bar-chart-line", "info"),
                    _metric_card("metric-max-drawdown", "Max Drawdown", "bi bi-graph-down-arrow", "danger"),
                    _metric_card("metric-num-trades", "# Trades", "bi bi-arrow-left-right", "warning"),
                ],
                className="g-3 mb-4",
            ),

            # ---- Equity curve chart ------------------------------------
            dbc.Card(
                [
                    dbc.CardHeader(
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.H6("Equity Curve", className="mb-0 text-white"),
                                    width="auto",
                                ),
                                dbc.Col(
                                    dbc.Spinner(
                                        html.Div(id="spinner-placeholder"),
                                        size="sm",
                                        color="light",
                                        type="border",
                                    ),
                                    width="auto",
                                    className="ms-auto",
                                ),
                            ],
                            align="center",
                        ),
                        className="bg-dark",
                    ),
                    dbc.CardBody(
                        dcc.Graph(
                            id="equity-curve-chart",
                            figure=empty_equity_figure(),
                            config={"displayModeBar": True, "displaylogo": False},
                            style={"height": "400px"},
                        ),
                        className="p-2",
                    ),
                ],
                className="shadow-sm mb-4",
            ),

            # ---- History DataTable -------------------------------------
            dbc.Card(
                [
                    dbc.CardHeader(
                        html.H6("Backtest History", className="mb-0 text-white"),
                        className="bg-dark",
                    ),
                    dbc.CardBody(
                        dash_table.DataTable(
                            id="history-table",
                            columns=[
                                {"name": "ID", "id": "id"},
                                {"name": "Strategy", "id": "strategy_name"},
                                {"name": "Ticker", "id": "ticker"},
                                {"name": "Short MA", "id": "short_window"},
                                {"name": "Long MA", "id": "long_window"},
                                {"name": "Start", "id": "start_date"},
                                {"name": "End", "id": "end_date"},
                                {"name": "Total Return", "id": "total_return"},
                                {"name": "Sharpe", "id": "sharpe_ratio"},
                                {"name": "Max DD", "id": "max_drawdown"},
                                {"name": "Trades", "id": "num_trades"},
                                {"name": "Run At", "id": "created_at"},
                            ],
                            data=[],
                            sort_action="native",
                            filter_action="native",
                            page_action="native",
                            page_size=10,
                            style_table={"overflowX": "auto"},
                            style_header={
                                "backgroundColor": "#1a1a2e",
                                "color": "white",
                                "fontWeight": "bold",
                                "border": "1px solid #444",
                            },
                            style_data={
                                "backgroundColor": "#16213e",
                                "color": "#e0e0e0",
                                "border": "1px solid #444",
                            },
                            style_data_conditional=[
                                {
                                    "if": {"row_index": "odd"},
                                    "backgroundColor": "#0f3460",
                                },
                                {
                                    "if": {
                                        "filter_query": "{total_return} > 0",
                                        "column_id": "total_return",
                                    },
                                    "color": "#00e676",
                                    "fontWeight": "bold",
                                },
                                {
                                    "if": {
                                        "filter_query": "{total_return} < 0",
                                        "column_id": "total_return",
                                    },
                                    "color": "#ff5252",
                                    "fontWeight": "bold",
                                },
                                {
                                    "if": {
                                        "filter_query": "{max_drawdown} < -0.2",
                                        "column_id": "max_drawdown",
                                    },
                                    "color": "#ff5252",
                                },
                            ],
                            style_filter={
                                "backgroundColor": "#1a1a2e",
                                "color": "white",
                            },
                        ),
                        className="p-0",
                    ),
                ],
                className="shadow-sm",
            ),
        ]
    )


