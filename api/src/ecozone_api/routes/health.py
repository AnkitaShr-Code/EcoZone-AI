from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
def healthz() -> dict[str, object]:
    """Liveness for Cloud Run. `bundleVersion` is null until the service loads a bundle (WP6)."""
    return {"ok": True, "bundleVersion": None}
