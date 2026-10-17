"""Resolve ECOZONE_BUNDLE_URI to a local directory the engine can load (ENGINEERING_RULES §5).

A local path is used as is. A `gs://bucket/prefix` URI is expected to hold the versioned layout the pipeline
publishes, `<prefix>/<area>/v<N>/<table>.parquet` plus `meta.json`. The highest version of each area is
downloaded into `<dest>/<area>/`, which is the flat layout `deps.load_areas` reads. Published versions are
immutable, so older versions are never fetched.
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_VERSION = re.compile(r"^v(\d+)$")
_DEFAULT_DEST = Path(tempfile.gettempdir()) / "ecozone-bundles"


def resolve_bundle_root(uri: str | None, dest: Path | None = None, client: Any = None) -> Path | None:
    """None when unset, the path itself when local, otherwise the directory the bundles were downloaded into."""
    if not uri:
        return None
    if not uri.startswith("gs://"):
        return Path(uri)
    return fetch_bundles(uri, dest or _DEFAULT_DEST, client)


def fetch_bundles(uri: str, dest: Path, client: Any = None) -> Path:
    bucket, _, prefix = uri.removeprefix("gs://").partition("/")
    prefix = prefix.strip("/")
    prefix = f"{prefix}/" if prefix else ""
    if client is None:
        from google.cloud import storage  # imported here so local runs and tests need no cloud client

        client = storage.Client()

    # area -> version -> [(file name, blob)]; anything not shaped <area>/v<N>/<file> is ignored
    found: dict[str, dict[int, list[tuple[str, Any]]]] = {}
    for blob in client.list_blobs(bucket, prefix=prefix):
        parts = blob.name.removeprefix(prefix).split("/")
        match = _VERSION.match(parts[1]) if len(parts) == 3 else None
        if match is None or not parts[2]:
            continue
        found.setdefault(parts[0], {}).setdefault(int(match.group(1)), []).append((parts[2], blob))

    dest.mkdir(parents=True, exist_ok=True)
    for area in sorted(found):
        version = max(found[area])
        target = dest / area
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True)
        for filename, blob in sorted(found[area][version], key=lambda item: item[0]):
            blob.download_to_filename(str(target / filename))
        log.info("Fetched bundle %s v%d from gs://%s/%s", area, version, bucket, prefix)
    if not found:
        log.warning("No bundles found under gs://%s/%s", bucket, prefix)
    return dest