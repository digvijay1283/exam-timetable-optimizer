from app.optimization.constraints.consecutive_exam import consecutive_conflicts
from app.optimization.constraints.distribution import distribution_penalty
from app.optimization.constraints.room_capacity import capacity_violations
from app.optimization.constraints.room_conflict import room_collisions
from app.optimization.constraints.room_suitability import room_type_mismatches, unavailable_rooms
from app.optimization.constraints.room_utilization import room_utilization_penalty
from app.optimization.constraints.short_gap import short_gaps
from app.optimization.constraints.slot_preference import slot_preference_penalty
from app.optimization.constraints.student_conflict import student_clashes
from app.optimization.constraints.valid_slot import assigned_mask, duration_violations, unassigned

__all__ = [
    "assigned_mask",
    "capacity_violations",
    "consecutive_conflicts",
    "distribution_penalty",
    "duration_violations",
    "room_collisions",
    "room_type_mismatches",
    "room_utilization_penalty",
    "short_gaps",
    "slot_preference_penalty",
    "student_clashes",
    "unassigned",
    "unavailable_rooms",
]
