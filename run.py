# -*- coding: UTF-8 -*-
"""FundEval entry point — uses the application factory (Phase 10)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import create_app
from src.config.yaml_config import get_server_config

app = create_app()

if __name__ == "__main__":
    from werkzeug.serving import run_simple

    server_cfg = get_server_config()
    host = server_cfg.get("host", "127.0.0.1")
    port = server_cfg.get("port", 8888)

    try:
        run_simple(
            host,
            port,
            app,
            use_reloader=True,
            use_debugger=False,
            exclude_patterns=[
                "logs/*",
                "cache/*.db",
                "cache/**/*.db",
                "*.db-journal",
                "*.db-wal",
                "*.db-shm",
            ],
        )
    except TypeError:
        run_simple(host, port, app, use_reloader=True, use_debugger=False)
