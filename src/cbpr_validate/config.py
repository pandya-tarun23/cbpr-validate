"""Environment-driven configuration.

The only thing that genuinely has to be configured is the XSD directory: this
project never ships SWIFT schemas, so a user who wants the optional structural
layer points it at their own licensed copy.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENV_XSD_DIR = "CBPR_VALIDATE_XSD_DIR"


@dataclass(frozen=True)
class Settings:
    """Resolved settings. Immutable; re-read from the environment on demand."""

    xsd_dir: Path | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        raw = source.get(ENV_XSD_DIR)
        return cls(xsd_dir=Path(raw) if raw else None)


def get_settings() -> Settings:
    """Read settings from the process environment.

    Deliberately not cached: the CLI, the API and the tests all expect an
    environment change to take effect without re-importing the package.
    """
    return Settings.from_env()
