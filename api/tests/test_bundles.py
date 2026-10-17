"""Bundle location handling: local roots, a single area bundle, and `gs://` downloads through a fake fetcher."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from ecozone_agents import AgentSettings
from ecozone_api.bundles import META_FILE, BundleFetchError, bundle_dirs, fetch_gcs, resolve_root
from ecozone_api.main import create_app
from ecozone_api.settings import Settings


def _bundle(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / META_FILE).write_text("{}")
    return directory


def test_a_root_with_area_subdirectories_lists_each_area(tmp_path: Path) -> None:
    (tmp_path / "deccan").mkdir()
    (tmp_path / "kothrud").mkdir()
    (tmp_path / "notes.txt").write_text("not an area")
    assert [d.name for d in bundle_dirs(tmp_path)] == ["deccan", "kothrud"]


def test_a_directory_holding_meta_json_is_one_area(tmp_path: Path) -> None:
    area = _bundle(tmp_path / "v1")
    (area / "sub").mkdir()
    assert bundle_dirs(area) == [area]


def test_a_missing_root_has_no_areas(tmp_path: Path) -> None:
    assert bundle_dirs(tmp_path / "nowhere") == []


def test_local_paths_are_used_as_they_are(tmp_path: Path) -> None:
    def never(uri: str, destination: Path) -> None:
        raise AssertionError("local paths must not download")

    assert resolve_root(str(tmp_path), tmp_path / "scratch", never) == tmp_path
    assert resolve_root(None, tmp_path / "scratch", never) is None
    assert resolve_root("", tmp_path / "scratch", never) is None


def test_gcs_locations_download_into_scratch(tmp_path: Path) -> None:
    fetched: list[tuple[str, Path]] = []

    def fake(uri: str, destination: Path) -> None:
        fetched.append((uri, destination))
        _bundle(destination)

    scratch = tmp_path / "scratch"
    root = resolve_root("gs://bucket/areas/deccan/v1", scratch, fake)
    assert root == scratch
    assert fetched == [("gs://bucket/areas/deccan/v1", scratch)]
    assert root is not None and bundle_dirs(root) == [scratch]


def test_the_service_loads_a_gcs_bundle_at_startup(tmp_path: Path, engine: Any) -> None:
    def fake(uri: str, destination: Path) -> None:
        _bundle(destination)

    settings = Settings(bundle_uri="gs://bucket/areas/deccan", app_dist=tmp_path / "no-dist")
    no_llm = AgentSettings(_env_file=None, llm="gemini", google_cloud_project=None)  # pyright: ignore[reportCallIssue]
    app = create_app(settings, engine=engine, agent_settings=no_llm, fetch_bundle=fake)  # pyright: ignore[reportArgumentType]
    with TestClient(app) as client:
        assert client.get("/api/healthz").status_code == 200
        # FakeEngine names an area after its directory, here the temporary download folder.
        assert len(app.state.services.areas) == 1


def test_a_failed_download_stops_startup(tmp_path: Path, engine: Any) -> None:
    def failing(uri: str, destination: Path) -> None:
        raise BundleFetchError("No files found under gs://bucket/missing.")

    settings = Settings(bundle_uri="gs://bucket/missing", app_dist=tmp_path / "no-dist")
    app = create_app(settings, engine=engine, fetch_bundle=failing)  # pyright: ignore[reportArgumentType]
    with pytest.raises(BundleFetchError), TestClient(app):
        pass


def test_a_malformed_gcs_uri_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(BundleFetchError):
        fetch_gcs("gs://", tmp_path)
