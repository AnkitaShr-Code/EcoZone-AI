"""Facts the writer is shown: plain names and whole-rupee ints, so explanations never print ids or `998628.0`."""

from ecozone_agents.facts import _plain, _rupees  # pyright: ignore[reportPrivateUsage]


def test_block_ids_in_names_read_like_the_app() -> None:
    assert _plain("Dark roofs, block blk_0006") == "Dark roofs, Block 0006"
    assert _plain("blk_0016") == "Block 0016"
    assert _plain("Open plot on an unnamed lane") == "Open plot on an unnamed lane"


def test_rupees_are_ints_without_a_trailing_decimal() -> None:
    assert _rupees(998628.4) == 998628
    assert isinstance(_rupees(2_000_000.0), int)
