"""Format and print validation issues."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from .validators.base import Issue, Severity


_SEVERITY_COLOR = {
    Severity.ERROR: "\033[31m",  # red
    Severity.WARN:  "\033[33m",  # yellow
    Severity.INFO:  "\033[36m",  # cyan
}
_RESET = "\033[0m"


def _supports_color(stream: TextIO) -> bool:
    return hasattr(stream, "isatty") and stream.isatty()


def print_text(issues: list[Issue], stream: TextIO = sys.stdout, base_dir: Path | None = None) -> None:
    use_color = _supports_color(stream)
    for issue in issues:
        sev = issue.severity.value
        if use_color:
            sev = f"{_SEVERITY_COLOR[issue.severity]}{sev}{_RESET}"

        rel = issue.file_path
        if base_dir:
            try:
                rel = issue.file_path.relative_to(base_dir)
            except ValueError:
                pass

        loc = f"{rel}:{issue.line}" if issue.line else str(rel)
        name_part = f"  {issue.element_name}" if issue.element_name else ""
        id_part = f"  {issue.element_id}" if issue.element_id else ""

        print(f"[{sev}]  {issue.rule:<40} {loc}", file=stream)
        if issue.element_id or issue.element_name:
            print(f"         element:{id_part}{name_part}", file=stream)
        print(f"         {issue.message}", file=stream)


def print_json(issues: list[Issue], stream: TextIO = sys.stdout) -> None:
    data = [
        {
            "severity": i.severity.value,
            "rule": i.rule,
            "file": str(i.file_path),
            "line": i.line,
            "element_id": i.element_id,
            "element_name": i.element_name,
            "message": i.message,
        }
        for i in issues
    ]
    json.dump(data, stream, indent=2)
    print(file=stream)


def print_summary(issues: list[Issue], stream: TextIO = sys.stdout) -> None:
    errors = sum(1 for i in issues if i.severity == Severity.ERROR)
    warns = sum(1 for i in issues if i.severity == Severity.WARN)
    infos = sum(1 for i in issues if i.severity == Severity.INFO)
    parts = []
    if errors:
        parts.append(f"{errors} error(s)")
    if warns:
        parts.append(f"{warns} warning(s)")
    if infos:
        parts.append(f"{infos} info(s)")
    if not parts:
        print("No issues found.", file=stream)
    else:
        print(f"\n{', '.join(parts)} found.", file=stream)
