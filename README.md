# O-RAN Fronthaul Optimization

Hackathon solution for inferring fronthaul topology and estimating optimal Ethernet link capacity.

## Deploy Backend on Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Induj1/O-RAN-fronthaul)

1. Push this repo to GitHub.
2. Click the button above (replace `YOUR_USERNAME/YOUR_REPO` with your repo URL).
3. Connect your GitHub account and apply. The API will serve `output/results.json` (static mode).
4. Your API URL: `https://pocket-noc-api.onrender.com` (or as shown in Render).

See [DEPLOY_RENDER.md](DEPLOY_RENDER.md) for details.

## Setup

```bash
pip install -r requirements.txt
```

## Configuration

Edit `config.py` to set:
- `DATA_DIR`: path to folder with `throughput-cell-*.dat` and `pkt-stats-cell-*.dat`
- `CAPACITY_TIME_WINDOW_SEC`: analysis window (60s default; set `None` for full data)

## Run

```bash
python main.py              # Standard run
python main.py --ml         # With optional ML validation
python main.py --json       # Write output/results.json for frontend
python main.py --ml --json  # Both
```

Outputs:
- Console: topology, capacity, confidence, bandwidth savings, root-cause attribution
- `output/`: topology diagram, loss correlation, traffic patterns, capacity bar chart

## Approach: Interpretability + ML Validation

**Core method (interpretable):** Correlation-based clustering and percentile-based capacity estimation. Operators can inspect correlations, understand why cells are grouped, and trace capacity to demand percentiles. No black box.

**Why this over pure ML?** Telecom operators need debuggable, explainable solutions. "Cell A and B share a link because their packet loss correlates at 0.87" is actionable; a neural network output is not.

**Optional ML (validation):** When run with `--ml`, we use:
- **Random Forest** to validate topology: predicts same/different link from pairwise features (correlation, cell distance). Cross-validation reports agreement with our clustering.
- **Gradient Boosting** to validate capacity: predicts required capacity from demand stats (mean, std, p99). Compares with our percentile-based estimates.

ML augments, not replaces: it provides confidence checks and supports the interpretable core.

## Pipeline

1. **Topology inference**: Cluster cells by correlated packet loss (200ms buckets, timestamp alignment up to 1.5s). Ground-truth anchors (Cell1→Link2, Cell2→Link3) relabel clusters.
2. **Capacity estimation**: 99th percentile (no buffer); buffer-aware simulation for ≤1% loss (with buffer). Per-cell loss constraint. Buffer = 143 µs × link rate.
3. **Visualization**: Topology, loss correlation over time, traffic patterns, capacity + bandwidth savings.
4. **Novelty**: Topology confidence, outlier detection, root-cause attribution, capacity reduction gauge.

## Constraints

- 14 symbols = 1 slot = 500 µs
- Buffer = 4 symbols (143 µs)
- Target: packet loss ≤ 1% of traffic slots per cell
- Exactly 3 shared Ethernet links
