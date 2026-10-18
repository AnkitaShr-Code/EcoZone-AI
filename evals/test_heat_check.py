"""Heat check: the baseline heat index against Landsat surface temperature, on held-out blocks.

Reads the committed table `evals/heat_check/data/<area>_block_lst.csv` (made by `pipeline heat-check`, which needs
Earth Engine) and the engine's baseline scores. Reports the Spearman rank correlation, block count and a permutation
p-value on the test half (the headline), on all blocks and on the tune half for context. There is no pass mark; the
assertions only check that the numbers are well formed. Nothing is tuned and the engine is not touched.
"""

import math

import pytest

from evalkit import heat_check as hc
from evalkit.bench import Bench
from evalkit.bundle import BundleInfo
from evalkit.results import Recorder


def test_heat_index_vs_surface_temperature(request: pytest.FixtureRequest, info: BundleInfo, rec: Recorder) -> None:
    csv, meta_file = hc.csv_path(info.area_id), hc.meta_path(info.area_id)
    if not csv.is_file():
        pytest.skip(hc.not_run_message(info.area_id))
    assert meta_file.is_file(), (
        f"{meta_file.name} (provenance) is missing next to {csv.name}; rerun the heat-check command"
    )

    bench: Bench = request.getfixturevalue("bench")
    baselines = dict(bench.area.block_baselines)
    lst = hc.read_lst(csv)

    # Well-formedness of the input table.
    assert not bool(lst["block_id"].duplicated().any()), "duplicate block ids in the surface temperature table"
    assert bool(lst["lst_kelvin"].map(math.isfinite).all()), "non-finite surface temperature"
    assert bool((lst["lst_kelvin"] > 0).all())
    assert bool((lst["valid_pixels"] > 0).all()), "a block with no valid pixel should have been dropped"
    frame = hc.join_blocks(lst, baselines, info.split)
    assert len(frame) == len(lst), "every block in the table must be a block of the bundle"

    meta = hc.read_meta(meta_file)
    prov = hc.provenance(meta, info.meta)
    assert prov["blocks_with_lst"] == len(lst), "the sidecar and the table disagree on the number of blocks"
    rec.measure("heat_check.provenance", "landsat", prov)

    in_bundle = {s: sum(1 for v in info.split.values() if v == s) for s in ("tune", "test")}
    in_bundle["all"] = in_bundle["tune"] + in_bundle["test"]

    def record(group: str, index: str) -> None:
        for name, c in hc.correlations(frame, index).items():
            assert c.n >= hc.MIN_BLOCKS, f"{c.n} {name} blocks: too few to compute a rank correlation"
            assert c.n <= in_bundle[name]
            assert math.isfinite(c.rho), f"{index} {name}: correlation is not a number (constant input?)"
            assert -1.0 <= c.rho <= 1.0
            assert 0.0 < c.p_value <= 1.0
            rec.measure(
                group,
                f"{index}:{name}",
                {
                    "index": index,
                    "split": name,
                    "n": c.n,
                    "blocks_in_bundle": in_bundle[name],
                    "rho": c.rho,
                    "p_value": c.p_value,
                    "permutations": hc.PERMUTATIONS,
                    "seed": hc.SEED,
                },
            )

    record("heat_check.primary", hc.PRIMARY)
    for index in hc.SECONDARY:
        record("heat_check.secondary", index)
