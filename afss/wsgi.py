"""Gunicorn-Einstiegspunkt fuer den Server-Deploy (siehe docs/changelogs fuer die passende Version).
Reine Verdrahtung - lokal (CLI: `afss dashboard`) wird weiterhin afss/dashboard/app.py direkt
verwendet, das hier ersetzt nichts, es macht dieselbe create_app() fuer Gunicorn aufrufbar."""

import os
from pathlib import Path

from afss.dashboard.app import create_app

config_dir = Path(os.environ.get("AFSS_CONFIG_DIR", "config"))
db_path = Path(os.environ["AFSS_DB_PATH"]) if os.environ.get("AFSS_DB_PATH") else None

app = create_app(config_dir, db_path)
