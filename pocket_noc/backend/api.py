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


@app.post("/simulate")
def simulate(req: SimulateRequest):
    """What-If simulations require raw .dat data. Not available in JSON-only mode."""
    raise HTTPException(
        400,
        "JSON-only mode: What-If simulations require raw throughput/pkt-stats .dat files. Run the backend locally with data for simulations.",
    )


if __name__ == "__main__":
    import uvicorn
    print("Pocket NOC API: http://localhost:8000")
    print("Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
