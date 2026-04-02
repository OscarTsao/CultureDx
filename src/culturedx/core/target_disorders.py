"""Canonical benchmark target disorder helpers."""
from __future__ import annotations

from pathlib import Path

from omegaconf import OmegaConf

FINAL_TARGET_DISORDERS = [
    "F20",
    "F31",
    "F32",
    "F39",
    "F41.0",
    "F41.1",
    "F42",
    "F43.1",
    "F43.2",
    "F45",
    "F51",
    "F98",
]
FINAL_TARGET_DISORDERS_CONFIG_PATH = (
    Path(__file__).resolve().parents[3]
    / "configs"
    / "targets"
    / "lingxidiag_12class.yaml"
)


def load_final_target_disorders() -> list[str]:
    """Load the canonical benchmark target disorders, falling back if missing."""
    if not FINAL_TARGET_DISORDERS_CONFIG_PATH.exists():
        return list(FINAL_TARGET_DISORDERS)

    cfg = OmegaConf.load(str(FINAL_TARGET_DISORDERS_CONFIG_PATH))
    plain = OmegaConf.to_container(cfg, resolve=True)
    disorders = plain.get("target_disorders") if isinstance(plain, dict) else None
    if isinstance(disorders, list) and all(isinstance(code, str) for code in disorders):
        return list(disorders)

    raise ValueError(
        f"Invalid target_disorders config at {FINAL_TARGET_DISORDERS_CONFIG_PATH}"
    )
