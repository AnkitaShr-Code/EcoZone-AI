from pathlib import Path

from fastapi.testclient import TestClient

from ecozone_api.main import create_app
from ecozone_api.settings import Settings


def test_healthz() -> None:
    client = TestClient(create_app(Settings(app_dist=Path("/nonexistent"))))
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "bundleVersion": None}


def test_serves_app_with_spa_fallback(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EcoZone AI</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "mock").mkdir()
    (tmp_path / "mock" / "area.json").write_text("{}")
    client = TestClient(create_app(Settings(app_dist=tmp_path)))

    assert "EcoZone AI" in client.get("/").text
    assert "EcoZone AI" in client.get("/some/in-app/route").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/mock/area.json").text == "{}"
    assert client.get("/api/unknown").status_code == 404
    assert "EcoZone AI" in client.get("/../../etc/passwd").text
