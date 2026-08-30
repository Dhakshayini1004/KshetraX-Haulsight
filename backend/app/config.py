from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_DEFAULTS: dict[str, Any] = {
    "stale_threshold_seconds": 10,
    "offline_threshold_seconds": 30,
    "state_check_interval_seconds": 2,
    "telemetry_tick_seconds": 0.5,
    "simulator_tick_seconds": 1.0,
    "risk_debounce_ticks": 3,
    "risk_downgrade_ticks": 6,
    "alert_suppression_window_seconds": 30,
    "alert_expiry_seconds": 300,
    "max_speed_kmh": 60,
    "max_deceleration_ms2": 3.0,
    "max_active_alerts": 20,
    # Distance-based risk engine — effective distance = physical x factor
    "dist_critical_meters": 3.0,
    "dist_high_meters": 5.0,
    "dist_warning_meters": 10.0,
    "approach_min_closing_speed_mps": 1.0,
    "risk_max_pair_meters": 200.0,
    "blind_corner_threshold_multiplier": 0.7,
    "gps_jump_max_meters": 500.0,
    # Critical node health monitor (simulated temperature sensor on blind corners)
    "node_health_interval_seconds": 2,
    "node_health_debounce_ticks": 3,
    "node_health_recovery_ticks": 3,
    "node_health_normal_min": 20.0,
    "node_health_normal_max": 45.0,
    "node_health_hard_multiplier": 1.25,
    "node_health_fault_value": 68.0,
    "cors_origins": ["http://localhost:5173", "http://localhost:3000"],
}

_config: dict[str, Any] = {}


def _config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "default_config.yaml"


def load_config() -> dict[str, Any]:
    global _config
    path = _config_path()
    if path.exists():
        with open(path) as f:
            file_cfg = yaml.safe_load(f) or {}
    else:
        file_cfg = {}
    _config = {**_DEFAULTS, **file_cfg}
    return _config


def get_config() -> dict[str, Any]:
    if not _config:
        load_config()
    return _config


def update_config(updates: dict[str, Any]) -> dict[str, Any]:
    _config.update(updates)
    return _config


def db_path() -> str:
    return str(Path(__file__).resolve().parent.parent / "data" / "haulsight.db")
