# gui/__init__.py
# GUI csomag inicializálója.
# Csak az ablak és a dashboard lapfülek kerülnek innen importálásra.

from .app_window import NavM2MApp
from .dashboard_tabs import DashboardTabs

__all__ = [
    "NavM2MApp",
    "DashboardTabs",
]