"""
Data loading and preprocessing for O-RAN fronthaul analysis.

Loads throughput (symbol-level) and pkt-stats (slot-level) files,
with proper sorting, outlier removal, and timestamp alignment.
"""

import numpy as np
import pandas as pd
from pathlib import Path

from config import DATA_DIR, SYMBOL_DURATION_US, SLOT_DURATION_US


def load_throughput(cell_id: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    Load and preprocess throughput data for a cell.
    - Sort by timestamp
    - Replace measurement outliers (unusually high bits) with 0
    """
    path = data_dir / f"throughput-cell-{cell_id}.dat"
    df = pd.read_csv(path, sep=r"\s+", header=None, names=["timestamp", "bits_kbit"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Outlier removal: symbols with unusually high bits are measurement errors
    if len(df) > 0:
        q99 = df["bits_kbit"].quantile(0.99)
        threshold = max(q99 * 2, df["bits_kbit"].median() * 10) if q99 > 0 else 1e9
        df.loc[df["bits_kbit"] > threshold, "bits_kbit"] = 0

    return df


def load_pkt_stats(cell_id: int, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """
    Load packet stats for a cell (slot-level).
    Format: timestamp (slotStart), txPackets, rxPackets, tooLateRxPackets
    """
    path = data_dir / f"pkt-stats-cell-{cell_id}.dat"
    df = pd.read_csv(
        path, sep=r"\s+", header=None, skiprows=1,
        names=["timestamp", "tx_packets", "rx_packets", "too_late_rx"]
    )
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["lost_packets"] = df["tx_packets"] - df["rx_packets"] + df["too_late_rx"]
    df["total_tx"] = df["tx_packets"]
    df["loss_slot"] = df["lost_packets"] > 0  # binary: slot had loss or not
    return df


def load_all_cells(data_dir: Path = DATA_DIR, num_cells: int = 24):
    """Load throughput and pkt-stats for all cells."""
    throughput = {}
    pkt_stats = {}
    for cid in range(1, num_cells + 1):
        throughput[cid] = load_throughput(cid, data_dir)
        pkt_stats[cid] = load_pkt_stats(cid, data_dir)
    return throughput, pkt_stats


if __name__ == "__main__":
    # Quick sanity check
    t1 = load_throughput(1)
    p1 = load_pkt_stats(1)
    print("Throughput cell 1:", t1.shape, t1.head())
    print("Pkt-stats cell 1:", p1.shape, p1.head())
    print("Pkt-stats loss sample:", p1[p1["loss_slot"]].head())
