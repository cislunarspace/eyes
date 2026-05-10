"""Eyes — head-pose monitoring desktop application."""

from .config_store import ConfigStore
from .event_log import AppEvent, EventLog
from .types import AppConfig, AppEventKind

__version__ = "0.1.0"

__all__ = [
    "AppConfig",
    "AppEvent",
    "AppEventKind",
    "ConfigStore",
    "EventLog",
]
