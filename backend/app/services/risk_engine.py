from __future__ import annotations

import math
from typing import Any

from ..config import get_config
from ..models import VehicleStateRecord, RiskLevel, VehicleState
from ..state import vehicle_store
from ..services.road_graph import road_graph, haversine, bearing

# Explicit risk ordering. RiskLevel is a str,Enum so alphabetical comparison of
# `.value` is wrong; use a rank so "worst case wins" works for highlighter.
_RISK_RANK = {
    "SAFE": 0,
    "CAUTION": 1,
    "WARNING": 2,
    "CRITICAL": 3,
}


def _risk_rank(level) -> int:
    level = level.value if hasattr(level, "value") else level
    return _RISK_RANK.get(level, 0)


def _closing_speed(a: VehicleStateRecord, b: VehicleStateRecord) -> float:
    """Calculate closing speed in m/s between two vehicles.
    Positive = approaching, negative = moving apart."""
    brng = bearing(a.latitude, a.longitude, b.latitude, b.longitude)
    brng_rad = math.radians(brng)

    # Project each vehicle's velocity onto the line connecting them
    a_head = math.radians(a.heading)
    b_head = math.radians(b.heading)

    a_speed_ms = a.speed / 3.6
    b_speed_ms = b.speed / 3.6

    # Component of A's velocity towards B
    a_towards = a_speed_ms * math.cos(a_head - brng_rad)
    # Component of B's velocity towards A (opposite direction)
    b_towards = b_speed_ms * math.cos(b_head - (brng_rad + math.pi))

    return a_towards + b_towards


def _stopping_time(speed_kmh: float, max_decel: float) -> float:
    """Time to stop in seconds."""
    speed_ms = speed_kmh / 3.6
    if speed_ms < 0.1:
        return 0.0
    return speed_ms / max_decel


def _risk_factor(a: VehicleStateRecord, b: VehicleStateRecord, distance: float) -> tuple[float, str, str]:
    """Adverse-condition factor for a vehicle pair.

    Factor is in (0, 1]: the closer to 0, the more dangerous a given physical
    distance is treated as (blind-corner segments and low AI-forecast visibility
    both shrink the effective distance). Returns (factor, blind_reason, vis_note).
    """
    config = get_config()
    factor = 1.0
    blind_reason = ""
    vis_note = ""

    if a.current_segment and a.current_segment == b.current_segment:
        seg = road_graph.get_segment(a.current_segment)
        if seg and seg.blind_corner:
            factor = config["blind_corner_threshold_multiplier"]
            blind_reason = f" on blind-corner segment {seg.segment_id}"

    # AI visibility safety margin: lower visibility -> more conservative, so a
    # given physical distance counts as closer (effective distance shrinks).
    try:
        from . import ai_state
        vis = ai_state._visibility
        vis_m = vis.get("estimated_visibility_m", 1000.0)
        if vis_m < 500:
            vis_factor = max(0.45, 0.35 + (vis_m / 500.0) * 0.65)
            factor = min(factor, vis_factor)
            vis_note = f", low visibility {vis_m:.0f}m (AI)"
    except Exception:
        pass

    return factor, blind_reason, vis_note


def evaluate_pair(a: VehicleStateRecord, b: VehicleStateRecord) -> tuple[RiskLevel, str]:
    """Evaluate collision risk between two vehicles.

    Primary trigger is PHYSICAL DISTANCE:
      effective distance = actual distance x adverse-condition factor
        > 10m  (dist_warning_meters)  -> NORMAL (SAFE)
        5-10m  (dist_warning)          -> WARNING
        3-5m   (dist_high)             -> HIGH RISK (severity CRITICAL on the map)
        < 3m   (dist_critical)         -> CRITICAL
    A pair is only escalated when a meaningful approach speed exists
    (> approach_min_closing_speed_mps), so parked/parallel trucks do not alarm.
    Returns (risk_level, reason_string).
    """
    config = get_config()

    # Both must be active enough to matter
    if a.state in (VehicleState.OFFLINE, VehicleState.UNKNOWN) and a.speed < 0.1:
        return RiskLevel.SAFE, ""
    if b.state in (VehicleState.OFFLINE, VehicleState.UNKNOWN) and b.speed < 0.1:
        return RiskLevel.SAFE, ""

    # Distance between vehicles
    distance = haversine(a.latitude, a.longitude, b.latitude, b.longitude)

    # Efficiency sanity cap — well outside every warning band.
    if distance > config.get("risk_max_pair_meters", 200.0):
        return RiskLevel.SAFE, ""

    risk_factor, blind_reason, vis_note = _risk_factor(a, b, distance)
    eff_dist = distance * risk_factor

    # Closing speed: approach gate, not the primary trigger.
    cs = _closing_speed(a, b)
    if cs < -2.0:  # actively moving apart
        return RiskLevel.SAFE, ""
    if cs < config.get("approach_min_closing_speed_mps", 1.0) and eff_dist >= config["dist_critical_meters"]:
        return RiskLevel.SAFE, ""

    risk = RiskLevel.SAFE
    reason = ""

    dist_critical = config["dist_critical_meters"]
    dist_high = config.get("dist_high_meters", dist_critical * 5 / 3)
    dist_warning = config["dist_warning_meters"]

    if eff_dist < dist_critical:
        risk = RiskLevel.CRITICAL
        reason = (
            f"CRITICAL — Vehicles {a.vehicle_id} and {b.vehicle_id} at conflict range: "
            f"distance {distance:.1f}m (< {dist_critical:.0f}m), closing {cs * 3.6:.0f} km/h{blind_reason}{vis_note}."
        )
    elif eff_dist < dist_high:
        risk = RiskLevel.CRITICAL
        reason = (
            f"HIGH RISK — Vehicles {a.vehicle_id} and {b.vehicle_id}: "
            f"distance {distance:.1f}m (3-5m band), closing {cs * 3.6:.0f} km/h{blind_reason}{vis_note}. Immediate braking advised."
        )
    elif eff_dist < dist_warning:
        risk = RiskLevel.WARNING
        reason = (
            f"WARNING — Vehicles {a.vehicle_id} and {b.vehicle_id}: "
            f"distance {distance:.1f}m (5-10m band), closing {cs * 3.6:.0f} km/h{blind_reason}{vis_note}. Reduce speed."
        )

    return risk, reason


async def evaluate_all_pairs() -> list[dict[str, Any]]:
    """Evaluate all vehicle pairs and return risk results.

    Per-vehicle risk is set to the WORST level across every pair the vehicle
    participates in. Previously each pair overwrote the vehicle's risk
    (last-pair-wins), so a vehicle that was CRITICAL with one partner could be
    reset to SAFE by a later, individually-safe pair — leaving the map with
    only one of the two involved vehicles highlighted.
    """
    vehicles = await vehicle_store.get_all()
    results = []
    # vehicle_id -> (worst_risk_level, worst_reason)
    worst: dict[str, tuple[RiskLevel, str]] = {}

    for i in range(len(vehicles)):
        for j in range(i + 1, len(vehicles)):
            a, b = vehicles[i], vehicles[j]
            # Skip if both are truly offline
            if a.state == VehicleState.OFFLINE and b.state == VehicleState.OFFLINE:
                continue
            # Skip unknown vehicles with no data
            if a.state == VehicleState.UNKNOWN and b.state == VehicleState.UNKNOWN:
                continue

            risk, reason = evaluate_pair(a, b)

            for vid in (a.vehicle_id, b.vehicle_id):
                current = worst.get(vid)
                if current is None or _risk_rank(risk) > _risk_rank(current[0]):
                    worst[vid] = (risk, reason if risk != RiskLevel.SAFE else "")

            if risk != RiskLevel.SAFE:
                results.append({
                    "vehicle_a": a.vehicle_id,
                    "vehicle_b": b.vehicle_id,
                    "risk_level": risk.value,
                    "reason": reason,
                })

    # Apply worst-case risk to every tracked vehicle (SAFE if not involved)
    for v in vehicles:
        level, reason = worst.get(v.vehicle_id, (RiskLevel.SAFE, ""))
        await vehicle_store.update_risk(v.vehicle_id, level, reason)

    return results
