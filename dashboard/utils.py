"""
Shared dashboard utilities.

Centralises the Plotly figure base layout so all chart components
use a consistent dark theme without duplicating the style dict.
"""

from __future__ import annotations

import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_CHART_BG = "#1e1e2e"
_GRID_COLOR = "#333"
_FONT_COLOR = "#e0e0e0"


def base_figure_layout() -> dict:
    """Return the shared dark-theme Plotly layout dict.

    Callers pass this to ``fig.update_layout(**base_figure_layout())``.
    """
    return dict(
        template="plotly_dark",
        paper_bgcolor=_CHART_BG,
        plot_bgcolor=_CHART_BG,
        xaxis=dict(showgrid=True, gridcolor=_GRID_COLOR, title="Date"),
        yaxis=dict(
            showgrid=True,
            gridcolor=_GRID_COLOR,
            title="Portfolio Value (normalised)",
        ),
        font=dict(color=_FONT_COLOR),
        margin=dict(l=50, r=20, t=20, b=50),
    )


def empty_equity_figure() -> go.Figure:
    """Return a styled empty equity curve figure used as the initial placeholder."""
    fig = go.Figure()
    fig.update_layout(
        **base_figure_layout(),
        annotations=[
            dict(
                text="Run a backtest to see the equity curve",
                xref="paper",
                yref="paper",
                x=0.5,
                y=0.5,
                showarrow=False,
                font=dict(size=16, color="#888"),
            )
        ],
    )
    return fig
