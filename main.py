"""
O-RAN Fronthaul Optimization - Main pipeline.

Runs: topology inference -> capacity estimation -> visualizations.
Use --ml for optional ML-based validation.
Use --json to write all outputs to output/results.json for frontend consumption.
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root
sys.path.insert(0, str(Path(__file__).parent))

from config import DATA_DIR, OUTPUT_DIR
from topology import infer_topology, compute_topology_confidence, detect_topology_outliers
from capacity import (
    estimate_all_capacities,
    compute_capacity_reduction,
    root_cause_attribution,
)
from visualize import (
    plot_topology,
    plot_traffic_patterns,
    plot_capacity_results,
    plot_loss_correlation_over_time,
    ensure_output_dir,
)


def _serialize(obj):
    """Convert numpy types to JSON-serializable types."""
    import numpy as np
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialize(x) for x in obj]
    return obj


def build_json_output(
    topology,
    corr,
    cells,
    confidence,
    outliers,
    cap_no_buf,
    cap_with_buf,
    reduction,
    rca,
    demand,
    ml_report,
    output_dir,
    include_ml,
):
    """Build a JSON-serializable dict for frontend consumption."""
    vis_base = str(Path(output_dir).name)  # "output"
    max_chart_points = 500

    traffic_summary = {}
    for link_id, item in demand.items():
        if len(item) < 2:
            continue
        slot_ts, demand_gbps = item[0], item[1]
        if len(slot_ts) == 0:
            continue
        arr = demand_gbps
        step = max(1, len(arr) // max_chart_points)
        traffic_summary[str(link_id)] = {
            "mean_gbps": round(float(arr.mean()), 2),
            "max_gbps": round(float(arr.max()), 2),
            "n_slots": len(arr),
            "time_sec": [round(float(t), 3) for t in slot_ts[::step]],
            "demand_gbps": [round(float(d), 2) for d in arr[::step]],
        }

    return {
        "topology": {str(k): sorted(v) for k, v in topology.items()},
        "topology_confidence": {str(k): int(v) for k, v in confidence.items()},
        "outliers": [
            {"link_id": k, "cell_id": v[0], "max_correlation": round(v[1], 4)}
            for k, v in outliers.items()
        ],
        "capacity": {
            "no_buffer_gbps": {str(k): round(v, 2) for k, v in cap_no_buf.items()},
            "with_buffer_gbps": {str(k): round(v, 2) for k, v in cap_with_buf.items()},
        },
        "bandwidth_savings_pct": {str(k): int(v) for k, v in reduction.items()},
        "root_cause_attribution": {
            str(link_id): [
                {"time_sec": round(t, 2), "contributors": [{"cell_id": c, "pct": round(p, 1)} for c, p in contribs]}
                for t, contribs in events[:5]
            ]
            for link_id, events in rca.items()
        },
        "correlation_matrix": {
            "cells": cells,
            "matrix": _serialize(corr),
        },
        "traffic_summary": traffic_summary,
        "visualizations": {
            "topology": f"{vis_base}/topology.png",
            "loss_correlation_over_time": f"{vis_base}/loss_correlation_over_time.png",
            "traffic_patterns": f"{vis_base}/traffic_patterns.png",
            "capacity_results": f"{vis_base}/capacity_results.png",
        },
        "ml_validation": ml_report if include_ml else None,
    }


def main():
    parser = argparse.ArgumentParser(description="O-RAN Fronthaul Optimization")
    parser.add_argument("--ml", action="store_true", help="Run optional ML validation (topology + capacity)")
    parser.add_argument("--json", action="store_true", help="Write output/results.json for frontend")
    args = parser.parse_args()

    data_dir = Path(DATA_DIR)
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        return 1

    print("Step 1: Inferring fronthaul topology (correlated packet loss)...")
    topology, corr, cells = infer_topology(data_dir)
    print("  Topology:")
    for link_id, cell_ids in topology.items():
        print(f"    Link {link_id}: cells {sorted(cell_ids)}")

    confidence = compute_topology_confidence(topology, corr, cells)
    print("  Topology Confidence:")
    for link_id in sorted(confidence.keys()):
        print(f"    Link {link_id}: {int(confidence[link_id])}%")

    outliers = detect_topology_outliers(topology, corr, cells)
    if outliers:
        print("  Topology Outlier Detection:")
        for link_id, (cell_id, max_corr) in outliers.items():
            print(f"    Cell {cell_id} (Link {link_id}): <{max_corr:.2f} correlation with any group")

    print("\nStep 2: Estimating link capacity for <=1% packet loss...")
    topology, cap_no_buf, cap_with_buf, demand = estimate_all_capacities(data_dir, topology=topology)
    print("  Capacity (Gbps):")
    for link_id in sorted(topology.keys()):
        print(f"    Link {link_id}: no buffer = {cap_no_buf[link_id]:.2f}, with buffer = {cap_with_buf[link_id]:.2f}")

    reduction = compute_capacity_reduction(cap_no_buf, cap_with_buf)
    print("  Bandwidth Savings via Buffering:")
    for link_id in sorted(reduction.keys()):
        print(f"    Link {link_id}: {int(reduction[link_id])}%")

    rca = root_cause_attribution(demand, cap_with_buf, topology, max_events_per_link=3)
    if rca:
        print("  Root-Cause Attribution (sample congestion events):")
        for link_id in sorted(rca.keys()):
            for t, contribs in rca[link_id][:2]:
                cells_str = ", ".join(f"Cell {c}: {p:.0f}%" for c, p in contribs)
                print(f"    Congestion @ t={t:.1f}s (Link {link_id}): {cells_str}")

    ml_report = None
    if args.ml:
        print("\n  ML Validation (optional):")
        from ml_validation import run_ml_validation
        ml_report = run_ml_validation(topology, corr, cells, demand, cap_with_buf)
        t = ml_report.get("topology", {})
        if t.get("available") and "cv_accuracy_mean" in t:
            print(f"    Topology: RF cross-val accuracy = {t['cv_accuracy_mean']:.2%} (+/- {t.get('cv_accuracy_std', 0):.2%})")
        elif t.get("available"):
            print(f"    Topology: {t.get('note', 'ok')}")
        c = ml_report.get("capacity", {})
        if c.get("available") and "mae_gbps" in c:
            print(f"    Capacity: GB regressor MAE = {c['mae_gbps']:.2f} Gbps (MAPE {c.get('mape_pct', 0):.1f}%)")
        elif c.get("available"):
            print(f"    Capacity: {c.get('note', 'ok')}")
        if not t.get("available") and t.get("reason"):
            print(f"    Topology ML: {t['reason']}")
        if not c.get("available") and c.get("reason"):
            print(f"    Capacity ML: {c['reason']}")

    print("\nStep 3: Generating visualizations...")
    ensure_output_dir()
    plot_topology(topology, corr, cells, OUTPUT_DIR / "topology.png", outliers=outliers)
    plot_loss_correlation_over_time(topology, data_dir, OUTPUT_DIR / "loss_correlation_over_time.png")
    plot_traffic_patterns(demand, OUTPUT_DIR / "traffic_patterns.png")
    plot_capacity_results(
        topology, cap_no_buf, cap_with_buf,
        reduction_pct=reduction,
        save_path=OUTPUT_DIR / "capacity_results.png",
    )
    print(f"  Saved to {OUTPUT_DIR}")

    if args.json:
        ensure_output_dir()
        payload = build_json_output(
            topology, corr, cells, confidence, outliers,
            cap_no_buf, cap_with_buf, reduction, rca, demand,
            _serialize(ml_report) if ml_report else None,
            OUTPUT_DIR,
            include_ml=args.ml,
        )
        json_path = OUTPUT_DIR / "results.json"
        with open(json_path, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"  JSON output: {json_path}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
