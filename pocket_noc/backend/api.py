"""
Pocket NOC - Fronthaul Digital Twin API

Serves precomputed results from output/results.json. No .dat files required.
"""

import json
import os
import sys
from pathlib import Path

# Add parent net12 to path for local config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional

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


# Cached state (loaded at startup from JSON)
_state = {}


def _to_api_format(data: dict) -> dict:
    """Transform results.json format to API response format."""
    cap = data.get("capacity", {})
    topology = data.get("topology", {})
    nb = cap.get("no_buffer_gbps", {})
    wb = cap.get("with_buffer_gbps", {})
    link_ids = set(nb.keys()) | set(wb.keys()) | set(topology.keys())
    risk_scores = {
        str(k): {"score": 0, "reason": "Precomputed from analysis"}
        for k in link_ids
    }
    recommendations = {
        str(k): ["View precomputed baseline. Run locally with .dat files for What-If simulations."]
        for k in link_ids
    }
    loss_over_time = data.get("loss_correlation_over_time", {})
    if not isinstance(loss_over_time, dict):
        loss_over_time = {}
    return {
        "topology": topology,
        "capacity_no_buf": nb,
        "capacity_with_buf": wb,
        "bandwidth_savings_pct": data.get("bandwidth_savings_pct", {}),
        "risk_scores": risk_scores,
        "recommendations": recommendations,
        "topology_confidence": data.get("topology_confidence", {}),
        "root_cause_attribution": data.get("root_cause_attribution", {}),
        "outliers": [
            {"link_id": str(o.get("link_id", "")), "cell_id": o.get("cell_id", 0), "max_correlation": o.get("max_correlation", 0)}
            for o in data.get("outliers", [])
        ],
        "traffic_summary": data.get("traffic_summary", {}),
        "congestion_fingerprint": data.get("congestion_fingerprint", {}) if isinstance(data.get("congestion_fingerprint"), dict) else {},
        "correlation_matrix": data.get("correlation_matrix"),
        "loss_correlation_over_time": loss_over_time,
    }


def _load_from_json(json_path: Path) -> bool:
    """Load and parse results.json, populate _state. Returns True on success."""
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        _state["static_response"] = _to_api_format(data)
        _state["static_mode"] = True
        _state["topology"] = {k: v for k, v in data.get("topology", {}).items()}
        _state["cap_no_buf"] = {k: float(v) for k, v in data.get("capacity", {}).get("no_buffer_gbps", {}).items()}
        _state["cap_with_buf"] = {k: float(v) for k, v in data.get("capacity", {}).get("with_buffer_gbps", {}).items()}
        _state["demand"] = {}
        _state["confidence"] = data.get("topology_confidence", {})
        _state["reduction"] = {k: int(v) for k, v in data.get("bandwidth_savings_pct", {}).items()}
        _state["outliers"] = {}
        _state["corr"] = []
        _state["cells"] = []
        _state["loss_correlation_over_time"] = data.get("loss_correlation_over_time", {}) if isinstance(data.get("loss_correlation_over_time"), dict) else {}
        print(f"Loaded precomputed results from {json_path}")
        return True
    except Exception as e:
        print(f"Failed to load {json_path}: {e}")
        return False


@app.on_event("startup")
def startup():
    """Load precomputed results.json at startup."""
    proj_root = Path(__file__).resolve().parent.parent.parent
    json_paths = [
        proj_root / "output" / "results.json",
        Path(os.environ.get("PRECOMPUTED_JSON", "")),
    ]
    for p in json_paths:
        if p and p.exists():
            if _load_from_json(p):
                return
    _state["static_mode"] = False
    _state["static_response"] = None
    _state["topology"] = {}
    _state["demand"] = {}
    _state["cap_no_buf"] = {}
    _state["cap_with_buf"] = {}
    print("No results.json found. Run: python main.py --json")


@app.get("/health")
def health():
    return {"status": "ok"}


class SimulateRequest(BaseModel):
    traffic_multipliers: Optional[dict] = None


@app.get("/results")
def get_results():
    """Get precomputed fronthaul results."""
    if _state.get("static_response"):
        return _state["static_response"]
    return {"error": "No data loaded. Add output/results.json and redeploy."}


def _simulate_from_json(multipliers: dict) -> dict:
    """
    Approximate What-If: scale per-link capacity by traffic multipliers.
    Assumes equal per-cell contribution on each link.
    """
    topology = _state.get("topology", {})
    cap_no = _state.get("cap_no_buf", {})
    cap_with = _state.get("cap_with_buf", {})
    base = _state.get("static_response", {})
    if not base or not topology:
        return None
    mults = multipliers or {}
    new_cap_no = {}
    new_cap_with = {}
    for link_id, cells in topology.items():
        nb = cap_no.get(link_id, 0)
        wb = cap_with.get(link_id, 0)
        n = len(cells) if cells else 1
        scale = 1.0
        for cid in cells:
            m = mults.get(str(cid), mults.get(cid, 1.0))
            scale += (float(m) - 1.0) / n
        new_cap_no[link_id] = round(nb * scale, 2)
        new_cap_with[link_id] = round(wb * scale, 2)
    reduction = {
        k: int(100 * (1 - new_cap_with[k] / new_cap_no[k])) if new_cap_no.get(k, 0) > 0 else 22
        for k in new_cap_no
    }
    risk = {
        str(k): {"score": 0, "reason": "Simulated (approximate from multipliers)"}
        for k in new_cap_no
    }
    recs = {
        str(k): [f"Simulated: {new_cap_no.get(k, 0):.1f} → {new_cap_with.get(k, 0):.1f} Gbps (no buffer → with buffer)"]
        for k in new_cap_no
    }
    return {
        "topology": base.get("topology", {}),
        "capacity_no_buf": {str(k): v for k, v in new_cap_no.items()},
        "capacity_with_buf": {str(k): v for k, v in new_cap_with.items()},
        "bandwidth_savings_pct": reduction,
        "risk_scores": risk,
        "recommendations": recs,
        "topology_confidence": base.get("topology_confidence", {}),
        "root_cause_attribution": base.get("root_cause_attribution", {}),
        "outliers": base.get("outliers", []),
        "traffic_summary": base.get("traffic_summary", {}),
        "congestion_fingerprint": base.get("congestion_fingerprint", {}),
        "correlation_matrix": base.get("correlation_matrix"),
        "loss_correlation_over_time": base.get("loss_correlation_over_time", {}),
    }


@app.post("/simulate")
def simulate(req: SimulateRequest):
    """What-If: scale capacity by traffic multipliers (approximate, no .dat required)."""
    mults = req.traffic_multipliers or {}
    if not mults:
        if _state.get("static_response"):
            return _state["static_response"]
        return {"error": "No multipliers provided"}
    result = _simulate_from_json(mults)
    if result is None:
        raise HTTPException(503, "No baseline data loaded.")
    return result


if __name__ == "__main__":
    import uvicorn
    print("Pocket NOC API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
