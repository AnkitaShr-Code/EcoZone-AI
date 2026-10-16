"""`uv run ecozone snapshot --area deccan`: write the read routes' responses as the app's mock files.

Calls the routes through the app (not the engine directly), so mock fixtures are exactly what the
API returns (api/RULES.md, "Snapshot"). File names match app/src/api/mock/mockApi.ts. The mock
rescore still reads `_mock-engine.json` (contract/RULES.md, mock decision), which this does not write.
"""

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from .main import create_app
from .settings import REPO_ROOT

FILES = {
    "area.json": "",
    "blocks.json": "/layers/blocks",
    "segments.json": "/layers/segments",
    "buildings.json": "/layers/buildings",
    "wait-points.json": "/layers/waitPoints",
    "parcels.json": "/layers/parcels",
    "hotspots.json": "/hotspots?top=10",
    "sites.json": "/sites",
    "shadows-1300.json": "/shadows?t=13:00",
    "shadows-1500.json": "/shadows?t=15:00",
    "shadows-1600.json": "/shadows?t=16:00",
}


def snapshot(area: str, out: Path, client: TestClient) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, route in FILES.items():
        response = client.get(f"/api/areas/{area}{route}")
        if response.status_code != 200:
            raise SystemExit(f"GET {route or '/'} failed ({response.status_code}): {response.text}")
        body = response.json()
        if name == "area.json":
            body["mock"] = True  # served by the mock adapter from here on
        path = out / name
        path.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")) + "\n")
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(prog="ecozone")
    commands = parser.add_subparsers(dest="command", required=True)
    snap = commands.add_parser("snapshot", help="write the app's mock files from the API")
    snap.add_argument("--area", required=True)
    snap.add_argument("--out", type=Path, help="default: app/public/mock/<area>")
    args = parser.parse_args()
    out = args.out or REPO_ROOT / "app" / "public" / "mock" / args.area
    with TestClient(create_app()) as client:
        for path in snapshot(args.area, out, client):
            print(f"wrote {path}")  # noqa: T201
