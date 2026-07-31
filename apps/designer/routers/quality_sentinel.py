"""FastAPI router for Protocol Quality Sentinel evaluation API.

Requirements: PRD-SYS-001
"""

from typing import Any, Dict

from cdisc.sentinel_models import ProtocolQualityScore
from fastapi import APIRouter, Depends

import packages  # noqa: F401
from apps.designer.services.quality_sentinel import ProtocolQualitySentinel
from packages.security.middleware import get_current_user

router = APIRouter(prefix="/api/v1/designer/sentinel", tags=["QualitySentinel"])


@router.post("/evaluate", response_model=ProtocolQualityScore)
async def evaluate_protocol_quality_endpoint(
    payload: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
) -> ProtocolQualityScore:
    """Evaluate authored protocol specification payload against quality and burden rules.

    Requirements: PRD-SYS-001
    """
    sentinel = ProtocolQualitySentinel()
    return sentinel.evaluate_protocol_quality(payload)
