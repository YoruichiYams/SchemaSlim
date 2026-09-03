"""UI package for SchemaSlim."""

from schemaslim.ui.dashboard import (
    DashboardRunner,
    create_header,
    create_metrics_panel,
    create_request_feed,
    render_dashboard,
)

__all__ = [
    "DashboardRunner",
    "create_header",
    "create_metrics_panel",
    "create_request_feed",
    "render_dashboard",
]
