"""
Estimate optimal Ethernet link capacity for ≤1% packet loss.

- Without buffer: capacity must meet peak demand (high percentile)
- With buffer (4 symbols = 143 µs): can absorb short bursts, so lower capacity suffices
"""

import numpy as np
import pandas as pd
from pathlib import Path

from config import (
    DATA_DIR,
    SYMBOL_DURATION_US,
    SLOT_DURATION_US,
    SYMBOLS_PER_SLOT,
    BUFFER_SYMBOLS,
    BUFFER_DURATION_SEC,
    MAX_PACKET_LOSS_PCT,
    NUM_CELLS,
    CAPACITY_TIME_WINDOW_SEC,
)
from data_loader import load_throughput, load_pkt_stats, load_all_cells
from topology import infer_topology


def bits_to_gbps(bits: float, duration_sec: float) -> float:
    """Convert bits over duration to Gbps."""
    if duration_sec <= 0:
        return 0.0
    return bits * 1000 / duration_sec / 1e9  # bits are in kbit


def aggregate_link_demand_slot_level(
    topology: dict,
    data_dir: Path = DATA_DIR,
    throughput_cache: dict | None = None,
) -> dict:
    """
    Per link: aggregate symbol-level throughput from all cells, then convert to slot-level.
    Returns {link_id: (slot_ts, demand_gbps, per_cell_traffic, per_cell_demand_gbps)}.
    per_cell_traffic: {cell_id: bool array} True where cell had traffic.
    per_cell_demand_gbps: {cell_id: array} Gbps per slot for root-cause attribution.
    """
    symbol_dur_sec = SYMBOL_DURATION_US / 1e6
    slot_dur_sec = SLOT_DURATION_US / 1e6
    if throughput_cache is None:
        throughput_cache = {}

    def get_throughput(cid):
        if cid not in throughput_cache:
            throughput_cache[cid] = load_throughput(cid, data_dir)
        return throughput_cache[cid]

    results = {}
    for link_id, cell_ids in topology.items():
        if not cell_ids:
            results[link_id] = (np.array([]), np.array([]), {}, {})
            continue

        t0, t1 = float("inf"), float("-inf")
        for cid in cell_ids:
            df = get_throughput(cid)
            t0 = min(t0, df["timestamp"].min())
            t1 = max(t1, df["timestamp"].max())
        if CAPACITY_TIME_WINDOW_SEC is not None:
            t1 = min(t1, t0 + CAPACITY_TIME_WINDOW_SEC)

        n_symbols = int((t1 - t0) / symbol_dur_sec) + 1
        if n_symbols < SYMBOLS_PER_SLOT:
            results[link_id] = (np.array([]), np.array([]), {}, {})
            continue

        combined_bits = np.zeros(n_symbols)
        per_cell_bits = {cid: np.zeros(n_symbols) for cid in cell_ids}
        for cid in cell_ids:
            df = get_throughput(cid)
            df = df[(df["timestamp"] >= t0) & (df["timestamp"] <= t1)]
            if len(df) == 0:
                continue
            idx = ((df["timestamp"].values - t0) / symbol_dur_sec).round().astype(int)
            idx = np.clip(idx, 0, n_symbols - 1)
            bits = df["bits_kbit"].values * 1000
            np.add.at(combined_bits, idx, bits)
            np.add.at(per_cell_bits[cid], idx, bits)

        # Aggregate to slots
        n_slots = n_symbols // SYMBOLS_PER_SLOT
        trimmed = combined_bits[: n_slots * SYMBOLS_PER_SLOT]
        slot_bits = trimmed.reshape(n_slots, SYMBOLS_PER_SLOT).sum(axis=1)
        slot_ts = t0 + (np.arange(n_slots) + 0.5) * slot_dur_sec
        demand_gbps = slot_bits / (slot_dur_sec * 1e9)

        # Per-cell traffic and demand (for root-cause attribution)
        per_cell_traffic = {}
        per_cell_demand_gbps = {}
        for cid in cell_ids:
            pc = per_cell_bits[cid][: n_slots * SYMBOLS_PER_SLOT].reshape(n_slots, SYMBOLS_PER_SLOT).sum(axis=1)
            d = pc / (slot_dur_sec * 1e9)
            per_cell_demand_gbps[cid] = d
            per_cell_traffic[cid] = d > 0.01
        results[link_id] = (slot_ts, demand_gbps, per_cell_traffic, per_cell_demand_gbps)

    return results


def get_traffic_slots_mask(pkt_stats: dict, cell_ids: list) -> np.ndarray:
    """
    For a link (set of cells), a slot has traffic if any cell had tx > 0.
    We need to align pkt-stats slots with our demand slots - use time overlap.
    Returns mask over our slot array (True = traffic in that slot).
    """
    # For simplicity: assume most slots have traffic when any cell has traffic
    # We'll use the demand > 0 as traffic indicator instead, since demand is from throughput
    return None  # Caller will use demand > 0


def capacity_without_buffer(
    slot_demand_gbps: np.ndarray,
    traffic_mask: np.ndarray | None,
    per_cell_traffic: dict | None = None,
    max_loss_pct: float = MAX_PACKET_LOSS_PCT,
) -> float:
    """
    Capacity needed so that ≤ max_loss_pct of traffic slots experience demand > capacity.
    Per-cell: for each cell, ≤1% of its traffic slots may have demand > C.
    C = max over cells of (100 - max_loss_pct) percentile of demand in that cell's traffic slots.
    """
    if len(slot_demand_gbps) == 0:
        return 0.0
    pct = 100 - max_loss_pct
    if per_cell_traffic and len(per_cell_traffic) > 0:
        caps = []
        for cid, cell_mask in per_cell_traffic.items():
            vals = slot_demand_gbps[cell_mask]
            if len(vals) > 0:
                caps.append(np.percentile(vals, pct))
        return float(max(caps)) if caps else float(np.max(slot_demand_gbps))
    if traffic_mask is not None and traffic_mask.any():
        vals = slot_demand_gbps[traffic_mask]
    else:
        vals = slot_demand_gbps[slot_demand_gbps > 0]
    if len(vals) == 0:
        return float(np.max(slot_demand_gbps))
    return float(np.percentile(vals, pct))


def capacity_with_buffer(
    slot_ts: np.ndarray,
    slot_demand_gbps: np.ndarray,
    per_cell_traffic: dict | None = None,
    max_loss_pct: float = MAX_PACKET_LOSS_PCT,
) -> float:
    """
    Buffer size = 143 µs × link_rate (per problem: buffer in bits = time × rate).
    Per-cell constraint: each cell has ≤1% of its traffic slots with loss.
    """
    if len(slot_demand_gbps) == 0:
        return 0.0
    slot_dur_sec = SLOT_DURATION_US / 1e6

    def sim_max_cell_loss(C: float) -> float:
        buffer_gb = BUFFER_DURATION_SEC * C  # 143µs × link_rate in Gb
        buffer = 0.0
        loss_in_slot = np.zeros(len(slot_demand_gbps), dtype=bool)
        for i, d in enumerate(slot_demand_gbps):
            if d <= 0:
                continue
            overflow = max(0, (d - C) * slot_dur_sec)
            buffer += overflow
            if buffer > buffer_gb:
                loss_in_slot[i] = True
                buffer = buffer_gb
            drain = min(buffer, C * slot_dur_sec) if C > 0 else 0
            buffer = max(0, buffer - drain)
        if per_cell_traffic and len(per_cell_traffic) > 0:
            max_pct = 0.0
            for cid, cell_mask in per_cell_traffic.items():
                traffic_slots = np.sum(cell_mask)
                if traffic_slots == 0:
                    continue
                loss_slots = np.sum(cell_mask & loss_in_slot)
                max_pct = max(max_pct, 100 * loss_slots / traffic_slots)
            return max_pct
        traffic_slots = np.sum(slot_demand_gbps > 0)
        if traffic_slots == 0:
            return 0.0
        return 100 * np.sum(loss_in_slot) / traffic_slots

    lo, hi = 0.0, float(np.max(slot_demand_gbps)) * 1.1
    for _ in range(50):
        mid = (lo + hi) / 2
        if sim_max_cell_loss(mid) <= max_loss_pct:
            hi = mid
        else:
            lo = mid
    return hi


def estimate_all_capacities(
    data_dir: Path = DATA_DIR,
    topology: dict | None = None,
) -> tuple[dict, dict, dict, dict]:
    """
    Estimate capacity for each link, with and without buffer.
    Returns: (topology, capacity_no_buf, capacity_with_buf, demand)
    """
    if topology is None:
        topology, _, _ = infer_topology(data_dir)
    demand = aggregate_link_demand_slot_level(topology, data_dir)

    # Need to pass throughput - aggregate_link expects it but we load inside. Fix.
    cap_no_buf = {}
    cap_with_buf = {}
    for link_id, item in demand.items():
        slot_ts = item[0]
        demand_gbps = item[1]
        per_cell_traffic = item[2] if len(item) > 2 else {}
        per_cell_demand_gbps = item[3] if len(item) > 3 else {}
        traffic_mask = demand_gbps > 0.01
        if not traffic_mask.any():
            traffic_mask = np.ones(len(demand_gbps), dtype=bool)
        cap_no_buf[link_id] = capacity_without_buffer(
            demand_gbps, traffic_mask, per_cell_traffic=per_cell_traffic
        )
        cap_with_buf[link_id] = capacity_with_buffer(
            slot_ts, demand_gbps, per_cell_traffic=per_cell_traffic
        )

    return topology, cap_no_buf, cap_with_buf, demand


def compute_capacity_reduction(
    cap_no_buf: dict, cap_with_buf: dict
) -> dict:
    """Bandwidth savings % from buffering: (no_buf - with_buf) / no_buf * 100."""
    reduction = {}
    for link_id in cap_no_buf:
        nb, wb = cap_no_buf[link_id], cap_with_buf[link_id]
        reduction[link_id] = round(100 * (nb - wb) / nb, 0) if nb > 0 else 0
    return reduction


def root_cause_attribution(
    demand: dict,
    cap_with_buf: dict,
    topology: dict,
    max_events_per_link: int = 5,
) -> dict:
    """
    For congestion events (demand > capacity), identify top 2 cells by traffic contribution.
    Returns {link_id: [(t, [(cell_id, pct), ...]), ...]}
    """
    events = {}
    for link_id, item in demand.items():
        if len(item) < 4:
            continue
        slot_ts, demand_gbps, _, per_cell_demand = item[0], item[1], item[2], item[3]
        cap = cap_with_buf.get(link_id, 0)
        if cap <= 0 or not per_cell_demand:
            continue
        cong_slots = np.where(demand_gbps > cap)[0]
        link_events = []
        for idx in cong_slots[:max_events_per_link]:
            t = float(slot_ts[idx])
            total = demand_gbps[idx]
            if total <= 0:
                continue
            contribs = [(cid, 100 * per_cell_demand[cid][idx] / total) for cid in per_cell_demand]
            contribs = [(c, p) for c, p in contribs if p > 0]
            contribs.sort(key=lambda x: -x[1])
            link_events.append((t, contribs[:2]))
        if link_events:
            events[link_id] = link_events
    return events


if __name__ == "__main__":
    topo, cap_nb, cap_wb, demand = estimate_all_capacities()
    print("Capacity estimates (Gbps) for <=1% packet loss:")
    for link_id in sorted(topo.keys()):
        print(f"  Link {link_id}: no buffer = {cap_nb[link_id]:.2f} Gbps, with buffer = {cap_wb[link_id]:.2f} Gbps")
