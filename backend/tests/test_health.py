import json
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient
from packaging.version import Version

from trl import __version__
from trl.api.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def test_health_endpoint(tmp_path: Path) -> None:
    with TestClient(create_app(tmp_path / "health.sqlite")) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_versions_have_one_source() -> None:
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text())["project"]
    package = json.loads((ROOT / "frontend" / "package.json").read_text())["version"]
    schema = json.loads((ROOT / "frontend" / "openapi.json").read_text())["info"]["version"]
    assert __version__ == project["version"] == schema
    assert Version(package.replace("-dev.", ".dev")) == Version(__version__)
