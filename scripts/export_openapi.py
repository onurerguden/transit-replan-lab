"""Regenerate the checked API schema from the application."""

import json
from pathlib import Path

from trl.api.app import app

target = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
target.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
