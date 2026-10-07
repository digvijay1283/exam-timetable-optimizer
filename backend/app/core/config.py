"""Default weights and domain vocabularies. See docs/SPEC_DECISIONS.md."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Weights:
    """Penalty weights (PRD section 7). Hard constraints dominate all soft terms."""

    hard: float = 10_000  # WH
    consecutive: float = 100  # WC
    gap: float = 40  # WG
    distribution: float = 20  # WD
    slot_pref: float = 10  # WS
    room_util: float = 5  # WR


@dataclass(frozen=True)
class ConstraintParams:
    # Exams on different days no more than this many calendar days apart count as a short gap.
    short_gap_days: int = 1
    # H8: a student sits at most one exam per day (exams sharing students go on different days).
    one_exam_per_day: bool = True


# Room types each exam type may use. Unknown exam types may use any room.
EXAM_ROOM_COMPAT: dict[str, frozenset[str]] = {
    "theory": frozenset({"classroom", "hall"}),
    "practical": frozenset({"lab"}),
}

DEFAULT_ROOM_TYPE = "classroom"
