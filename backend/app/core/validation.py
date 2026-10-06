"""Issue collection for data import and pre-run feasibility checks."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Issue:
    file: str
    message: str
    row: int | None = None  # CSV line number (header is line 1)

    def __str__(self) -> str:
        where = f"{self.file} row {self.row}" if self.row is not None else self.file
        return f"{where}: {self.message}"


@dataclass
class ValidationReport:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, file: str, message: str, row: int | None = None) -> None:
        self.errors.append(Issue(file, message, row))

    def warn(self, file: str, message: str, row: int | None = None) -> None:
        self.warnings.append(Issue(file, message, row))

    def extend(self, other: "ValidationReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)

    def messages(self) -> list[str]:
        return [str(i) for i in self.errors]


class DataValidationError(Exception):
    def __init__(self, report: ValidationReport):
        self.report = report
        lines = report.messages()
        super().__init__(f"{len(lines)} validation error(s):\n" + "\n".join(f"  - {m}" for m in lines))
