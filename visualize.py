"""
Visualize topology, traffic patterns, and capacity results for hackathon judges.
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from config import OUTPUT_DIR, DATA_DIR, NUM_CELLS
from data_loader import load_all_cells
from topology import infer_topology, align_and_bucket_loss_simple, compute_topology_confidence, detect_topology_outliers
from capacity import estimate_all_capacities, compute_capacity_reduction


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def plot_topology(
    topology: dict,
    corr_matrix: np.ndarray,
    cells: list,
    save_path: Path,
    outliers: dict = None,
):
    """Draw inferred topology: DU -> 3 links -> cells. Highlight outliers if provided."""
    ensure_output_dir()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: topology diagram (compact)
    colors = ["#2ecc71", "#3498db", "#e74c3c"]
    ax1.set_title("Inferred Fronthaul Topology", fontsize=14)
    ax1.set_xlim(-1.5, 1.5)
    ax1.set_ylim(-1.2, 1.2)
    ax1.axis("off")
    ax1.add_patch(plt.Circle((0, 0), 0.12, color="navy", zorder=3))
    ax1.text(0, 0, "DU", ha="center", va="center", color="white", fontsize=9, zorder=4)

    outlier_links = set(outliers.keys()) if outliers else set()
    for i, (link_id, cell_ids) in enumerate(topology.items()):
        c = colors[(link_id - 1) % len(colors)]
        angle = -0.5 * np.pi + (i + 1) * 2 * np.pi / 4
        lx, ly = 0.6 * np.cos(angle), 0.6 * np.sin(angle)
        ax1.plot([0.12, lx * 0.8], [0, ly * 0.8], color=c, lw=2.5,
                 linestyle="--" if link_id in outlier_links else "-")
        ec = "cyan" if link_id in outlier_links else "none"
        circle = plt.Circle((lx, ly), 0.1, facecolor=c, alpha=0.8,
                           edgecolor=ec, linewidth=2 if ec != "none" else 0)
        ax1.add_patch(circle)
        label = f"Link {link_id}" + (" (outlier)" if link_id in outlier_links else "")
        ax1.text(lx, ly, label, ha="center", va="center", fontsize=8)
        cell_str = ",".join(str(x) for x in sorted(cell_ids)[:6])
        if len(cell_ids) > 6:
            cell_str += "..."
        ax1.text(lx, ly - 0.25, f"cells: {cell_str}", ha="center", fontsize=6)

    # Right: correlation heatmap (highlight outlier cells)
    outlier_cells = set()
    if outliers:
        for link_id, (cid, _) in outliers.items():
            outlier_cells.add(cid)
    im = ax2.imshow(corr_matrix, cmap="YlOrRd", vmin=0, vmax=1)
    if outlier_cells and cells:
        for j, c in enumerate(cells):
            if c in outlier_cells:
                ax2.axhline(j, color="cyan", linewidth=2, alpha=0.8)
                ax2.axvline(j, color="cyan", linewidth=2, alpha=0.8)
    ax2.set_xticks(range(len(cells)))
    ax2.set_xticklabels(cells)
    ax2.set_yticks(range(len(cells)))
    ax2.set_yticklabels(cells)
    ax2.set_title("Packet Loss Correlation (cells on same link correlate)")
    plt.colorbar(im, ax=ax2, label="Correlation")
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_traffic_patterns(demand: dict, save_path: Path, n_samples: int = 5000):
    """Plot aggregate demand time series per link."""
    ensure_output_dir()
    n_links = len(demand)
    fig, axes = plt.subplots(n_links, 1, figsize=(12, 3 * n_links), sharex=True)
    if n_links == 1:
        axes = [axes]

    colors = ["#2ecc71", "#3498db", "#e74c3c"]
    for i, (link_id, item) in enumerate(demand.items()):
        slot_ts, demand_gbps = item[0], item[1]
        ax = axes[i]
        k = min(n_samples, len(slot_ts))
        ax.fill_between(slot_ts[:k], 0, demand_gbps[:k], color=colors[i % 3], alpha=0.6)
        ax.set_ylabel("Demand (Gbps)")
        ax.set_title(f"Link {link_id} - aggregated traffic")
        ax.grid(True, alpha=0.3)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("Link Traffic Patterns (slot-level aggregate demand)", fontsize=14)
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_loss_correlation_over_time(
    topology: dict,
    data_dir: Path = None,
    save_path: Path = None,
    bucket_sec: float = 0.2,
):
    """
    Figure 1-style: packet loss fraction over time per cell, grouped by link.
    Shows correlated loss during congestion for cells sharing the same link.
    """
    ensure_output_dir()
    data_dir = data_dir or DATA_DIR
    _, pkt_stats = load_all_cells(data_dir, NUM_CELLS)
    bucketed, t_base, n_buckets = align_and_bucket_loss_simple(pkt_stats, bucket_sec)
    t_axis = t_base + np.arange(n_buckets) * bucket_sec

    n_links = len(topology)
    fig, axes = plt.subplots(n_links, 1, figsize=(12, 3 * n_links), sharex=True)
    if n_links == 1:
        axes = [axes]

    colors = ["#2ecc71", "#3498db", "#e74c3c"]
    for i, (link_id, cell_ids) in enumerate(topology.items()):
        ax = axes[i]
        for j, cid in enumerate(sorted(cell_ids)[:8]):  # max 8 cells per plot for clarity
            ax.plot(t_axis, bucketed[cid], alpha=0.6 + 0.05 * j, label=f"Cell {cid}")
        ax.set_ylabel("Loss fraction")
        ax.set_title(f"Link {link_id} - packet loss over time (cells sharing link correlate)")
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(-0.05, 1.05)
    axes[-1].set_xlabel("Time (s)")
    fig.suptitle("Traffic Pattern Snapshot: Correlated Packet Loss (Figure 1-style)", fontsize=14)
    plt.tight_layout()
    path = save_path or OUTPUT_DIR / "loss_correlation_over_time.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_capacity_results(
    topology: dict,
    cap_no_buf: dict,
    cap_with_buf: dict,
    save_path: Path,
    reduction_pct: dict = None,
):
    """Bar chart: capacity with vs without buffer per link. Optionally show bandwidth savings %."""
    ensure_output_dir()
    fig, ax = plt.subplots(figsize=(8, 5))
    links = sorted(topology.keys())
    x = np.arange(len(links))
    w = 0.35
    ax.bar(x - w / 2, [cap_no_buf[l] for l in links], w, label="No buffer", color="#e74c3c", alpha=0.8)
    ax.bar(x + w / 2, [cap_with_buf[l] for l in links], w, label="With buffer (4 sym)", color="#2ecc71", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([f"Link {l}" for l in links])
    ax.set_ylabel("Capacity (Gbps)")
    ax.set_title("Optimal Link Capacity for <=1% Packet Loss")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    for i, l in enumerate(links):
        ax.text(i - w / 2, cap_no_buf[l] + 1, f"{cap_no_buf[l]:.0f}", ha="center", fontsize=8)
        ax.text(i + w / 2, cap_with_buf[l] + 1, f"{cap_with_buf[l]:.0f}", ha="center", fontsize=8)
        if reduction_pct and l in reduction_pct:
            ax.text(i, -max(cap_no_buf.values()) * 0.08, f"-{int(reduction_pct[l])}%",
                    ha="center", fontsize=9, color="#2ecc71", fontweight="bold")
    if reduction_pct:
        ax.set_title("Optimal Link Capacity for <=1% Packet Loss (labels: bandwidth savings with buffer)")
    plt.tight_layout()
    fig.savefig(save_path, dpi=150, bbox_inches="tight")
    plt.close()


def run_all_visualizations(data_dir: Path = DATA_DIR):
    """Generate all plots."""
    topo, corr, cells = infer_topology(data_dir)
    topo, cap_nb, cap_wb, demand = estimate_all_capacities(data_dir, topology=topo)
    outliers = detect_topology_outliers(topo, corr, cells)
    reduction = compute_capacity_reduction(cap_nb, cap_wb)

    ensure_output_dir()
    plot_topology(topo, corr, cells, OUTPUT_DIR / "topology.png", outliers=outliers)
    plot_loss_correlation_over_time(topo, data_dir, OUTPUT_DIR / "loss_correlation_over_time.png")
    plot_traffic_patterns(demand, OUTPUT_DIR / "traffic_patterns.png")
    plot_capacity_results(topo, cap_nb, cap_wb, reduction_pct=reduction, save_path=OUTPUT_DIR / "capacity_results.png")
    print(f"Saved figures to {OUTPUT_DIR}")


if __name__ == "__main__":
    run_all_visualizations()
