# O-RAN Fronthaul Optimization

Hackathon solution for inferring fronthaul topology and estimating optimal Ethernet link capacity.

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to set:
- `DATA_DIR`: path to folder with `throughput-cell-*.dat` and `pkt-stats-cell-*.dat`
- `CAPACITY_TIME_WINDOW_SEC`: analysis window (default 30s; set `None` for full data)

## Run

```bash
python main.py
```

Outputs:
- Console: inferred topology and capacity estimates
- `output/`: topology diagram, traffic patterns, capacity bar chart

## Pipeline

1. **Topology inference**: Cluster cells by correlated packet loss (cells on same link lose packets together). Uses 200ms buckets, timestamp alignment up to 1.5s.
2. **Capacity estimation**:
   - **No buffer**: 99th percentile of slot-level aggregate demand
   - **With buffer** (4 symbols = 143 µs): binary search for min capacity achieving ≤1% slot loss
3. **Visualization**: Topology + correlation heatmap, traffic time series, capacity comparison

## Constraints

- 14 symbols = 1 slot = 500 µs
- Buffer = 4 symbols
- Target: packet loss ≤ 1% of traffic slots
- Exactly 3 shared Ethernet links
