"""Exam slot generation (PRD FR-05)."""
from __future__ import annotations

from datetime import date, time, timedelta
from typing import Iterable, Sequence

from app.core.domain import Slot

# Default (start, end) times per day for 1-3 slots/day. Slots are 150-180 minutes long.
DEFAULT_SLOT_TIMES: dict[int, list[tuple[str, str]]] = {
    1: [("10:00", "13:00")],
    2: [("09:30", "12:30"), ("14:00", "17:00")],
    3: [("09:00", "11:30"), ("12:30", "15:00"), ("15:30", "18:00")],
}

MON_FRI = (0, 1, 2, 3, 4)
_MAX_DAYS = 3650


def generate_slots(
    start_date: date,
    end_date: date | None = None,
    *,
    slots_per_day: int = 2,
    working_days: Sequence[int] = MON_FRI,
    slot_times: Sequence[tuple[str, str]] | None = None,
    holidays: Iterable[date] = (),
    min_slots: int | None = None,
) -> list[Slot]:
    """Generate chronological slots on working days.

    Provide `end_date` to fill a fixed window, or `min_slots` (with no `end_date`) to extend
    day by day until at least that many slots exist. `working_days` uses Monday=0.
    """
    if end_date is None and min_slots is None:
        raise ValueError("provide end_date or min_slots")
    if not working_days:
        raise ValueError("working_days must not be empty")
    times = list(slot_times) if slot_times is not None else DEFAULT_SLOT_TIMES.get(slots_per_day)
    if times is None:
        raise ValueError(f"no default slot times for {slots_per_day} slots/day; pass slot_times")
    if len(times) != slots_per_day:
        raise ValueError(f"slot_times has {len(times)} entries but slots_per_day={slots_per_day}")

    skip = set(holidays)
    raw: list[tuple[date, int, time, time]] = []
    day = start_date
    for _ in range(_MAX_DAYS):
        if end_date is not None and day > end_date:
            break
        if end_date is None and len(raw) >= (min_slots or 0):
            break
        if day.weekday() in working_days and day not in skip:
            for pos, (start, end) in enumerate(times):
                raw.append((day, pos, time.fromisoformat(start), time.fromisoformat(end)))
        day += timedelta(days=1)

    width = max(2, len(str(len(raw))))
    return [
        Slot(f"S{n:0{width}d}", d, start, end, slot_number=pos, pref_penalty=pos)
        for n, (d, pos, start, end) in enumerate(raw, start=1)
    ]
