from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict


class TimetableOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    run_id: int | None
    name: str
    fitness: float
    penalty: float
    hard_violations: int
    status: str
    breakdown: dict
    created_at: datetime


class EntryOut(BaseModel):
    exam_id: str
    subject_code: str
    subject_name: str
    department: str
    semester: str
    exam_type: str
    students: int
    duration_minutes: int
    slot_id: str
    date: date
    start_time: time
    end_time: time
    room_id: str
    room_code: str
    building: str
    capacity: int


class TimetableDetail(TimetableOut):
    entries: list[EntryOut]
    total_entries: int


class AssignmentIn(BaseModel):
    exam_id: str
    slot_id: str
    room_id: str


class ValidateRequest(BaseModel):
    session_id: int
    entries: list[AssignmentIn]


class ValidationOut(BaseModel):
    valid: bool
    hard_violations: int
    student_conflicts: int
    room_conflicts: int
    capacity_violations: int
    unassigned: int
    unavailable_rooms: int
    room_type_mismatches: int
    duration_violations: int
    same_day_conflicts: int
    details: list[str]
