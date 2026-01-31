"""
Pocket NOC - Fronthaul Digital Twin API

FastAPI backend for what-if simulations, risk scores, and action recommendations.
"""

import json
import os
import sys
from pathlib import Path

# Add parent net12 to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

# Import from parent project
from config import DATA_DIR, NUM_CELLS
from data_loader import load_all_cells
from topology import infer_topology, compute_topology_confidence, detect_topology_outliers, align_and_bucket_loss_simple
from capacity import (
    aggregate_link_demand_slot_level,
    capacity_without_buffer,
    capacity_with_buffer,
    compute_capacity_reduction,
    root_cause_attribution,
)

app = FastAPI(title="Pocket NOC - Fronthaul Digital Twin API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


@app.get("/")
def root():
    """Redirect to API docs."""
    return RedirectResponse(url="/docs", status_code=302)


# Cached state (loaded at startup)
_state = {}


def _to_api_format(data: dict) -> dict:
    """Transform results.json format to API response format."""
    cap = data.get("capacity", {})
    topology = data.get("topology", {})
    nb = cap.get("no_buffer_gbps", {})
    wb = cap.get("with_buffer_gbps", {})
    risk_scores = {
        str(k): {"score": 0, "reason": "Static data (no raw traffic)"}
        for k in set(nb.keys()) | set(wb.keys()) | set(topology.keys())
    }
    recommendations = {
        str(k): ["View precomputed baseline. Run with data for simulations."]
        for k in set(nb.keys()) | set(wb.keys()) | set(topology.keys())
    }
    return {
        "topology": topology,
        "capacity_no_buf": nb,
        "capacity_with_buf": wb,
        "bandwidth_savings_pct": data.get("bandwidth_savings_pct", {}),
        "risk_scores": risk_scores,
        "recommendations": recommendations,
        "topology_confidence": data.get("topology_confidence", {}),
        "root_cause_attribution": data.get("root_cause_attribution", {}),
        "outliers": [{"link_id": str(o.get("link_id", "")), "cell_id": o.get("cell_id", 0), "max_correlation": o.get("max_correlation", 0)} for o in data.get("outliers", [])],
        "traffic_summary": data.get("traffic_summary", {}),
        "congestion_fingerprint": {},
        "correlation_matrix": data.get("correlation_matrix"),
        "loss_correlation_over_time": data.get("loss_correlation_over_time", {}),
    }


def load_initial_state(data_dir: Path):
    """Load topology and demand at startup."""
    topology, corr, cells = infer_topology(data_dir)
    demand = aggregate_link_demand_slot_level(topology, data_dir)

    cap_no_buf, cap_with_buf = {}, {}
    for link_id, item in demand.items():
        slot_ts, demand_gbps, per_cell_traffic, per_cell_demand = item[0], item[1], item[2], item[3]
        traffic_mask = demand_gbps > 0.01
        if not traffic_mask.any():
            traffic_mask = np.ones(len(demand_gbps), dtype=bool)
        cap_no_buf[link_id] = capacity_without_buffer(demand_gbps, traffic_mask, per_cell_traffic)
        cap_with_buf[link_id] = capacity_with_buffer(slot_ts, demand_gbps, per_cell_traffic)

    confidence = compute_topology_confidence(topology, corr, cells)
    reduction = compute_capacity_reduction(cap_no_buf, cap_with_buf)
    outliers = detect_topology_outliers(topology, corr, cells)

    _state["topology"] = topology
    _state["corr"] = corr
    _state["cells"] = cells
    _state["demand"] = demand
    _state["cap_no_buf"] = cap_no_buf
    _state["cap_with_buf"] = cap_with_buf
    _state["confidence"] = confidence
    _state["reduction"] = reduction
    _state["outliers"] = outliers
    _state["data_dir"] = data_dir

    # Loss correlation over time (Figure 1-style) for visualization
    try:
        _, pkt_stats = load_all_cells(data_dir, NUM_CELLS)
        bucketed, t_base, n_buckets = align_and_bucket_loss_simple(pkt_stats, bucket_sec=0.2)
        t_axis = float(t_base) + np.arange(n_buckets) * 0.2
        step = max(1, len(t_axis) // 150)
        loss_over_time = {}
        for link_id, cell_ids in topology.items():
            loss_over_time[str(link_id)] = {
                "time_sec": [round(float(t), 2) for t in t_axis[::step]],
                "cells": {str(cid): [round(float(v), 3) for v in bucketed[cid][::step]] for cid in cell_ids if cid in bucketed},
            }
        _state["loss_correlation_over_time"] = loss_over_time
    except Exception:
        _state["loss_correlation_over_time"] = {}


def apply_multipliers(demand: dict, multipliers: dict) -> dict:
    """Apply traffic multipliers to per-cell demand, return new demand dict."""
    import copy
    new_demand = {}
    for link_id, item in demand.items():
        slot_ts, demand_gbps, per_cell_traffic, per_cell_demand = item
        new_per_cell = {}
        new_aggregate = np.zeros_like(demand_gbps)
        for cid, arr in per_cell_demand.items():
            mult = multipliers.get(str(cid), multipliers.get(cid, 1.0))
            scaled = arr * mult
            new_per_cell[cid] = scaled
            new_aggregate += scaled
        new_traffic = {cid: (arr > 0.01) for cid, arr in new_per_cell.items()}
        new_demand[link_id] = (slot_ts, new_aggregate, new_traffic, new_per_cell)
    return new_demand


def compute_risk_score(
    demand_gbps: np.ndarray,
    cap: float,
    buffer_exhaustion_pct: float,
    burst_density: float,
) -> tuple[float, str]:
    """Risk 0-100 and human-readable reason."""
    if len(demand_gbps) == 0 or cap <= 0:
        return 0, "No traffic"
    overflow_slots = np.sum(demand_gbps > cap)
    total_traffic = np.sum(demand_gbps > 0)
    overflow_pct = 100 * overflow_slots / total_traffic if total_traffic > 0 else 0

    # Composite: overflow propensity + buffer exhaustion + burstiness
    risk = min(100, 30 * (overflow_pct / 5) + 40 * min(1, buffer_exhaustion_pct / 3) + 30 * min(1, burst_density))
    risk = max(0, risk)

    if risk >= 70:
        level = "High"
        reason = f"Demand exceeds capacity in {overflow_pct:.1f}% of traffic slots. Buffer exhaustion contributes to congestion risk."
    elif risk >= 40:
        level = "Medium"
        reason = f"Moderate overflow ({overflow_pct:.1f}% of slots). Consider capacity increase for headroom."
    else:
        level = "Low"
        reason = "Link has adequate headroom. Current capacity sufficient for observed traffic."

    return round(risk, 1), f"{level}: {reason}"


def _compute_traffic_summary(demand: dict, max_points: int = 100) -> dict:
    """Build traffic summary for sparklines from demand."""
    out = {}
    for link_id, item in demand.items():
        if len(item) < 2:
            continue
        slot_ts, demand_gbps = item[0], item[1]
        if len(slot_ts) == 0:
            continue
        arr = np.asarray(demand_gbps)
        step = max(1, len(arr) // max_points)
        out[str(link_id)] = {
            "time_sec": [round(float(t), 2) for t in slot_ts[::step]],
            "demand_gbps": [round(float(d), 2) for d in arr[::step]],
        }
    return out


def _congestion_fingerprint(demand_gbps: np.ndarray, cap: float) -> str:
    """Heuristic: buffer bottleneck vs synchronized peaks."""
    if len(demand_gbps) == 0 or cap <= 0:
        return "No traffic"
    overflow = demand_gbps > cap
    if not overflow.any():
        return "No congestion"
    burst_len = 0
    max_burst = 0
    for v in overflow:
        if v:
            burst_len += 1
            max_burst = max(max_burst, burst_len)
        else:
            burst_len = 0
    cv = np.std(demand_gbps) / (np.mean(demand_gbps) + 1e-9) if len(demand_gbps) > 0 else 0
    if max_burst >= 5 and cv > 0.8:
        return "Synchronized traffic peaks"
    return "Switch buffer bottleneck"


def get_recommendations(
    link_id: int,
    current_cap: float,
    required_cap: float,
    n_cells: int,
) -> list[str]:
    """Generate prescriptive action recommendations."""
    recs = []
    if required_cap > current_cap * 1.05:
        recs.append(f"Increase Link {link_id} from {current_cap:.1f} Gbps to {required_cap:.1f} Gbps to keep packet loss ≤1%")
    if n_cells > 8:
        recs.append(f"Link {link_id} has {n_cells} cells. Consider load balancing by reassigning cells to other links.")
    if not recs:
        recs.append(f"Link {link_id} capacity is adequate. No action required.")
    return recs


class SimulateRequest(BaseModel):
    traffic_multipliers: Optional[dict] = None  # {"7": 1.4} = Cell 7 +40%


class SimulateResponse(BaseModel):
    topology: dict
    capacity_no_buf: dict
    capacity_with_buf: dict
    bandwidth_savings_pct: dict
    risk_scores: dict
    recommendations: dict


def _has_data(data_dir: Path) -> bool:
    """Check if data dir has required throughput files."""
    if not data_dir.exists() or not data_dir.is_dir():
        return False
    return (data_dir / "throughput-cell-1.dat").exists()


@app.on_event("startup")
def startup():
    data_dir = Path(DATA_DIR)
    if _has_data(data_dir):
        load_initial_state(data_dir)
    else:
        # Static fallback: serve precomputed results.json when data not available (e.g. Render deploy)
        proj_root = Path(__file__).resolve().parent.parent.parent
        precomp = os.environ.get("PRECOMPUTED_JSON")
        fallback_paths = [proj_root / "output" / "results.json"]
        if precomp:
            fallback_paths.append(Path(precomp))
        fallback = None
        for p in fallback_paths:
            if p.exists():
                fallback = Path(p)
                break
        if fallback:
            try:
                with open(fallback) as f:
                    data = json.load(f)
                # Transform results.json format to API format
                cap = data.get("capacity", {})
                _state["topology"] = {k: v for k, v in data.get("topology", {}).items()}
                _state["cap_no_buf"] = {k: float(v) for k, v in cap.get("no_buffer_gbps", {}).items()}
                _state["cap_with_buf"] = {k: float(v) for k, v in cap.get("with_buffer_gbps", {}).items()}
                _state["static_mode"] = True
                _state["static_response"] = _to_api_format(data)
                _state["corr"] = np.array([])
                _state["cells"] = []
                _state["demand"] = {}
                _state["confidence"] = data.get("topology_confidence", {})
                _state["reduction"] = {k: int(v) for k, v in data.get("bandwidth_savings_pct", {}).items()}
                _state["outliers"] = {}
                _state["loss_correlation_over_time"] = data.get("loss_correlation_over_time", {})
                print(f"Loaded static fallback from {fallback}")
            except Exception as e:
                print(f"Static fallback failed: {e}")
        if not _state.get("static_mode"):
            _state["topology"] = {}
            _state["corr"] = np.array([])
            _state["cells"] = []
            _state["demand"] = {}
            _state["cap_no_buf"] = {}
            _state["cap_with_buf"] = {}
            _state["confidence"] = {}
            _state["reduction"] = {}
            _state["outliers"] = {}
            _state["loss_correlation_over_time"] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/results")
def get_results():
    """Get current state (baseline or after last simulation)."""
    if _state.get("static_mode") and _state.get("static_response"):
        return _state["static_response"]
    if not _state.get("topology"):
        return {"error": "No data loaded. Set DATA_DIR or use precomputed results."}
    return _build_response(_state["demand"], _state["cap_no_buf"], _state["cap_with_buf"])


@app.post("/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    """Run what-if simulation with traffic multipliers."""
    if _state.get("static_mode"):
        raise HTTPException(400, "Static mode: simulations require raw data. Set DATA_DIR with throughput/pkt-stats files.")
    if not _state.get("demand"):
        raise HTTPException(503, "No data loaded.")

    multipliers = req.traffic_multipliers or {}
    demand = apply_multipliers(_state["demand"], multipliers)

    cap_no_buf, cap_with_buf = {}, {}
    for link_id, item in demand.items():
        slot_ts, demand_gbps, per_cell_traffic, _ = item[0], item[1], item[2], item[3]
        traffic_mask = demand_gbps > 0.01
        if not traffic_mask.any():
            traffic_mask = np.ones(len(demand_gbps), dtype=bool)
        cap_no_buf[link_id] = capacity_without_buffer(demand_gbps, traffic_mask, per_cell_traffic)
        cap_with_buf[link_id] = capacity_with_buffer(slot_ts, demand_gbps, per_cell_traffic)

    reduction = compute_capacity_reduction(cap_no_buf, cap_with_buf)
    return _build_response(demand, cap_no_buf, cap_with_buf, reduction)


def _build_response(demand, cap_no_buf, cap_with_buf, reduction=None):
    topology = _state["topology"]
    if reduction is None:
        reduction = compute_capacity_reduction(cap_no_buf, cap_with_buf)

    risk_scores = {}
    recommendations = {}
    congestion_fingerprint = {}

    for link_id in topology:
        item = demand.get(link_id)
        if not item or len(item) < 2:
            continue
        demand_gbps = item[1]
        cap = cap_with_buf.get(link_id, 0)
        n_cells = len(topology.get(link_id, []))
        burst = float(np.std(demand_gbps) / (np.mean(demand_gbps) + 1e-9)) if len(demand_gbps) > 0 else 0
        overflow_pct = 100 * np.sum(demand_gbps > cap) / max(1, np.sum(demand_gbps > 0)) if len(demand_gbps) > 0 else 0
        risk, reason = compute_risk_score(demand_gbps, cap, overflow_pct, min(1, burst))
        risk_scores[str(link_id)] = {"score": risk, "reason": reason}
        required = cap_no_buf.get(link_id, cap)
        recommendations[str(link_id)] = get_recommendations(link_id, cap, required, n_cells)
        congestion_fingerprint[str(link_id)] = _congestion_fingerprint(demand_gbps, cap)

    rca = root_cause_attribution(demand, cap_with_buf, topology, max_events_per_link=5)
    rca_serialized = {}
    for link_id, events in rca.items():
        rca_serialized[str(link_id)] = [
            {"time_sec": round(t, 2), "contributors": [{"cell_id": c, "pct": round(p, 1)} for c, p in contribs]}
            for t, contribs in events[:5]
        ]

    traffic_summary = _compute_traffic_summary(demand)
    outliers_serialized = [
        {"link_id": str(k), "cell_id": v[0], "max_correlation": round(v[1], 4)}
        for k, v in _state.get("outliers", {}).items()
    ]

    corr = _state.get("corr")
    cells = _state.get("cells", [])
    correlation_matrix = None
    if corr is not None and len(cells) > 0 and corr.size > 0:
        correlation_matrix = {
            "cells": [int(c) for c in cells],
            "matrix": [[round(float(v), 4) for v in row] for row in np.asarray(corr).tolist()],
        }

    loss_over_time = _state.get("loss_correlation_over_time", {})

    return {
        "topology": {str(k): sorted(v) for k, v in topology.items()},
        "capacity_no_buf": {str(k): round(v, 2) for k, v in cap_no_buf.items()},
        "capacity_with_buf": {str(k): round(v, 2) for k, v in cap_with_buf.items()},
        "bandwidth_savings_pct": {str(k): int(v) for k, v in reduction.items()},
        "risk_scores": risk_scores,
        "recommendations": recommendations,
        "topology_confidence": _state.get("confidence", {}),
        "root_cause_attribution": rca_serialized,
        "outliers": outliers_serialized,
        "traffic_summary": traffic_summary,
        "congestion_fingerprint": congestion_fingerprint,
        "correlation_matrix": correlation_matrix,
        "loss_correlation_over_time": loss_over_time,
    }


if __name__ == "__main__":
    import uvicorn
    print("Pocket NOC API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
