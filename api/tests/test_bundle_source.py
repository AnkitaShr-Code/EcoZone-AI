from __future__ import annotations

from pathlib import Path

import ecozone_engine as e
from ecozone_api.bundle_source import fetch_bundles, resolve_bundle_root
from ecozone_api.deps import load_areas


class _FakeEngine:
    def load_bundle(self, path: Path) -> e.AreaModel:
        return e.AreaModel(area_id=path.name, bundle_version="v1-test")


class FakeBlob:
    def __init__(self, name: str, content: str) -> None:
        self.name = name
        self.content = content

    def download_to_filename(self, filename: str) -> None:
        Path(filename).write_text(self.content)


class FakeClient:
    def __init__(self, objects: dict[str, str]) -> None:
        self.objects = objects

    def list_blobs(self, bucket: str, prefix: str | None = None) -> list[FakeBlob]:
        assert bucket == "bkt"
        return [FakeBlob(n, c) for n, c in sorted(self.objects.items()) if n.startswith(prefix or "")]


OBJECTS = {
    "areas/deccan/v1/meta.json": "deccan-v1-meta",
    "areas/deccan/v1/blocks.parquet": "deccan-v1-blocks",
    "areas/deccan/v2/meta.json": "deccan-v2-meta",
    "areas/deccan/v2/blocks.parquet": "deccan-v2-blocks",
    "areas/tiny/v1/meta.json": "tiny-v1-meta",
    "areas/README.md": "ignored: not <area>/v<N>/<file>",
    "areas/deccan/notes/x.txt": "ignored: not a version directory",
    "areas/deccan/v2/sub/deep.txt": "ignored: nested too deep",
    "other/deccan/v9/meta.json": "ignored: outside the prefix",
}


def test_downloads_the_highest_version_of_each_area_in_the_flat_layout(tmp_path: Path) -> None:
    root = fetch_bundles("gs://bkt/areas", tmp_path / "out", FakeClient(OBJECTS))
    assert root == tmp_path / "out"
    assert sorted(p.name for p in root.iterdir()) == ["deccan", "tiny"]
    assert sorted(p.name for p in (root / "deccan").iterdir()) == ["blocks.parquet", "meta.json"]
    assert (root / "deccan" / "meta.json").read_text() == "deccan-v2-meta"
    assert (root / "tiny" / "meta.json").read_text() == "tiny-v1-meta"


def test_a_refetch_replaces_stale_files(tmp_path: Path) -> None:
    out = tmp_path / "out"
    (out / "deccan").mkdir(parents=True)
    (out / "deccan" / "old.parquet").write_text("stale")
    fetch_bundles("gs://bkt/areas", out, FakeClient(OBJECTS))
    assert not (out / "deccan" / "old.parquet").exists()


def test_an_empty_prefix_loads_nothing(tmp_path: Path) -> None:
    root = fetch_bundles("gs://bkt/empty", tmp_path / "out", FakeClient(OBJECTS))
    assert list(root.iterdir()) == []


def test_versions_compare_as_numbers_not_text(tmp_path: Path) -> None:
    objects = {"areas/a/v2/meta.json": "two", "areas/a/v10/meta.json": "ten"}
    root = fetch_bundles("gs://bkt/areas", tmp_path / "out", FakeClient(objects))
    assert (root / "a" / "meta.json").read_text() == "ten"


def test_unset_and_local_uris_do_not_touch_the_cloud(tmp_path: Path) -> None:
    assert resolve_bundle_root(None) is None
    assert resolve_bundle_root("") is None
    assert resolve_bundle_root(str(tmp_path)) == tmp_path


def test_local_bundle_uri_loads_areas_unchanged(tmp_path: Path) -> None:
    # A local path goes through resolve_bundle_root unchanged; load_areas must still find the area.
    area_dir = tmp_path / "tiny"
    area_dir.mkdir()
    bundle_root = resolve_bundle_root(str(tmp_path))
    areas = load_areas(_FakeEngine(), bundle_root)
    assert list(areas) == ["tiny"]