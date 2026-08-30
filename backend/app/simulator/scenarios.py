from __future__ import annotations

"""
Demo scenarios for HaulSight.
Each scenario positions vehicles and sets system state for clear demonstration.
"""

from ..simulator.vehicle_sim import vehicle_simulator, VEHICLE_ROUTES
from ..simulator.radar_sim import radar_simulator
from ..api.websocket import broadcast
from ..models import GpsQuality


async def scenario_1_normal_operation():
    """Scenario 1: Two trucks approach Blind Corner Alpha (SEG_N2_N3) on the
    same haul segment. A persistent driver step-wise closes the along-segment
    gap so the REAL risk engine escalates SAFE → WARNING → HIGH RISK → CRITICAL,
    producing a single lifecycle alert (CREATED/ACTIVE/ACKNOWLEDGED/RESOLVED).
    No teleporting: vehicles always stay on the road graph."""
    print("[scenario] Running Scenario 1: Blind corner risk escalation")
    from .scenario_driver import run_scenario_1, stop_driver

    # Stop any prior driver (no duplicate loops) then start this one.
    await stop_driver()

    from ..services.alert_manager import reset_alerts
    reset_alerts()

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_1",
            "title": "Blind Corner Collision Course",
            "description": "VH1027 and VH1052 approaching Blind Corner Alpha on the same segment — risk escalation SAFE→WARNING→HIGH→CRITICAL",
            "status": "active",
        },
    })

    await run_scenario_1()


async def scenario_2_network_failure():
    """Scenario 2: Gateway/network failure (S2).
    The gateway/WebSocket connection is DEGRADED while radar beacons stay
    ONLINE and can still raise a local warning. Visibility is INDEPENDENT of
    network state and is left unchanged."""
    print("[scenario] Running Scenario 2: Network gateway failure")

    from .scenario_driver import stop_driver
    from ..services.alert_manager import reset_alerts
    await stop_driver()
    reset_alerts()

    vehicle_simulator.set_scenario("scenario_2")

    # Suppress two vehicles — no telemetry at all → STALE → OFFLINE via stale_detector
    vehicle_simulator.suppress_vehicle("VH1027")
    vehicle_simulator.suppress_vehicle("VH1045")

    # Broadcast scenario notification FIRST
    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_2",
            "title": "Network Gateway Failure",
            "description": "VH1027 and VH1045 stopped transmitting — gateway degraded. Radar beacons still operational.",
            "status": "active",
        },
    })

    # Then broadcast the degraded health
    await broadcast({
        "type": "gateway_status",
        "data": {"gateway_status": "degraded", "message": "Gateway connectivity interrupted"},
    })


async def scenario_3_non_equipped_vehicle():
    """Scenario 3: Non-equipped (UNKNOWN) vehicle detected by radar at a blind
    corner. Radar-only detection — no HaulSight unit, so no fake vehicle ID.
    The AI classifier reports VEHICLE and a local radar warning is emitted."""
    print("[scenario] Running Scenario 3: Non-equipped vehicle detection")

    from .scenario_driver import stop_driver
    await stop_driver()

    vehicle_simulator.set_scenario("scenario_3")

    # Trigger a radar detection for an unknown vehicle
    from ..models import RadarDetection
    from ..services import radar_service, radar_ai
    import uuid

    detection = RadarDetection(
        detection_id=str(uuid.uuid4())[:8],
        beacon_id="RADAR_ALPHA",
        detected_vehicle_id=None,  # Unknown vehicle — no HaulSight unit
        range_meters=35.0,
        direction=180.0,
        confidence=0.85,
    )

    result = await radar_service.record_detection(detection)

    # AI classify the detected object so the panel shows UNKNOWN/NON-EQUIPPED.
    ai_result = await radar_ai.record_classification({
        "range_m": 35.0,
        "relative_speed_mps": 6.0,
        "reflectivity": 0.9,
        "size": 5.8,
        "persistence": 0.9,
    }, ground_truth="VEHICLE")

    await broadcast({
        "type": "radar_ai",
        "data": ai_result,
    })

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_3",
            "title": "Non-Equipped Vehicle Detected",
            "description": "UNKNOWN vehicle detected by RADAR_ALPHA at Blind Corner Alpha — no GPS unit, radar-only detection",
            "status": "active",
            "detection": result,
            "classification": ai_result,
        },
    })

    await broadcast({
        "type": "radar_warning",
        "data": {
            "beacon_id": "RADAR_ALPHA",
            "message": f"LOCAL WARNING: Non-equipped vehicle detected {detection.range_meters:.0f}m from Blind Corner Alpha",
            "range": detection.range_meters,
            "object_class": ai_result["object_class"],
            "confidence": ai_result["confidence"],
        },
    })


async def scenario_ai_visibility():
    """AI Scenario: Normal visibility — visibility AI shows GOOD conditions."""
    from ..services import visibility_ai
    print("[scenario] Running AI Scenario: Normal visibility")
    vehicle_simulator.set_scenario("scenario_ai_visibility")
    visibility_ai.set_fog_profile("NONE")
    await visibility_ai.update_visibility()
    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_visibility",
            "title": "Normal Visibility (AI)",
            "description": "Visibility AI reports good conditions — normal risk profile",
            "status": "active",
        },
    })


async def scenario_ai_fog():
    """AI Scenario: Dense fog — visibility AI predicts LOW visibility,
    risk engine becomes more conservative, two vehicles escalate risk."""
    from ..services import visibility_ai
    print("[scenario] Running AI Scenario: Dense fog")
    vehicle_simulator.set_scenario("scenario_ai_fog")

    visibility_ai.set_fog_profile("HIGH")
    await visibility_ai.update_visibility()

    # Position two vehicles close on a blind corner as in scenario 1
    vehicle_simulator.reposition_on_segment("VH1027", "SEG_N2_N3", t=0.48)
    vehicle_simulator.reposition_on_segment("VH1052", "SEG_N2_N3", t=0.58)
    vehicle_simulator.reposition_on_segment("VH1031", "SEG_N9_N10", t=0.5)
    vehicle_simulator.reposition_on_segment("VH1045", "SEG_N7_N12", t=0.5)

    for vid in VEHICLE_ROUTES:
        vehicle_simulator.resume_vehicle(vid)

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_fog",
            "title": "Dense Fog (AI)",
            "description": "Visibility AI: ~80m HIGH fog — risk engine more conservative, vehicles approaching blind corner",
            "status": "active",
        },
    })


async def scenario_ai_radar_false_positive():
    """AI Scenario: Radar false positive — AI classifies object as ROCK,
    no vehicle collision alert is generated."""
    from ..services import radar_ai
    print("[scenario] Running AI Scenario: Radar false positive")
    vehicle_simulator.set_scenario("scenario_ai_radar_false_positive")

    # A stationary rock-like object with high reflectivity and no movement
    features = {
        "range_m": 35.0,
        "relative_speed_mps": 0.05,
        "reflectivity": 0.78,
        "size": 1.8,
        "persistence": 1.0,
    }
    result = await radar_ai.record_classification(features, ground_truth="ROCK")
    radar_simulator.force_classification("ROCK")

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_radar_false_positive",
            "title": "Radar False Positive (AI)",
            "description": "AI classifier: ROCK (91% confidence) — no collision alert produced",
            "status": "active",
            "detection": result,
        },
    })
    await broadcast({
        "type": "radar_ai",
        "data": result,
    })
    await broadcast({
        "type": "radar_warning",
        "data": {
            "beacon_id": "RADAR_ALPHA",
            "message": f"Object classified as {result['object_class']} ({result['confidence']}%) — not a vehicle, no alert",
            "range": features["range_m"],
        },
    })


async def scenario_ai_radar_vehicle():
    """AI Scenario: Radar vehicle detection — AI classifies object as VEHICLE,
    a local safety warning is generated."""
    from ..services import radar_ai
    print("[scenario] Running AI Scenario: Radar vehicle detection")
    vehicle_simulator.set_scenario("scenario_ai_radar_vehicle")

    features = {
        "range_m": 40.0,
        "relative_speed_mps": 7.0,
        "reflectivity": 0.92,
        "size": 5.5,
        "persistence": 0.98,
    }
    result = await radar_ai.record_classification(features, ground_truth="VEHICLE")
    radar_simulator.force_classification("VEHICLE")

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_radar_vehicle",
            "title": "Radar Vehicle Detection (AI)",
            "description": "AI classifier: VEHICLE (94% confidence) — local safety warning generated",
            "status": "active",
            "detection": result,
        },
    })
    await broadcast({
        "type": "radar_ai",
        "data": result,
    })
    await broadcast({
        "type": "radar_warning",
        "data": {
            "beacon_id": "RADAR_ALPHA",
            "message": f"⚠ LOCAL WARNING: Vehicle detected {features['range_m']:.0f}m from Blind Corner Alpha (AI {result['confidence']}%)",
            "range": features["range_m"],
        },
    })


async def scenario_ai_hotspot():
    """AI Scenario: Historical hotspot — map shows high-risk zone."""
    from ..services import hotspot_analysis
    print("[scenario] Running AI Scenario: Historical hotspot")
    vehicle_simulator.set_scenario("scenario_ai_hotspot")
    await hotspot_analysis.analyze()
    from ..services import ai_state
    hotspots = await ai_state.get_hotspots()
    await broadcast({
        "type": "hotspots",
        "data": hotspots,
    })
    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_hotspot",
            "title": "Historical Hotspot (AI)",
            "description": f"{hotspots['zones'][0]['segment_id'] if hotspots['zones'] else 'N/A'} — {hotspots['zones'][0]['alerts'] if hotspots['zones'] else 0} alerts, {hotspots['zones'][0]['critical'] if hotspots['zones'] else 0} critical",
            "status": "active",
        },
    })


async def scenario_ai_production():
    """AI Scenario: Production forecast — visibility decreases, predicts impact."""
    from ..services import visibility_ai, production_forecast
    print("[scenario] Running AI Scenario: Production forecast")
    vehicle_simulator.set_scenario("scenario_ai_production")

    visibility_ai.set_fog_profile("MODERATE")
    await visibility_ai.update_visibility()
    forecast = await production_forecast.update_forecast()

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_production",
            "title": "Production Forecast (AI)",
            "description": f"{forecast['normal_cycle_min']}→{forecast['predicted_cycle_min']} min cycle, {forecast['production_impact_pct']}% impact (estimate)",
            "status": "active",
        },
    })
    await broadcast({
        "type": "production_forecast",
        "data": forecast,
    })


async def scenario_ai_node_health():
    """AI Scenario: Critical node anomaly — a blind-corner node's temperature
    sensor reads far outside its normal range and the monitor raises an alert
    (a direct CRITICAL fault, surfaced after the configured persistence delay)."""
    from ..services import node_health
    from ..config import get_config
    print("[scenario] Running AI Scenario: Critical node health anomaly")
    vehicle_simulator.set_scenario("scenario_ai_node_health")

    value = float(get_config()["node_health_fault_value"])
    await node_health.set_override("N3", "temperature_c", value)

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "scenario_ai_node_health",
            "title": "Critical Node Health (AI)",
            "description": f"N-03 Blind Corner Alpha sensor abnormal — temperature reading {value:.0f}°C outside normal range",
            "status": "active",
        },
    })


async def reset_all():
    """Reset all scenarios — restore normal operation without a browser reload."""
    print("[scenario] Resetting all scenarios")

    from .scenario_driver import stop_driver
    from ..services.alert_manager import reset_alerts
    await stop_driver()

    vehicle_simulator.set_scenario(None)

    from ..services import visibility_ai
    visibility_ai.set_fog_profile("NONE")
    try:
        radar_simulator.force_classification(None)
    except Exception:
        pass

    from ..services import node_health
    try:
        await node_health.clear_overrides()
    except Exception:
        pass

    for vid in VEHICLE_ROUTES:
        vehicle_simulator.resume_vehicle(vid)
        vehicle_simulator.set_gps_quality(vid, GpsQuality.GOOD)

    # Remove any virtual radar-only vehicles that accumulated
    from ..state import vehicle_store
    all_vehicles = await vehicle_store.get_all()
    for v in all_vehicles:
        if v.vehicle_id.startswith("RADAR-"):
            await vehicle_store.remove(v.vehicle_id)

    # Clear in-memory alert state so the next run starts clean.
    reset_alerts()

    await visibility_ai.update_visibility()

    await broadcast({
        "type": "gateway_status",
        "data": {"gateway_status": "online", "message": "All systems normal"},
    })

    await broadcast({
        "type": "scenario",
        "data": {
            "name": "reset",
            "title": "Normal Operation",
            "description": "All systems restored to normal",
            "status": "inactive",
        },
    })
