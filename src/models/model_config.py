"""Model configuration for multi-model support.

A ModelConfig defines a named set of strategies trained with a specific
data configuration (time period, strategy selection).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DataFilter:
    """Data filtering configuration for training."""

    years: int | None = None  # Number of years of data (None = all)


@dataclass
class ModelConfig:
    """A named model configuration."""

    slug: str
    name: str
    strategies: list[str] = field(default_factory=lambda: ["xgboost", "poisson", "elo", "logreg"])
    data_filter: DataFilter = field(default_factory=DataFilter)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_default: bool = False

    def __post_init__(self) -> None:
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", self.slug):
            raise ValueError(f"Invalid slug: {self.slug!r} (must be lowercase alphanumeric with hyphens)")
        if not self.name:
            raise ValueError("name cannot be empty")
        if not self.strategies:
            raise ValueError("strategies cannot be empty")

    def save(self, models_dir: Path) -> None:
        """Save config to models/<slug>/config.json."""
        config_dir = models_dir / self.slug
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.json"
        config_path.write_text(json.dumps(self._to_dict(), indent=2, ensure_ascii=False))

    def _to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "strategies": self.strategies,
            "data_filter": {"years": self.data_filter.years},
            "created_at": self.created_at,
            "is_default": self.is_default,
        }

    @classmethod
    def load(cls, config_path: Path) -> ModelConfig:
        """Load config from a config.json file."""
        data = json.loads(config_path.read_text())
        return cls(
            slug=data["slug"],
            name=data["name"],
            strategies=data.get("strategies", ["xgboost", "poisson", "elo", "logreg"]),
            data_filter=DataFilter(years=data.get("data_filter", {}).get("years")),
            created_at=data.get("created_at", ""),
            is_default=data.get("is_default", False),
        )

    @classmethod
    def list_all(cls, models_dir: Path) -> list[ModelConfig]:
        """List all model configs found in models_dir."""
        configs = []
        if not models_dir.is_dir():
            return configs
        for config_path in sorted(models_dir.glob("*/config.json")):
            configs.append(cls.load(config_path))
        return configs
