"""Cross-message correlation (pairwise, stateless) - Phase 4.5."""

from cbpr_validate.match.matcher import UnsupportedPairError, correlate
from cbpr_validate.match.result import (
    Direction,
    MatchKey,
    MatchResult,
    MessageRef,
    Scenario,
)

__all__ = [
    "Direction",
    "MatchKey",
    "MatchResult",
    "MessageRef",
    "Scenario",
    "UnsupportedPairError",
    "correlate",
]
