# -*- coding: UTF-8 -*-
"""Backward-compatible entry point for the Blueprint application.

The route implementations now live under ``src/blueprints`` and are wired by
``src.app.create_app``. Keep this module so older commands and imports that
reference ``fund_server:app`` continue to work.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import create_app
from src.config.yaml_config import get_server_config
from src.dependencies import get_db


app = create_app()
db = get_db()


if __name__ == "__main__":
    from werkzeug.serving import run_simple

    server_cfg = get_server_config()
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8311)

    try:
        run_simple(
            host,
            port,
            app,
            use_reloader=True,
            use_debugger=False,
            exclude_patterns=[
                "cache/logs/*",
                "cache/*.db",
                "cache/**/*.db",
                "*.db-journal",
                "*.db-wal",
                "*.db-shm",
            ],
        )
    except TypeError:
        run_simple(host, port, app, use_reloader=True, use_debugger=False)
