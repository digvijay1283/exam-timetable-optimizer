"""Pre-run feasibility check, the "Validate Data" step (docs/SPEC_DECISIONS.md section 11).

Catches problems that would make a zero-violation timetable impossible, with readable messages,
instead of letting the GA run and silently fail.
"""
from __future__ import annotations

from app.core.validation import ValidationReport
from app.optimization.context import OptimizationContext
from app.services.conflict_service import dsatur_colors, greedy_clique_size

FILE = "feasibility"


def check_feasibility(ctx: OptimizationContext) -> ValidationReport:
    report = ValidationReport()
    if ctx.n_slots == 0:
        report.error(FILE, "no slots defined.")
        return report
    if ctx.n_rooms == 0:
        report.error(FILE, "no rooms defined.")
        return report

    longest_slot = int(ctx.slot_minutes.max())
    for i, exam_id in enumerate(ctx.exam_ids):
        if not ctx.slot_ok[i].any():
            report.error(
                FILE,
                f"{exam_id} lasts {ctx.exam_minutes[i]} min but the longest slot is {longest_slot} min.",
            )
        need = int(ctx.student_count[i])
        if ctx.room_ok[i].any():
            continue
        usable = ctx.room_available & ctx.room_type_ok[i]
        if not usable.any():
            exam = ctx.dataset.exams[i]
            report.error(
                FILE, f"{exam_id} has no available room compatible with exam type '{exam.exam_type}'."
            )
        else:
            largest = int(ctx.room_capacity[usable].max())
            report.error(
                FILE, f"{exam_id} needs {need} seats but the largest compatible available room has {largest}."
            )

    clique = greedy_clique_size(ctx.conflict)
    if clique > ctx.n_slots:
        report.error(
            FILE,
            f"At least {clique} slots are needed ({clique} exams share students pairwise) "
            f"but only {ctx.n_slots} slots are defined.",
        )

    cells = ctx.n_slots * int(ctx.room_available.sum())
    if ctx.n_exams > cells:
        report.error(
            FILE,
            f"{ctx.n_exams} exams cannot fit into {ctx.n_slots} slots x "
            f"{int(ctx.room_available.sum())} available rooms = {cells} (slot, room) cells.",
        )

    if ctx.n_exams:
        colors_needed = int(dsatur_colors(ctx.conflict).max()) + 1
        if colors_needed > ctx.n_slots:
            report.warn(
                FILE,
                f"A greedy colouring needs {colors_needed} slots but only {ctx.n_slots} are defined; "
                "a clash-free timetable may not exist.",
            )
    return report
