"""Internal metadata endpoints (feature-source transparency)."""

from fastapi import APIRouter

from ..feature_sources import feature_sources_public

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/feature-sources")
def get_feature_sources():
    # documents where every model feature comes from — public for transparency
    return feature_sources_public()
