"""Critical Node Health Monitor (simulated).

SIMULATION MODE:
  There is no real instrumented sensor hardware on the road-graph nodes. The
  module consumes synthetic readings generated in-process. Every result is
  clearly labelled SIMULATION.

Model:
  Monitors "critical" nodes (blind-corner nodes by default) for abnormal
  parameter values. A reading is NORMAL inside a configurable baseline range,
  WARNING outside it but within a hard multiplier, and CRITICAL beyond that.
  Anomalies persist across consecutive abnormal ticks (debounce) before an
  alert is raised, and are cleared by consecutive normal ticks (recovery) so a
  single noisy reading never raises or clears an alert by itself.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime
from typing import Any

from ..config import get_config
from ..services.road_graph import road_graph
from ..api.websocket import broadcast

_SEED = 7
_rng = random.Random(_SEED)

_PARAM_UNIT = {"temperature_c": "°C"}

# (node_id, parameter) -> consecutive abnormal readings since baseline
_debounce: dict[tuple, int] = {}
# (node_id, parameter) -> consecutive normal readings while an anomaly is active
_recovery: dict[tuple, int] = {}
# (node_id, parameter) -> active anomaly record (alert)
_anomalies: dict[tuple, dict[str, Any]] = {}
# fault override for demo scenarios: node_id -> {parameter: value}
_override: dict[str, dict[str, float]] = {}
_current: dict[str, Any] = {"nodes": [], "anomalies": [], "updated_at": None}


def _monitored_nodes() -> list:
    """Critical nodes to monitor (blind-corner nodes unless configured otherwise)."""
    config = get_config()
    critical_only = config.get("node_health_critical_only", True)
    nodes = []
    for n in road_graph.nodes.values():
        if critical_only and getattr(n, "node_type", None) != "blind_corner":
            continue
        nodes.append(n)
    return nodes


def _classify(value: float) -> str:
    config = get_config()
    lo = config["node_health_normal_min"]
    hi = config["node_health_normal_max"]
    hard = config["node_health_hard_multiplier"]
    if lo <= value <= hi:
        return "NORMAL"
    hard_lo, hard_hi = lo / hard, hi * hard
    if hard_lo <= value < lo or hi < value <= hard_hi:
        return "WARNING"
    return "CRITICAL"


def _sample_value(node_id: str, parameter: str) -> float:
    ov = _override.get(node_id, {}).get(parameter)
    if ov is not None:
        return float(ov)
    # Baseline stays comfortably inside the normal range; jitter is small so
    # the demo is stable until a fault override is applied.
    return round(_rng.uniform(28.0, 38.0), 2)


def _make_snapshot() -> list[dict[str, Any]]:
    config = get_config()
    param = "temperature_c"
    unit = _PARAM_UNIT.get(param, "")
    snap = []
    for node in _monitored_nodes():
        value = _sample_value(node.node_id, param)
        status = _classify(value)
        snap.append({
            "node_id": node.node_id,
            "name": getattr(node, "name", None) or node.node_id,
            "location": getattr(node, "name", None) or node.node_id,
            "node_type": getattr(node, "node_type", "node"),
            "latitude": getattr(node, "latitude", None),
            "longitude": getattr(node, "longitude", None),
            "parameter": param,
            "value": value,
            "unit": unit,
            "status": status,
            "normal_range": {
                "min": config["node_health_normal_min"],
                "max": config["node_health_normal_max"],
            },
            "updated_at": datetime.utcnow().isoformat(),
            "data_mode": "SIMULATION",
        })
    return snap


def _find_anomaly(node_id: str, parameter: str) -> dict[str, Any] | None:
    for key, rec in _anomalies.items():
        if key == (node_id, parameter):
            return rec
    return None


async def update_node_health() -> tuple[list, list]:
    """Sample all monitored nodes, apply persistence/recovery logic, and emit
    node_anomaly events for newly-raised and resolved anomalies. Returns the
    (snapshot, anomalies) pair."""
    global _current
    config = get_config()
    now = datetime.utcnow()
    events = []

    snapshot = _make_snapshot()

    # Group by (node_id, parameter) for persistence counters.
    seen_keys: set[tuple] = set()
    for rec in snapshot:
        key = (rec["node_id"], rec["parameter"])
        seen_keys.add(key)
        status = rec["status"]

        if status != "NORMAL":
            _recovery.pop(key, None)
            _debounce[key] = _debounce.get(key, 0) + 1
            rec["tick"] = _debounce[key]

            if _debounce[key] >= config["node_health_debounce_ticks"] and key not in _anomalies:
                rec.pop("tick", None)
                anomaly = {
                    "alert_id": f"NA-{rec['node_id']}-{rec['parameter']}",
                    "node_id": rec["node_id"],
                    "name": rec["name"],
                    "location": rec["location"],
                    "node_type": rec["node_type"],
                    "parameter": rec["parameter"],
                    "value": rec["value"],
                    "unit": rec["unit"],
                    "normal_range": rec["normal_range"],
                    "severity": status,
                    "status": "active",
                    "created_at": rec["updated_at"],
                    "resolved_at": None,
                    "data_mode": "SIMULATION",
                }
                _anomalies[key] = anomaly
                events.append({"type": "node_anomaly", "data": anomaly})
        else:
            _debounce.pop(key, None)
            existing = _find_anomaly(key[0], key[1])
            if existing is not None:
                _recovery[key] = _recovery.get(key, 0) + 1
                if _recovery[key] >= config["node_health_recovery_ticks"]:
                    existing["status"] = "resolved"
                    existing["resolved_at"] = now.isoformat()
                    existing["value"] = rec["value"]
                    _anomalies.pop(key, None)
                    _recovery.pop(key, None)
                    events.append({"type": "node_anomaly", "data": dict(existing)})

    # Nodes that disappeared from monitoring resolve any lingering anomaly.
    for key in list(_anomalies.keys()):
        if key not in seen_keys:
            existing = _anomalies.pop(key)
            existing["status"] = "resolved"
            existing["resolved_at"] = now.isoformat()
            events.append({"type": "node_anomaly", "data": dict(existing)})

    anomalies = [dict(a) for a in _anomalies.values()]
    _current = {
        "nodes": snapshot,
        "anomalies": anomalies,
        "updated_at": now.isoformat(),
    }

    try:
        await broadcast({"type": "node_health", "data": _current})
    except Exception:
        pass
    for event in events:
        try:
            await broadcast(event)
        except Exception:
            pass

    return snapshot, anomalies


async def run_loop(tick: float | None = None) -> None:
    config = get_config()
    tick = tick or config.get("node_health_interval_seconds", 2.0)
    while True:
        try:
            await update_node_health()
        except Exception as e:
            print(f"[node_health] Error: {e}")
        await asyncio.sleep(tick)


def get_current() -> dict[str, Any]:
    return _current


async def set_override(node_id: str, parameter: str, value: float) -> None:
    _override.setdefault(node_id, {})[parameter] = value
    # Re-run immediately so the fault shows up without waiting a full interval.
    await update_node_health()


async def clear_overrides() -> None:
    _override.clear()
    _debounce.clear()
    _recovery.clear()
    await update_node_health()