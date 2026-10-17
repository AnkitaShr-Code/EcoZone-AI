"""Errors the agents layer raises. Engine input errors keep their own types (ecozone_engine.errors)."""


class ModelError(Exception):
    """The model call failed: network, quota, timeout or an answer that does not fit the schema.

    The search treats it as fail-soft (agents/RULES.md): the run ends with the best scored result so
    far and an `error` event.
    """
