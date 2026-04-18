"""
Experiment tracking — version and compare strategy, prompt, and parameter changes.
"""

import json
from pathlib import Path
from typing import List, Optional
from backend.core.time_utils import utc_timestamp


class ExperimentTracker:
    """Tracks experiment versions for strategies, prompts, and configurations."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.experiments_file = data_dir / "experiments.json"

    def _load(self) -> List[dict]:
        try:
            if self.experiments_file.exists():
                return json.loads(self.experiments_file.read_text())
        except Exception:
            pass
        return []

    def _save(self, experiments: List[dict]):
        self.experiments_file.write_text(
            json.dumps(experiments, indent=2, default=str)
        )

    def log_experiment(self, name: str, config: dict, results: dict,
                       description: str = "") -> dict:
        """Log a backtest or evaluation experiment.

        Args:
            name: experiment name (e.g., "backtest_v1_london_only")
            config: configuration used (strategies, params, data range, etc.)
            results: metrics from the experiment
            description: human-readable description
        """
        experiment = {
            "id": len(self._load()) + 1,
            "name": name,
            "timestamp": utc_timestamp(),
            "description": description,
            "config": config,
            "results": results,
        }
        experiments = self._load()
        experiments.append(experiment)
        self._save(experiments)
        return experiment

    def get_all(self) -> List[dict]:
        return self._load()

    def get_by_name(self, name: str) -> List[dict]:
        return [e for e in self._load() if e.get("name") == name]

    def compare(self, id_1: int, id_2: int) -> Optional[dict]:
        """Compare two experiments by ID."""
        experiments = self._load()
        e1 = next((e for e in experiments if e["id"] == id_1), None)
        e2 = next((e for e in experiments if e["id"] == id_2), None)
        if not e1 or not e2:
            return None

        r1 = e1.get("results", {})
        r2 = e2.get("results", {})

        comparison = {
            "experiment_1": {"id": id_1, "name": e1["name"]},
            "experiment_2": {"id": id_2, "name": e2["name"]},
            "metrics_comparison": {},
        }

        for key in ("win_rate", "expectancy", "profit_factor", "sharpe",
                     "max_drawdown_r", "total_trades", "total_r"):
            v1 = r1.get(key)
            v2 = r2.get(key)
            if v1 is not None and v2 is not None:
                try:
                    comparison["metrics_comparison"][key] = {
                        "exp_1": v1, "exp_2": v2,
                        "diff": round(float(v2) - float(v1), 4),
                    }
                except (TypeError, ValueError):
                    comparison["metrics_comparison"][key] = {"exp_1": v1, "exp_2": v2}

        return comparison
