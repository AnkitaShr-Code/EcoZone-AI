from pathlib import Path

from fastapi.testclient import TestClient

from ecozone_api.main import create_app
from ecozone_api.settings import Settings


def test_healthz_without_a_bundle() -> None:
    with TestClient(create_app(Settings(app_dist=Path("/nonexistent")))) as client:
        response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "bundleVersion": None}


def test_engine_stubs_do_not_stop_startup(tmp_path: Path) -> None:
    (tmp_path / "deccan").mkdir()
    with TestClient(create_app(Settings(bundle_uri=str(tmp_path), app_dist=tmp_path / "x"))) as client:
        assert client.get("/api/healthz").json()["bundleVersion"] is None
        body = client.get("/api/areas/deccan").json()
    assert body["error"]["code"] == "AREA_NOT_FOUND"


def test_serves_app_with_spa_fallback(tmp_path: Path) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>EcoZone AI</title>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "mock").mkdir()
    (tmp_path / "mock" / "area.json").write_text("{}")
    with TestClient(create_app(Settings(app_dist=tmp_path))) as client:
        assert "EcoZone AI" in client.get("/").text
        assert "EcoZone AI" in client.get("/some/in-app/route").text
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/mock/area.json").text == "{}"
        assert client.get("/api/unknown").status_code == 404
        assert "EcoZone AI" in client.get("/../../etc/passwd").text
