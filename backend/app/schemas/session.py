from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    academic_year: str = Field(min_length=1, max_length=20)
    semester: str = Field(min_length=1, max_length=20)
    start_date: date
    end_date: date
    working_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], description="Monday = 0")
    slots_per_day: int = Field(default=2, ge=1, le=3)

    @field_validator("working_days")
    @classmethod
    def _days_valid(cls, v: list[int]) -> list[int]:
        if not v or any(d < 0 or d > 6 for d in v):
            raise ValueError("working_days must be a non-empty list of weekday numbers 0 (Mon) to 6 (Sun)")
        return sorted(set(v))

    @model_validator(mode="after")
    def _dates_ordered(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        return self


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    academic_year: str
    semester: str
    start_date: date
    end_date: date
    working_days: list[int]
    slots_per_day: int
    created_at: datetime


class SessionDetail(SessionOut):
    counts: dict[str, int]


class ImportResult(BaseModel):
    imported: int
    warnings: list[str] = []
    invalidated_timetables: int = 0


class SlotGenerateRequest(BaseModel):
    slot_times: list[tuple[str, str]] | None = Field(
        default=None, description="Override (start, end) per slot of the day, HH:MM"
    )
    holidays: list[date] = []


class SampleRequest(BaseModel):
    name: Literal["small", "medium", "large"]


class DataCheck(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str]
    stats: dict[str, float | int | None]
