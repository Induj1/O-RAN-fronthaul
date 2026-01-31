"""
O-RAN Fronthaul Optimization - Main pipeline.

Runs: topology inference -> capacity estimation -> visualizations.
"""

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


def main():
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

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
