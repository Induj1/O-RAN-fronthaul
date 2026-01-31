"""Configuration for O-RAN fronthaul optimization analysis."""

from pathlib import Path

# Data paths
DATA_DIR = Path(r"C:\Users\induj\Downloads\drive-download-20260131T064638Z-3-001")
OUTPUT_DIR = Path(__file__).parent / "output"

# O-RAN timing constants
SYMBOL_DURATION_US = 500 / 14  # ~35.7 µs
SLOT_DURATION_US = 500
SYMBOLS_PER_SLOT = 14
BUFFER_SYMBOLS = 4
BUFFER_DURATION_US = BUFFER_SYMBOLS * SYMBOL_DURATION_US  # ~143 µs
BUFFER_DURATION_SEC = BUFFER_DURATION_US / 1e6  # buffer = time × link_rate (bits)

# Requirements
MAX_PACKET_LOSS_PCT = 1.0  # %
NUM_CELLS = 24
NUM_SHARED_LINKS = 3

# Ground truth (Cell1->Link2, Cell2->Link3) - used to relabel clusters
TOPOLOGY_ANCHORS = {1: 2, 2: 3}  # cell_id -> link_id

# Limit analysis window (problem asks 60 sec for graphs)
CAPACITY_TIME_WINDOW_SEC = 60
