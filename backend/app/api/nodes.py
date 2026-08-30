from __future__ import annotations

from fastapi import APIRouter

from ..services import node_health

router = APIRouter(prefix="/api/v1/nodes", tags=["nodes"])


@router.get("/health")
async def get_node_health():
    await node_health.update_node_health()
    return node_health.get_current()