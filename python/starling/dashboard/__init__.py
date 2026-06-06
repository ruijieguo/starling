"""Starling dashboard engine-API (P2.g/P2.h)."""
from starling.dashboard.app import create_app
from starling.dashboard.config import DashboardConfig
from starling.dashboard.engine import DashboardEngine

__all__ = ["create_app", "DashboardConfig", "DashboardEngine"]
