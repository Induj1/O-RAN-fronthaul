"""
Optional ML validation for topology and capacity estimates.

Augments the interpretable correlation-based approach:
- Topology: Random Forest classifier validates "same link" predictions from pairwise features
- Capacity: Gradient Boosting regressor cross-checks capacity from demand statistics

Design choice: Core logic remains correlation + clustering (interpretable, debuggable).
ML is used for validation and confidence, not as a black-box replacement.
"""

import numpy as np
from pathlib import Path
from typing import Optional

try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingRegressor
    from sklearn.model_selection import cross_val_score
    from sklearn.metrics import accuracy_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from config import NUM_CELLS


def _build_pairwise_features(
    corr: np.ndarray,
    topology: dict,
    cells: list,
) -> tuple[np.ndarray, np.ndarray]:
    """
    For each pair (i,j), build features and label (1=same link, 0=different).
    Features: correlation, |i-j| (cell index distance), etc.
    """
    idx = {c: i for i, c in enumerate(cells)}
    link_of = {}
    for lid, cids in topology.items():
        for c in cids:
            link_of[c] = lid

    X, y = [], []
    for i, ci in enumerate(cells):
        for j, cj in enumerate(cells):
            if i >= j:
                continue
            corr_ij = corr[i, j]
            feat = [
                corr_ij,
                abs(ci - cj) / NUM_CELLS,
                np.sqrt(corr_ij) if corr_ij > 0 else 0,
            ]
            X.append(feat)
            y.append(1 if link_of.get(ci) == link_of.get(cj) else 0)
    return np.array(X), np.array(y)


def ml_validate_topology(
    topology: dict,
    corr: np.ndarray,
    cells: list,
) -> dict:
    """
    Train RF to predict same/different link from pairwise features.
    Returns validation metrics. Uses inferred topology as labels (self-consistency check).
    """
    if not SKLEARN_AVAILABLE:
        return {"available": False, "reason": "scikit-learn not installed"}

    X, y = _build_pairwise_features(corr, topology, cells)
    if len(np.unique(y)) < 2:
        return {"available": True, "accuracy": 1.0, "note": "Insufficient label diversity"}

    clf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    scores = cross_val_score(clf, X, y, cv=min(5, len(X) // 4 or 1), scoring="accuracy")
    clf.fit(X, y)
    pred = clf.predict(X)
    train_acc = accuracy_score(y, pred)

    return {
        "available": True,
        "cv_accuracy_mean": float(np.mean(scores)),
        "cv_accuracy_std": float(np.std(scores)),
        "train_accuracy": float(train_acc),
        "n_pairs": len(y),
        "feature_importance": dict(
            zip(["correlation", "cell_distance", "sqrt_corr"], clf.feature_importances_.tolist())
        ),
    }


def ml_validate_capacity(
    topology: dict,
    demand: dict,
    cap_with_buf: dict,
) -> dict:
    """
    Train GB regressor: predict capacity from link-level demand stats.
    Compare predictions with our percentile-based estimates.
    """
    if not SKLEARN_AVAILABLE:
        return {"available": False, "reason": "scikit-learn not installed"}

    X, y = [], []
    for link_id, item in demand.items():
        if len(item) < 2:
            continue
        demand_gbps = item[1]
        if len(demand_gbps) < 10:
            continue
        cap = cap_with_buf.get(link_id, 0)
        if cap <= 0:
            continue
        n_cells = len(topology.get(link_id, []))
        feat = [
            n_cells,
            np.mean(demand_gbps),
            np.std(demand_gbps),
            np.percentile(demand_gbps, 99),
            np.max(demand_gbps),
        ]
        X.append(feat)
        y.append(cap)

    if len(X) < 2:
        return {"available": True, "mae": 0, "note": "Insufficient links for regression"}

    X, y = np.array(X), np.array(y)
    reg = GradientBoostingRegressor(n_estimators=30, max_depth=3, random_state=42)
    reg.fit(X, y)
    pred = reg.predict(X)
    mae = float(np.mean(np.abs(pred - y)))
    mape = float(np.mean(np.abs((pred - y) / (y + 1e-9))) * 100)

    return {
        "available": True,
        "mae_gbps": mae,
        "mape_pct": mape,
        "n_links": len(X),
        "feature_importance": dict(
            zip(["n_cells", "mean_demand", "std_demand", "p99_demand", "max_demand"],
                reg.feature_importances_.tolist()),
        ),
    }


def run_ml_validation(
    topology: dict,
    corr: np.ndarray,
    cells: list,
    demand: dict,
    cap_with_buf: dict,
) -> dict:
    """Run all ML validation steps. Returns combined report."""
    topo_result = ml_validate_topology(topology, corr, cells)
    cap_result = ml_validate_capacity(topology, demand, cap_with_buf)
    return {"topology": topo_result, "capacity": cap_result}
