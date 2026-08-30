"""Scenario driver: orchestrates deterministic demo staging.

Runs AT MOST ONE driver task at a time (module-level singleton). Selecting a
new scenario cancels any running driver so there are never duplicate loops or
overlapping alerts. All alert/risk output flows through the real risk engine +
alert manager so the lifecycle (CREATED / ACTIVE / ACKNOWLEDGED / RESOLVED)
and its hysteresis/debounce remain genuine.
"""
from __future__ import annotations

import asyncio

from .vehicle_sim import vehicle_simulator
from ..services import ai_state

_driver_task: asyncio.Task | None = None


def is_running() -> bool:
    return _driver_task is not None and not _driver_task.done()


async def stop_driver() -> None:
    """Cancel any running driver cleanly and await its termination."""
    global _driver_task
    task = _driver_task
    _driver_task = None
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


async def _start(coro) -> asyncio.Task:
    """Stop any existing driver, then start the given coroutine."""
    global _driver_task
    await stop_driver()
    _driver_task = asyncio.create_task(coro)
    return _driver_task


# ──────────────────────────────────────────────────────────────
# Shared helpers
# ──────────────────────────────────────────────────────────────

def _hold_pair() -> None:
    """Pause the two scenario vehicles so their stage positions hold."""
    for vid in ("VH1027", "VH1052"):
        vehicle_simulator.pause_vehicle(vid)


def _park_others() -> None:
    """Move non-scenario vehicles to distant segments so they don't interfere."""
    vehicle_simulator.reposition_on_segment("VH1031", "SEG_N9_N10", t=0.5)
    vehicle_simulator.reposition_on_segment("VH1045", "SEG_N7_N12", t=0.5)


def _move_pair(lead_t: float, trail_t: float) -> None:
    """Place VH1052 (lead) and VH1027 (trail) on SEG_N2_N3 at given t values.

    SEG_N2_N3 is the Blind Corner Alpha haul segment; both vehicles route
    N2 -> N3. Positioning stays on the road graph (no teleporting off-road);
    each stage just re-steps the along-segment parameter, which the real risk
    engine turns into distance -> WARNING / HIGH RISK / CRITICAL. The blind-
    corner factor (0.7) shrinks the effective distance, so a given physical gap
    reads as more dangerous than the same gap on a straight segment.
    """
    vehicle_simulator.reposition_on_segment("VH1052", "SEG_N2_N3", t=lead_t)
    vehicle_simulator.reposition_on_segment("VH1027", "SEG_N2_N3", t=trail_t)


# ──────────────────────────────────────────────────────────────
# Scenario 1: risk escalation SAFE -> WARNING -> HIGH -> CRITICAL -> RESOLVE
# ──────────────────────────────────────────────────────────────

async def _drive_scenario_1(stage_seconds: float = 3.0) -> None:
    """Step the pair through risk stages, feeding the real pipeline."""
    from ..api.websocket import broadcast
    from ..models import GpsQuality

    _park_others()
    vehicle_simulator.set_gps_quality("VH1027", GpsQuality.GOOD)
    vehicle_simulator.set_gps_quality("VH1052", GpsQuality.GOOD)

    # SAFE: comfortably separated, below any escalation threshold (~110m gap).
    _move_pair(lead_t=0.72, trail_t=0.30)
    _hold_pair()
    await broadcast({
        "type": "scenario_stage",
        "data": {"stage": "SAFE", "scenario": "scenario_1",
                 "message": "Two haul trucks approaching Blind Corner Alpha — SAFE"},
    })
    await asyncio.sleep(stage_seconds)

    # WARNING: ~9m physical gap on the blind-corner segment (eff ~6.3m).
    _move_pair(lead_t=0.62, trail_t=0.586)
    _hold_pair()
    await broadcast({
        "type": "scenario_stage",
        "data": {"stage": "WARNING", "scenario": "scenario_1",
                 "message": "Trucks closing to ~9m on blind-corner segment — WARNING"},
    })
    await asyncio.sleep(stage_seconds)

    # HIGH RISK: ~5m physical gap (eff ~3.5m) — severity CRITICAL on the map.
    _move_pair(lead_t=0.62, trail_t=0.601)
    _hold_pair()
    await broadcast({
        "type": "scenario_stage",
        "data": {"stage": "HIGH", "scenario": "scenario_1",
                 "message": "Trucks at ~5m on the visually-blind corner — HIGH RISK"},
    })
    await asyncio.sleep(stage_seconds)

    # CRITICAL: ~2.4m physical gap on the visually-blind corner — imminent conflict.
    _move_pair(lead_t=0.62, trail_t=0.611)
    _hold_pair()
    await broadcast({
        "type": "scenario_stage",
        "data": {"stage": "CRITICAL", "scenario": "scenario_1",
                 "message": "Imminent conflict at Blind Corner Alpha — CRITICAL"},
    })

    # Hold CRITICAL so operators can acknowledge / the alert can be seen.
    await asyncio.sleep(stage_seconds * 4)

    # RESOLVE: separate the pair -> alert resolves via the real downgrade path.
    _move_pair(lead_t=0.85, trail_t=0.12)
    _hold_pair()
    await broadcast({
        "type": "scenario_stage",
        "data": {"stage": "RESOLVED", "scenario": "scenario_1",
                 "message": "Conflict cleared — returning to normal operation"},
    })
    await asyncio.sleep(stage_seconds)


# ──────────────────────────────────────────────────────────────
# Public entry points
# ──────────────────────────────────────────────────────────────

async def run_scenario_1(stage_seconds: float = 3.0) -> None:
    vehicle_simulator.set_scenario("scenario_1")
    await _start(_drive_scenario_1(stage_seconds))


async def run_scenario_2() -> None:
    """S2 emits its own persistent degraded state (no long-running driver loop)."""
    pass


async def run_scenario_3() -> None:
    """S3 emits a one-shot radar detection (no long-running driver loop)."""
    pass
