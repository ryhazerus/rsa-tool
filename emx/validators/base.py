"""Shared Issue dataclass and BaseValidator ABC."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator


class Severity(str, Enum):
    ERROR = "ERROR"
    WARN = "WARN"
    INFO = "INFO"

    def __lt__(self, other: "Severity") -> bool:
        order = [Severity.INFO, Severity.WARN, Severity.ERROR]
        return order.index(self) < order.index(other)


@dataclass
class Issue:
    severity: Severity
    rule: str           # e.g. "ids.DUPLICATE_ID_IN_FILE"
    file_path: Path
    line: int
    element_id: str
    element_name: str
    message: str


class BaseValidator:
    def validate(self, registry, resolver) -> Iterator[Issue]:
        raise NotImplementedError
