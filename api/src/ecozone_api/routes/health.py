from fastapi import APIRouter

from ..deps import ServicesDep

router = APIRouter()


@router.get("/healthz")
def healthz(services: ServicesDep) -> dict[str, object]:
    """Liveness for Cloud Run. `bundleVersion` is null until a bundle loads (one area per bundle)."""
    versions = sorted({area.bundle_version for area in services.areas.values()})
    return {"ok": True, "bundleVersion": ", ".join(versions) or None}
