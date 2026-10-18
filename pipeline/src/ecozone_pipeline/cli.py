"""`uv run pipeline <step|all> --area deccan` (pipeline/RULES.md)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from .config import AreaConfig, Paths, load_config
from .steps import attributes, baselines, bundle, classify, earth_engine, geometry, heights, osm, sun_wind

app = typer.Typer(add_completion=False, no_args_is_help=True, help="Build an area bundle from public data.")

STEPS = ("osm", "sun_wind", "heights", "geometry", "classify", "attributes", "bundle", "baselines")
HEAT_CHECK = "heat-check"
"""Separate command, never part of `all`: needs the optional Earth Engine extra and live access."""
REPO_ROOT = Path(__file__).resolve().parents[3]


def run_step(name: str, cfg: AreaConfig, paths: Paths, refresh: bool, out: Path | None) -> Any:
    runners: dict[str, Callable[[], Any]] = {
        "osm": lambda: osm.run(cfg, paths, refresh=refresh),
        "sun_wind": lambda: sun_wind.run(cfg, paths, refresh=refresh),
        "heights": lambda: heights.run(cfg, paths),
        "geometry": lambda: geometry.run(cfg, paths),
        "classify": lambda: classify.run(cfg, paths),
        "attributes": lambda: attributes.run(cfg, paths),
        "bundle": lambda: str(bundle.run(cfg, paths, out_dir=out)),
        "baselines": lambda: baselines.run(out or paths.bundle(cfg.bundle_version)),
    }
    return runners[name]()


@app.command()
def main(
    step: Annotated[
        str,
        typer.Argument(
            help=f"One of {', '.join(STEPS)}, or 'all'. '{HEAT_CHECK}' is separate (needs `--extra ee`): "
            "it writes the Landsat surface temperature table the heat-check eval reads."
        ),
    ],
    area: Annotated[str, typer.Option(help="Area id; reads pipeline/config/<area>.yaml.")] = "deccan",
    refresh: Annotated[bool, typer.Option(help="Download raw data again instead of using the cache.")] = False,
    data_dir: Annotated[
        Path | None, typer.Option(help="Data directory (default: $ECOZONE_DATA_DIR or ./data).")
    ] = None,
    config: Annotated[Path | None, typer.Option(help="Config file, overriding the area's default.")] = None,
    out: Annotated[Path | None, typer.Option(help="Bundle directory, overriding data/areas/<area>/v<N>.")] = None,
    heat_csv: Annotated[
        Path | None,
        typer.Option(help=f"{HEAT_CHECK} only: output CSV (default evals/heat_check/data/<area>_block_lst.csv)."),
    ] = None,
) -> None:
    if step not in (*STEPS, "all", HEAT_CHECK):
        raise typer.BadParameter(f"unknown step {step!r}; choose from {', '.join(STEPS)}, all or {HEAT_CHECK}")
    cfg = load_config(area, config)
    paths = Paths.for_area(cfg.area_id, data_dir)
    if step == HEAT_CHECK:
        csv_path = heat_csv or REPO_ROOT / "evals" / "heat_check" / "data" / f"{cfg.area_id}_block_lst.csv"
        try:
            result = earth_engine.run(cfg, paths, csv_path, bundle_dir=out)
        except earth_engine.HeatCheckError as err:
            typer.echo(f"[{HEAT_CHECK}] failed: {err}", err=True)
            raise typer.Exit(1) from err
        typer.echo(f"[{HEAT_CHECK}] {result}")
        return
    for name in STEPS if step == "all" else (step,):
        typer.echo(f"[{name}] {run_step(name, cfg, paths, refresh, out)}")


if __name__ == "__main__":
    app()
