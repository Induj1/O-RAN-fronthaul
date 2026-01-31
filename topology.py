"""
Infer fronthaul topology by identifying which cells share the same Ethernet link.

Cells on the same link experience correlated packet loss when the link is congested.
Uses correlation of loss indicators with timestamp alignment (up to 1.5 sec shift).
"""

import numpy as np
import pandas as pd
from pathlib import Path
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform
from scipy.stats import pearsonr

from config import DATA_DIR, NUM_CELLS, NUM_SHARED_LINKS, TOPOLOGY_ANCHORS
from data_loader import load_all_cells


# Max timestamp shift between cells (seconds) - per README
MAX_SHIFT_SEC = 1.5
# Aggregation window for alignment - larger = fewer buckets, faster
BUCKET_SEC = 0.2  # 200ms windows (~400 slots each)


def align_and_bucket_loss_simple(pkt_stats: dict, bucket_sec: float = BUCKET_SEC) -> dict:
    """
    Simpler: per bucket, fraction of traffic slots that had loss.
    """
    all_t_min = min(ps["timestamp"].min() for ps in pkt_stats.values())
    all_t_max = max(ps["timestamp"].max() for ps in pkt_stats.values())
    n_buckets = int((all_t_max - all_t_min) / bucket_sec) + 1
    t_base = all_t_min

    bucketed = {}
    for cid, df in pkt_stats.items():
        arr = np.zeros(n_buckets)
        df = df.copy()
        df["bucket"] = ((df["timestamp"] - t_base) / bucket_sec).astype(int)
        df = df[(df["bucket"] >= 0) & (df["bucket"] < n_buckets)]
        g = df.groupby("bucket")
        # Fraction of slots with loss in this bucket
        loss_frac = g["loss_slot"].mean()
        for b, v in loss_frac.items():
            arr[int(b)] = v
        bucketed[cid] = arr
    return bucketed, t_base, n_buckets


def max_correlation_with_shift(a: np.ndarray, b: np.ndarray, max_shift: int) -> float:
    """Max Pearson correlation over shifts of b relative to a. Samples shifts to keep fast."""
    L = len(a)
    if L < 10:
        return 0.0
    # Sample shifts (every 2nd to speed up)
    step = max(1, max_shift // 8)
    shifts = list(range(-max_shift, max_shift + 1, step))
    if shifts[-1] != max_shift:
        shifts.append(max_shift)
    best = -1.0
    for s in shifts:
        if s >= 0:
            a_sub = a[: L - s] if s < L else a[:1]
            b_sub = b[s:L] if s < L else b[-1:]
        else:
            a_sub = a[-s:L] if -s < L else a[-1:]
            b_sub = b[: L + s] if -s < L else b[:1]
        if len(a_sub) < 10 or len(b_sub) < 10:
            continue
        mn = min(len(a_sub), len(b_sub))
        a_sub, b_sub = a_sub[:mn].astype(float), b_sub[:mn].astype(float)
        r, _ = pearsonr(a_sub, b_sub)
        if np.isfinite(r) and r > best:
            best = r
    return max(best, 0.0)


def build_correlation_matrix(pkt_stats: dict, bucket_sec: float = BUCKET_SEC) -> np.ndarray:
    """Build cell-to-cell correlation matrix of packet loss (with alignment)."""
    bucketed, _, n_buckets = align_and_bucket_loss_simple(pkt_stats, bucket_sec)
    max_shift = int(MAX_SHIFT_SEC / bucket_sec)

    n = NUM_CELLS
    corr = np.eye(n)
    cells = sorted(bucketed.keys())
    idx = {c: i for i, c in enumerate(cells)}

    for i, ci in enumerate(cells):
        for j, cj in enumerate(cells):
            if i >= j:
                continue
            r = max_correlation_with_shift(
                bucketed[ci], bucketed[cj], max_shift
            )
            corr[i, j] = corr[j, i] = r
    return corr, cells


def cluster_cells(corr: np.ndarray, n_clusters: int = NUM_SHARED_LINKS) -> list:
    """
    Cluster cells by loss correlation. High correlation -> same link.
    Use distance = 1 - correlation, then hierarchical clustering.
    """
    dist = 1 - np.clip(corr, 0, 1)
    np.fill_diagonal(dist, 0)
    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method="average")
    labels = fcluster(Z, n_clusters, criterion="maxclust")
    return labels.tolist()


def infer_topology(data_dir: Path = DATA_DIR) -> dict:
    """
    Infer which cells share each Ethernet link.
    Returns: {link_id: [cell_ids]}
    """
    _, pkt_stats = load_all_cells(data_dir, NUM_CELLS)
    corr, cells = build_correlation_matrix(pkt_stats)
    labels = cluster_cells(corr, NUM_SHARED_LINKS)

    # Relabel clusters using ground truth: Cell1->Link2, Cell2->Link3
    label_to_cells = {}
    for i, cid in enumerate(cells):
        lab = labels[i]
        label_to_cells.setdefault(lab, []).append(cid)
    # Map cluster labels to link IDs so anchors are satisfied
    link_assignment = {}  # cluster_label -> link_id
    used_links = set()
    for cell_id, required_link in TOPOLOGY_ANCHORS.items():
        if cell_id not in cells or required_link in used_links:
            continue
        idx = cells.index(cell_id)
        lab = labels[idx]
        if lab not in link_assignment:
            link_assignment[lab] = required_link
            used_links.add(required_link)
    remaining_links = set(range(1, NUM_SHARED_LINKS + 1)) - used_links
    for lab in label_to_cells:
        if lab not in link_assignment:
            link_assignment[lab] = remaining_links.pop()
    topology = {link_id: [] for link_id in range(1, NUM_SHARED_LINKS + 1)}
    for i, cid in enumerate(cells):
        link_id = link_assignment[labels[i]]
        topology[link_id].append(cid)
    return topology, corr, cells


def compute_topology_confidence(
    topology: dict, corr: np.ndarray, cells: list
) -> dict:
    """
    Mean intra-cluster correlation per link, normalized to [0, 100].
    confidence = mean_corr / max_corr (max_corr=1.0)
    """
    idx = {c: i for i, c in enumerate(cells)}
    confidence = {}
    for link_id, cell_ids in topology.items():
        if len(cell_ids) < 2:
            # Single cell: use max correlation with any other cell (inverted)
            if len(cell_ids) == 1:
                i0 = idx[cell_ids[0]]
                others = [corr[i0, j] for j in range(len(cells)) if j != i0]
                max_other = max(others) if others else 0.0
                confidence[link_id] = round(100 * max_other, 0)  # low corr with others = low confidence
            else:
                confidence[link_id] = 0
            continue
        pairs = []
        for a in cell_ids:
            for b in cell_ids:
                if a < b:
                    pairs.append(corr[idx[a], idx[b]])
        confidence[link_id] = round(100 * np.mean(pairs) / 1.0, 0) if pairs else 0
    return confidence


def detect_topology_outliers(
    topology: dict, corr: np.ndarray, cells: list, threshold: float = 0.2
) -> dict:
    """
    Single-cell links where max correlation with any other cell < threshold.
    Returns {link_id: (cell_id, max_corr)} for outlier links.
    """
    idx = {c: i for i, c in enumerate(cells)}
    outliers = {}
    for link_id, cell_ids in topology.items():
        if len(cell_ids) != 1:
            continue
        cid = cell_ids[0]
        i0 = idx[cid]
        max_corr = max(corr[i0, j] for j in range(len(cells)) if j != i0) if len(cells) > 1 else 0.0
        if max_corr < threshold:
            outliers[link_id] = (cid, float(max_corr))
    return outliers


if __name__ == "__main__":
    topo, corr, cells = infer_topology()
    print("Inferred topology (cells per link):")
    for link, cids in topo.items():
        print(f"  Link {link}: {sorted(cids)}")
