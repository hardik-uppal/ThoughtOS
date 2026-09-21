"""One database location for CLI, graph, notes, API and MCP."""
import os
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

_override = ContextVar('thoughtos_database', default=None)


def database_path(path=None):
    value = path or _override.get() or os.getenv('THOUGHTOS_DB_PATH')
    root = Path(__file__).resolve().parent.parent
    target = Path(value or 'context_os.db').expanduser()
    if not target.is_absolute():
        target = root / target
    return str(target.resolve())


@contextmanager
def using_database(path):
    token = _override.set(database_path(path))
    try:
        yield
    finally:
        _override.reset(token)
