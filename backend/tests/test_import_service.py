import pandas as pd
import pytest

from app.core.validation import DataValidationError
from app.services.data_generator import PRESETS, generate_dataset, write_dataset
from app.services.import_service import load_dataset, parse_dataset


def errors_of(frames) -> list[str]:
    dataset, report = parse_dataset(frames)
    assert dataset is None
    return report.messages()


def test_valid_frames_parse(tiny_frames, tiny_dataset):
    dataset, report = parse_dataset(tiny_frames)
    assert report.ok and not report.warnings
    assert [e.exam_id for e in dataset.exams] == ["E1", "E2", "E3"]
    assert [e.student_count for e in dataset.exams] == [25, 27, 10]
    assert len(dataset.enrollments) == len(tiny_dataset.enrollments)
    assert dataset.exams[0].priority == 0  # optional column defaults
    assert [s.slot_number for s in dataset.slots] == [0, 1, 0, 1]  # derived
    assert [s.pref_penalty for s in dataset.slots] == [0, 1, 0, 1]


def test_duplicate_exam_id_rejected(tiny_frames):
    tiny_frames["exams"].loc[1, "exam_id"] = "E1"
    assert any("duplicate exam_id 'E1'" in m for m in errors_of(tiny_frames))


def test_missing_required_field_rejected(tiny_frames):
    tiny_frames["exams"].loc[0, "subject_name"] = ""
    msgs = errors_of(tiny_frames)
    assert "exams.csv row 2: 'subject_name' is required" in msgs


def test_missing_required_column_rejected(tiny_frames):
    tiny_frames["exams"] = tiny_frames["exams"].drop(columns=["exam_type"])
    assert "exams.csv: missing required column(s): exam_type" in errors_of(tiny_frames)


def test_invalid_student_reference_uses_documented_message(tiny_frames):
    tiny_frames["enrollments"].loc[0, "student_id"] = "ST999"
    assert "enrollments.csv row 2: E1 references student ST999, but ST999 does not exist." in errors_of(
        tiny_frames
    )


def test_invalid_exam_reference_rejected(tiny_frames):
    tiny_frames["enrollments"].loc[0, "exam_id"] = "E99"
    assert any("ST001 is enrolled in E99, but E99 does not exist." in m for m in errors_of(tiny_frames))


def test_duplicate_enrollment_rejected(tiny_frames):
    dup = tiny_frames["enrollments"].iloc[[0]]
    tiny_frames["enrollments"] = pd.concat([tiny_frames["enrollments"], dup], ignore_index=True)
    assert any("duplicate enrollment: ST001 is enrolled in E1" in m for m in errors_of(tiny_frames))


@pytest.mark.parametrize("capacity", ["0", "-5"])
def test_non_positive_room_capacity_rejected(tiny_frames, capacity):
    tiny_frames["rooms"].loc[0, "capacity"] = capacity
    assert any("room R1 has non-positive capacity" in m for m in errors_of(tiny_frames))


def test_non_integer_values_rejected(tiny_frames):
    tiny_frames["exams"].loc[0, "duration_minutes"] = "three hours"
    assert any("'duration_minutes' must be an integer" in m for m in errors_of(tiny_frames))


def test_empty_slot_set_rejected(tiny_frames):
    tiny_frames["slots"] = tiny_frames["slots"].iloc[0:0]
    assert "slots.csv: no slots defined." in errors_of(tiny_frames)


def test_slot_end_before_start_rejected(tiny_frames):
    tiny_frames["slots"].loc[0, "end_time"] = "08:00"
    assert any("end_time 08:00 must be after start_time 09:30" in m for m in errors_of(tiny_frames))


def test_all_errors_are_collected_not_fail_fast(tiny_frames):
    tiny_frames["exams"].loc[1, "exam_id"] = "E1"
    tiny_frames["rooms"].loc[0, "capacity"] = "0"
    tiny_frames["slots"] = tiny_frames["slots"].iloc[0:0]
    assert len(errors_of(tiny_frames)) >= 3


def test_student_count_is_reconciled_with_enrollments(tiny_frames):
    tiny_frames["exams"].loc[0, "student_count"] = "99"
    dataset, report = parse_dataset(tiny_frames)
    assert report.ok
    assert dataset.exams[0].student_count == 25
    assert any("E1 lists student_count=99 but has 25 enrollments; using 25." in str(w) for w in report.warnings)


def test_optional_room_fields_default(tiny_frames):
    tiny_frames["rooms"] = tiny_frames["rooms"][["room_id", "room_code", "capacity"]]
    dataset, report = parse_dataset(tiny_frames)
    assert report.ok
    assert all(r.available and r.room_type == "classroom" for r in dataset.rooms)


def test_load_dataset_raises_with_all_messages(tmp_path):
    (tmp_path / "exams.csv").write_text("exam_id\nE1\n")
    with pytest.raises(DataValidationError) as exc:
        load_dataset(tmp_path)
    assert "file not found" in str(exc.value)


def test_generated_csvs_round_trip(tmp_path):
    original = generate_dataset(PRESETS["small"])
    write_dataset(original, tmp_path)
    loaded = load_dataset(tmp_path)
    assert loaded.exams == original.exams
    assert loaded.rooms == original.rooms
    assert loaded.slots == original.slots
    assert loaded.students == original.students
    assert loaded.enrollments == original.enrollments
