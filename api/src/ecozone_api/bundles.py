"""Finding the area bundles at startup: a local directory or a `gs://` prefix (api/RULES.md, "Bundles")."""

import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

META_FILE = "meta.json"
"""Every area bundle holds one; the pipeline writes it last (pipeline/RULES.md)."""

Fetcher = Callable[[str, Path], None]
"""Copies everything under a `gs://bucket/prefix` into a local directory."""


class BundleFetchError(RuntimeError):
    """The bundle location could not be read. Startup stops so a bad revision never takes traffic."""


def fetch_gcs(uri: str, destination: Path) -> None:
    """Download every object under `gs://bucket/prefix` into `destination`, keeping relative paths."""
    from google.cloud import storage  # pyright: ignore[reportMissingTypeStubs]

    bucket_name, _, prefix = uri.removeprefix("gs://").partition("/")
    if not bucket_name:
        raise BundleFetchError(f"{uri} is not a gs://bucket/prefix location.")
    prefix = prefix.strip("/")
    prefix = f"{prefix}/" if prefix else ""
    try:
        client = storage.Client()  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType]
        blobs = [b for b in client.list_blobs(bucket_name, prefix=prefix) if not b.name.endswith("/")]  # pyright: ignore[reportUnknownVariableType, reportUnknownMemberType, reportUnknownArgumentType]
        for blob in blobs:  # pyright: ignore[reportUnknownVariableType]
            target = destination / blob.name.removeprefix(prefix)  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
            target.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(target))  # pyright: ignore[reportUnknownMemberType]
    except BundleFetchError:
        raise
    except Exception as exc:
        raise BundleFetchError(f"Could not read the bundle at {uri}: {exc}") from exc
    if not blobs:
        raise BundleFetchError(f"No files found under {uri}. Check the bucket, the prefix and the service account.")
    log.info("Downloaded %d bundle files from %s", len(blobs), uri)


def resolve_root(uri: str | None, scratch: Path, fetch: Fetcher = fetch_gcs) -> Path | None:
    """The local directory to load bundles from; `gs://` locations are downloaded into `scratch` first."""
    if not uri:
        return None
    if uri.startswith("gs://"):
        fetch(uri, scratch)
        return scratch
    return Path(uri)


def bundle_dirs(root: Path) -> list[Path]:
    """The root itself when it is one area bundle (it holds `meta.json`), else each subdirectory."""
    if not root.is_dir():
        return []
    if (root / META_FILE).is_file():
        return [root]
    return [d for d in sorted(root.iterdir()) if d.is_dir()]
