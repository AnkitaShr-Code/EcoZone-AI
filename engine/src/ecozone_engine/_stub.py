"""Marker for public functions that WP5 (engine core, rescore and greedy) still has to implement."""


class NotImplementedYetError(NotImplementedError):
    """Raised by engine stubs. The API maps it to 501 so callers can tell a stub from a bug."""

    def __init__(self, what: str, work_package: str) -> None:
        super().__init__(f"{what} is not implemented yet ({work_package}, see docs/TASKS.md)")
